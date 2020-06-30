# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################
from odoo import models, fields, api, _
import requests
from requests.auth import HTTPBasicAuth
import base64
import json
from odoo.exceptions import ValidationError, UserError
import logging
from .shipstation_request import ShipstationRequest

logger = logging.getLogger('Shipstation Log')


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # @api.depends('move_lines')
    # def _cal_weight(self):
    # 	for picking in self:
    # 		picking.weight = sum(move.weight for move in picking.move_lines if move.state != 'cancel')

    # def _inverse_cal_weight(self):
    # 	pass

    @api.depends('package_ids', 'weight_bulk', 'move_lines')
    def _compute_shipping_weight(self):
        for picking in self:
            if picking.package_ids:
                picking.shipping_weight = picking.weight_bulk + sum(
                    [pack.shipping_weight for pack in picking.package_ids])
            else:
                picking.shipping_weight = sum(move.weight for move in picking.move_lines if move.state != 'cancel')

    def _inverse_shipping_weight(self):
        pass

    shipstation_carrier_id = fields.Many2one('shipstation.carrier', 'Shipstation Carrier')
    shipping_provider_id = fields.Selection([('shipstation', 'Shipstation')], default='shipstation')
    shipping_rate = fields.Float('Shipping Rate', copy=False)
    ship_package_id = fields.Many2one('shipstation.package', 'Package')
    length = fields.Float('L (in)', copy=False)
    width = fields.Float('W (in)', copy=False)
    height = fields.Float('H (in)', copy=False)
    # weight = fields.Float(compute='_cal_weight',inverse='_inverse_cal_weight', digits='Stock Weight', store=True, help="Total weight of the products in the picking.", compute_sudo=True)
    quote_lines = fields.One2many('shipping.quote.line', 'picking_id',
                                  string="Shipping Quotes")
    transit_days = fields.Float(string="Transit Days", copy=False)
    # Orver write to make editable
    shipping_weight = fields.Float("Weight for Shipping",
                                   compute='_compute_shipping_weight',
                                   inverse='_inverse_shipping_weight',
                                   digits='Stock Weight', store=True, compute_sudo=True,
                                   help="Total weight of the packages and products which are not in a package. That's the weight used to compute the cost of the shipping.")
    insure_package_type = fields.Selection(
        [('shipsurance', 'Shipsurance'),
         ('carrier', 'Carrier'),
         ('provider', 'Other/External')],
        copy=False, string="Insure Type")
    shipping_weight_oz = fields.Float("Weight(oz)")
    rule_id = fields.Many2one("automation.rule", string="Rule")
    confirmation = fields.Selection(
        [('none', 'None'),
         ('delivery', 'Delivery'),
         ('signature', 'Signature'),
         ('adult_signature', 'Adult Signature'),
         ('direct_signature', 'Direct Signature')],
        copy=False, string="Confirmation", default='none')
    shipmentId = fields.Char('Label Shipment ID')
    tag_id = fields.Many2one("order.tag", string="Tags")

    @api.onchange('carrier_id')
    def onchange_carrier_id(self):
        """
        Get the Server URL based on server selected.
        :return:
        """
        if self.carrier_id:
            self.shipping_rate = 0.0

    def _convert_to_lbs(self, weight_in_kg):
        # Return weight in LBS as prefered
        return round(weight_in_kg * 2.20462, 3)

    def get_shipping_rates(self):
        api_config_obj = self.env['shipstation.config'].search(
            [('active', '=', True)])
        delivery_obj = self.env['delivery.carrier']
        if not api_config_obj:
            return False
        url = api_config_obj.server_url + '/shipments/getrates'
        token = api_config_obj.auth_token()
        headers = {
            'Host': 'ssapi.shipstation.com',
            'Content-Type': 'application/json',
            'Authorization': 'Basic %s' % token
        }
        # Check for required fields for all pickings
        for pick in self:
            service_id = pick.carrier_id
            srm = ShipstationRequest(service_id.log_xml, service_id.prod_environment, url, token)
            delivery_nature = 'domestic'
            if service_id.international:
                delivery_nature = 'international'
            check_result = srm.check_required_value(pick.partner_id, delivery_nature,
                                                    pick.picking_type_id.warehouse_id.partner_id,
                                                    picking=pick)
            if check_result:
                raise UserError(check_result)

        for picking in self:
            partner_id = picking.sale_id.warehouse_id.partner_id
            if not partner_id:
                partner_id = picking.picking_type_id.warehouse_id.partner_id
            to_partner_id = picking.partner_id
            if picking.weight_uom_name == 'kg':
                total_weight = picking._convert_to_lbs(picking.shipping_weight)
            else:
                total_weight = picking.shipping_weight
            service_id = picking.carrier_id
            payload = {
                "fromPostalCode": partner_id.zip.replace(" ", "") if partner_id.zip else '',
                "toState": to_partner_id.state_id.code or '',
                "toCountry": to_partner_id.country_id.code or '',
                "toPostalCode": to_partner_id.zip.replace(" ", "") if to_partner_id.zip else '',
                "toCity": to_partner_id.city or '',
                "weight": {
                    "value": total_weight,
                    "units": "pounds"
                },
                "dimensions": {
                    "units": "inches",
                    "length": picking.length,
                    "width": picking.width,
                    "height": picking.height
                },
                "confirmation": picking.confirmation,
                "residential": False
            }
            ship_carrier_id = False
            if picking.shipstation_carrier_id:
                ship_carrier_id = picking.shipstation_carrier_id
            elif service_id.shipstation_carrier_id:
                ship_carrier_id = service_id.shipstation_carrier_id

            payload.update({"carrierCode": ship_carrier_id.code})
            if service_id:
                payload.update({"serviceCode": service_id.shipstation_service_code})
            if picking.ship_package_id:
                payload.update({"packageCode": picking.ship_package_id.code})
            try:
                logger.info("payload!!!!!! %s" % payload)
                api_call = requests.request("POST", url, headers=headers, data=json.dumps(payload))
                logger.info("api_call!!!!!! %s" % api_call)
                response_data = json.loads(api_call.text)
            except requests.exceptions.ConnectionError as e:
                logger.info("Connection ERROR!!!!!! %s" % e)
                raise ValidationError(_("Failed to establish a connection. Please check internet connection"))
            except ValidationError as e:
                logger.info("API ERROR::::::: %s" % e)
                raise
            except Exception as e:
                logger.info("ERROR!!!!!! %s" % e)
                raise ValidationError(_(e))

            if not response_data:
                raise ValidationError(_("Service Unavailable for order %s!" % picking.name))
            logger.info("Response!!!!!! %s" % response_data)
            if api_call.status_code not in (200, 201):
                raise ValidationError(_(response_data.get('ExceptionMessage')))
            picking.quote_lines.unlink()
            line_ids = []
            service_rate_lst = []
            for data in response_data:
                service_id = delivery_obj.search([('shipstation_service_code', '=', data.get('serviceCode'))])
                if not service_id:
                    service_id = api_config_obj.get_services(ship_carrier_id)
                pack_name = data.get('serviceName', '').split(' - ')
                pack_id = False
                if pack_name:
                    pack_id = self.env['shipstation.package'].search([('name', '=', pack_name[1])])
                values = {
                    'shipstation_carrier_id': ship_carrier_id.id,
                    'service_id': service_id.id,
                    'service_name': data.get('serviceName', ''),
                    'service_code': data.get('serviceCode', ''),
                    'shipping_cost': data.get('shipmentCost', 0),
                    'other_cost': data.get('otherCost', 0),
                    'rate': data.get('shipmentCost', 0) + data.get('otherCost', 0),
                    # 'transit_days': result.get('transitdays', 0),
                    'package_id': pack_id.id if pack_id else False,
                }
                service_rate_lst.append(values)
                line_ids.append((0, 0, values))
            min_service = min(service_rate_lst, key=lambda x: x['rate'])
            picking.with_context(api_call=True).write({'quote_lines': line_ids,
                                                       'carrier_id': min_service.get('service_id', False),
                                                       'carrier_price': min_service.get('rate', 0),
                                                       'ship_package_id': min_service.get('package_id', False),
                                                       })
        return False

    def write(self, vals):
        pickings = self
        if 'carrier_id' in vals and vals.get('carrier_id'):
            service_id = self.env['delivery.carrier'].search(
                [('id', '=', vals.get('carrier_id'))])
            vals[
                'shipstation_carrier_id'] = service_id.shipstation_carrier_id.id if service_id.delivery_type == 'shipstation' else False

        res = super(StockPicking, pickings).write(vals)
        if not self._context.get('api_call'):
            for pick in pickings:
                if ('carrier_id' in vals and vals.get('carrier_id')) \
                        or (pick.carrier_id and \
                            ('ship_package_id' in vals or \
                             'length' in vals or 'width' in vals or \
                             'height' in vals or 'shipping_weight' in vals)):
                    logger.info("\n\n\nAPI CALL START!!!!!! ")
                    pick.get_shipping_rates()
        return res

    def print_packing_slip(self):
        # Add report in attachments
        pdf_content = self.env.ref('stock.action_report_delivery').sudo().render_qweb_pdf([self.id])[0]
        self.env['ir.attachment'].create({
            'name': _("Packing Slip - %s" % self.name),
            'type': 'binary',
            'datas': base64.encodestring(pdf_content),
            'res_model': self._name,
            'res_id': self.id
        })


class ShippingQuoteLine(models.Model):
    _name = "shipping.quote.line"
    _description = "Shipping Quote Lines"
    _rec_name = 'service_id'

    picking_id = fields.Many2one('stock.picking')
    shipstation_carrier_id = fields.Many2one('shipstation.carrier', 'Carrier')
    service_id = fields.Many2one('delivery.carrier', string="Service ID")
    service_name = fields.Char("Service")
    service_code = fields.Char("Service Code")
    rate = fields.Float(string="Rate")
    other_cost = fields.Float(string='Other Cost')
    shipping_cost = fields.Float(string="Shipment Cost")
    transit_days = fields.Float(string="Transit Days")
    package_id = fields.Many2one('shipstation.package', 'Package')

    def set_carrier_rate(self):
        self.ensure_one()
        self.picking_id.with_context(api_call=True).write({'carrier_id': self.service_id.id,
                                                           'carrier_price': self.rate,
                                                           # 'transit_days':self.transit_days,
                                                           'ship_package_id': self.package_id.id,
                                                           })
        return True
