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
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from datetime import datetime

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
            length = 0.0
            width = 0.0
            height = 0.0
            dimension_id = False
            if picking.package_ids:
                picking.shipping_weight = picking.weight_bulk + sum(
                    [pack.shipping_weight for pack in picking.package_ids])
            else:
                # picking.shipping_weight = sum(move.weight for move in picking.move_lines if move.state != 'cancel')
                for line in picking.move_lines:
                    dimension_id = line.product_id.product_tmpl_id.product_dimension_line.filtered(lambda d: d.quantity == line.product_uom_qty)
                if dimension_id:
                    length = dimension_id.length
                    width = dimension_id.width
                    height = dimension_id.height
                    picking.shipping_weight = dimension_id.weight_lbs
                    picking.shipping_weight_oz = dimension_id.weight_oz
            picking.length = length
            picking.width = width
            picking.height = height
                
    def _inverse_shipping_weight(self):
        pass

    def _get_default_weight_oz_uom(self):
        uom_id = self.env.ref('uom.product_uom_oz', False) or self.env['uom.uom'].search(
            [('measure_type', '=', 'weight'), ('uom_type', '=', 'reference')], limit=1)
        return uom_id.display_name

    shipstation_carrier_id = fields.Many2one('shipstation.carrier', 'Shipstation Carrier')
    shipping_provider_id = fields.Selection([('shipstation', 'Shipstation')], default='shipstation')
    shipping_rate = fields.Float('Shipping Rate', copy=False)
    ship_package_id = fields.Many2one('shipstation.package', 'Package')
    length = fields.Float('L (in)', copy=False, compute='_compute_shipping_weight',
                                   inverse='_inverse_shipping_weight',store=True, compute_sudo=True)
    width = fields.Float('W (in)', copy=False, compute='_compute_shipping_weight',
                                   inverse='_inverse_shipping_weight', store=True, compute_sudo=True)
    height = fields.Float('H (in)', copy=False, compute='_compute_shipping_weight',
                                   inverse='_inverse_shipping_weight', store=True, compute_sudo=True)
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
    shipping_weight_oz = fields.Float("Weight(oz)", compute='_compute_shipping_weight',
                                   inverse='_inverse_shipping_weight',
                                   digits='Stock Weight', store=True, compute_sudo=True)
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
    weight_uom_name_oz = fields.Char(string='Weight oz unit of measure', default=_get_default_weight_oz_uom)
    shipping_package_line = fields.One2many('shipping.package', 'picking_id',
                                  string="Shipping Package")

    @api.onchange('shipping_weight_oz', 'shipping_weight')
    def onchange_shipping_weights(self):
        """
        Get total weight and validation.
        :return:
        """
        if self.shipping_weight_oz >= 16 or self.shipping_weight_oz < 0:
            raise ValidationError(_("Please enter shipping weight(oz) between 0 and 15.99!"))
        if self.shipping_weight < 0:
            raise ValidationError(_("shipping weight(lb) should not be negative!"))

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
                raise ValidationError(
                    _("No applicable services were available for the configured Order %s!" % picking.name))
            logger.info("Response!!!!!! %s" % response_data)
            if api_call.status_code not in (200, 201):
                raise ValidationError(_(response_data.get('ExceptionMessage')))
            picking.quote_lines.unlink()
            data = srm.rate_response_data(response_data, api_config_obj, ship_carrier_id)
            picking.with_context(api_call=True).write({'quote_lines': data.get('line_ids'),
                                                       'carrier_id': data.get('min_service').get('service_id', False),
                                                       'carrier_price': data.get('min_service').get('rate', 0),
                                                       'ship_package_id': data.get('min_service').get('package_id',
                                                                                                      False),
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

    def _put_in_pack(self, move_line_ids):
        package = False
        for pick in self:
            move_lines_to_pack = self.env['stock.move.line']
            package = self.env['stock.quant.package'].create({})

            precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            if float_is_zero(move_line_ids[0].qty_done, precision_digits=precision_digits):
                for line in move_line_ids:
                    line.qty_done = line.product_uom_qty
            package_dict = {}
            item_dict = {}
            package_history = []
            for ml in move_line_ids:
                item_dict = {
                    'product_id': ml.product_id.id, 'tracking_ref':ml.tracking_ref,
                    'shipping_date':ml.shipping_date,'package_id': package.id, 'product_qty': ml.qty_done}

                package_dict = {
                     'tracking_ref':ml.tracking_ref, 'package_date':ml.shipping_date,
                     'shipstation_carrier_id': ml.shipstation_carrier_id.id, 'carrier_id': ml.carrier_id.id, 'picking_id': ml.picking_id.id, 'sale_id': ml.sale_id.id}
                if float_compare(ml.qty_done, ml.product_uom_qty,
                                 precision_rounding=ml.product_uom_id.rounding) >= 0:
                    move_lines_to_pack |= ml
                else:
                    quantity_left_todo = float_round(
                        ml.product_uom_qty - ml.qty_done,
                        precision_rounding=ml.product_uom_id.rounding,
                        rounding_method='UP')
                    done_to_keep = ml.qty_done
                    new_move_line = ml.copy(
                        default={'product_uom_qty': 0, 'qty_done': ml.qty_done, 'shipping_weight': ml.shipping_weight, 'length': ml.length, 'width': ml.width, 'shipping_weight_oz': ml.shipping_weight_oz})


                    vals = {'product_uom_qty': quantity_left_todo, 'qty_done': 0.0,
                     'tracking_ref':'', 'shipping_date': datetime.today()}
                    if ml.move_id.sale_line_id.line_type == 'dropship':
                        shipstation_carrier_id = self.env[
                                'shipstation.carrier'].search(
                                    [], order='id', limit=1)

                        carrier_id = self.env['delivery.carrier'].search(
                                    [], order='id', limit=1)
                        vals.update({'shipstation_carrier_id': shipstation_carrier_id.id or False
                     , 'carrier_id': carrier_id and carrier_id.id or False})
                    if pick.picking_type_id.code == 'incoming':
                        if ml.lot_id:
                            vals['lot_id'] = False
                        if ml.lot_name:
                            vals['lot_name'] = False
                    ml.write(vals)
                    new_move_line.write({'product_uom_qty': done_to_keep})
                    move_lines_to_pack |= new_move_line
                    move_lines_to_pack.write({'product_demand': ml.move_id.product_uom_qty
            })
                package_history.append((0,0,item_dict))
            if package_dict:
                package.write(package_dict)
            self.update({'shipping_package_line': package_history})
            package_level = self.env['stock.package_level'].create({
                'package_id': package.id,
                'picking_id': pick.id,
                'location_id': False,
                'location_dest_id': move_line_ids.mapped('location_dest_id').id,
                'move_line_ids': [(6, 0, move_lines_to_pack.ids)],
                'company_id': pick.company_id.id,
            })
            move_lines_to_pack.write({
                'result_package_id': package.id
            })

        return package

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

    def action_done(self):
        res = super(StockPicking, self).action_done()
        sale_ids = self.move_lines.mapped('purchase_line_id').mapped('sale_order_id')
        sale_ids.action_show_stock_move_line()
        return res

    def action_assign(self):
        res = super(StockPicking, self).action_assign()
        self.sale_id.action_show_stock_move_line()
        return res

class StockQuantPackage(models.Model):
    _inherit = 'stock.quant.package'

    tracking_ref = fields.Char(string="Tracking Reference")
    package_date = fields.Date(string="Date", default=datetime.today())
    shipstation_carrier_id = fields.Many2one("shipstation.carrier", string="Carrier")
    carrier_id = fields.Many2one("delivery.carrier", string="Shipping Method")
    ship_package_id = fields.Many2one("shipstation.package", string="Package")
    sale_id = fields.Many2one('sale.order', string="Sale Order")
    carrier_price = fields.Float(string="Shipping Cost")
    picking_id = fields.Many2one('stock.picking', string="Picking")
    length = fields.Float('L (in)')
    width = fields.Float('W (in)')
    height = fields.Float('H (in)')

    def send_to_shipper(self, picking, move_line=False):
        self.ensure_one()
        res = self.carrier_id.send_shipping(picking, move_line=move_line)[0]
        if self.carrier_id.free_over and self.sale_id and self.sale_id._compute_amount_total_without_delivery() >= self.carrier_id.amount:
            res['exact_price'] = 0.0
        self.carrier_price = res['exact_price'] * (1.0 + (self.carrier_id.margin / 100.0))
        if move_line:
            move_line.carrier_price = res['exact_price'] * (1.0 + (self.carrier_id.margin / 100.0))
        if res['tracking_number']:
            self.tracking_ref = res['tracking_number']
            if move_line:
                move_line.tracking_ref = res['tracking_number']
        order_currency = self.sale_id.currency_id or self.company_id.currency_id
        msg = _("Shipment sent to carrier %s for shipping with tracking number %s<br/>Cost: %.2f %s") % (self.carrier_id.name, self.tracking_ref, self.carrier_price, order_currency.name)
        self.picking_id.message_post(body=msg)
        self._add_delivery_cost_to_so()

    def _add_delivery_cost_to_so(self):
        self.ensure_one()
        sale_order = self.sale_id
        if sale_order and self.carrier_id.invoice_policy == 'real' and self.carrier_price:
            delivery_lines = sale_order.order_line.filtered(lambda l: l.is_delivery and l.currency_id.is_zero(l.price_unit) and l.product_id == self.carrier_id.product_id)
            carrier_price = self.carrier_price * (1.0 + (float(self.carrier_id.margin) / 100.0))
            if not delivery_lines:
                sale_order._create_delivery_line(self.carrier_id, carrier_price)
            else:
                delivery_line = delivery_lines[0]
                delivery_line[0].write({
                    'price_unit': carrier_price,
                    # remove the estimated price from the description
                    'name': sale_order.carrier_id.with_context(lang=self.partner_id.lang).name,
                })


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    # tracking_ref = fields.Char(string="Tracking Reference", related="result_package_id.tracking_ref", store=True)
    # shipping_date = fields.Date(string="Shipping Date", related="result_package_id.package_date", store=True)
    # shipstation_carrier_id = fields.Many2one("shipstation.carrier", string="Carrier", related="result_package_id.shipstation_carrier_id")
    # carrier_id = fields.Many2one("delivery.carrier", string="Shipping Method", related="result_package_id.carrier_id")

    @api.depends('product_id')
    def _compute_shipping_weight(self):
        for line in self:
            length = 0.0
            width = 0.0
            height = 0.0
            dimension_id = False
            # picking.shipping_weight = sum(move.weight for move in picking.move_lines if move.state != 'cancel')
            dimension_id = line.product_id.product_tmpl_id.product_dimension_line.filtered(lambda d: d.quantity == line.product_uom_qty)
            if dimension_id:
                length = dimension_id.length
                width = dimension_id.width
                height = dimension_id.height
                line.shipping_weight = dimension_id.weight_lbs
                line.shipping_weight_oz = dimension_id.weight_oz
            line.length = length
            line.width = width
            line.height = height

    def _inverse_shipping_weight(self):
        pass

    tracking_ref = fields.Char(string="Tracking Reference")
    shipping_date = fields.Date(string="Shipping Date", default=lambda self: fields.Datetime.now())
    shipstation_carrier_id = fields.Many2one("shipstation.carrier", string="Carrier")
    carrier_id = fields.Many2one("delivery.carrier", string="Shipping Method")
    product_demand = fields.Float(related="move_id.product_uom_qty",
        string='Demand')

    carrier_tracking_ref = fields.Char(string='Tracking Reference', copy=False)
    ship_package_id = fields.Many2one('shipstation.package', 'Package', required="1")
    length = fields.Float('L (in)', compute='_compute_shipping_weight',
                                   inverse='_inverse_shipping_weight',store=True, compute_sudo=True)
    width = fields.Float('W (in)', compute='_compute_shipping_weight',
                                   inverse='_inverse_shipping_weight', store=True, compute_sudo=True)
    height = fields.Float('H (in)', compute='_compute_shipping_weight',
                                   inverse='_inverse_shipping_weight', store=True, compute_sudo=True)
    weight = fields.Float(digits='Stock Weight', help="Total weight of the products in the picking.")
    shipping_weight = fields.Float("Weight for Shipping(lbs)",
                                   compute='_compute_shipping_weight',
                                   inverse='_inverse_shipping_weight',
                                   digits='Stock Weight', store=True, compute_sudo=True,
                                   help="Total weight of the packages and products which are not in a package. That's the weight used to compute the cost of the shipping.")
    shipping_weight_oz = fields.Float("Weight(ozs)", compute='_compute_shipping_weight',
                                   inverse='_inverse_shipping_weight',
                                   digits='Stock Weight', store=True, compute_sudo=True)
    carrier_price = fields.Float(string="Shipping Cost")
    delivery_type = fields.Selection(related='carrier_id.delivery_type', readonly=True)
    weight_uom_name = fields.Char(string='lbs')
    weight_uom_name_oz = fields.Char(string='lbs')
    shipmentId = fields.Char('Label Shipment ID')

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
        for ml in self:
            service_id = ml.carrier_id
            srm = ShipstationRequest(service_id.log_xml, service_id.prod_environment, url, token)
            delivery_nature = 'domestic'
            if service_id.international:
                delivery_nature = 'international'
            check_result = srm.check_required_value(ml.picking_id.partner_id, delivery_nature,
                                                    ml.picking_id.picking_type_id.warehouse_id.partner_id,
                                                    move_line=ml)
            if check_result:
                raise UserError(check_result)

        for move_line in self:
            partner_id = move_line.sale_id.warehouse_id.partner_id
            if not partner_id:
                partner_id = move_line.picking_id.picking_type_id.warehouse_id.partner_id
            to_partner_id = move_line.picking_id.partner_id
            if move_line.picking_id.weight_uom_name == 'kg':
                total_weight = move_line.picking_id._convert_to_lbs(move_line.shipping_weight)
            else:
                total_weight = move_line.shipping_weight
            service_id = move_line.carrier_id
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
                    "length": move_line.length,
                    "width": move_line.width,
                    "height": move_line.height
                },
                "confirmation": move_line.picking_id.confirmation,
                "residential": False
            }
            ship_carrier_id = False
            if move_line.shipstation_carrier_id:
                ship_carrier_id = move_line.shipstation_carrier_id
            elif service_id.shipstation_carrier_id:
                ship_carrier_id = service_id.shipstation_carrier_id

            payload.update({"carrierCode": ship_carrier_id.code})
            if service_id:
                payload.update({"serviceCode": service_id.shipstation_service_code})
            if move_line.ship_package_id:
                payload.update({"packageCode": move_line.ship_package_id.code})
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
                raise ValidationError(
                    _("No applicable services were available for the configured Order %s!" % move_line.picking_id.name))
            logger.info("Response!!!!!! %s" % response_data)
            if api_call.status_code not in (200, 201):
                raise ValidationError(_(response_data.get('ExceptionMessage')))
            data = srm.rate_response_data(response_data, api_config_obj, ship_carrier_id)
            move_line.with_context(api_call=True).write({
                                                'carrier_id': data.get('min_service').get('service_id', False),
                                                'carrier_price': data.get('min_service').get('rate', 0),
                                                'ship_package_id': data.get('min_service').get('package_id')
                                                })
        return False


class ShippingPackages(models.Model):
    _name = "shipping.package"
    _description = "Shipping Package"

    picking_id = fields.Many2one('stock.picking', string="Picking")
    product_id = fields.Many2one('product.product', string="Product")
    tracking_ref = fields.Char(string="Tracking Reference")
    shipping_date = fields.Datetime(string="Shipping Date")
    package_id = fields.Many2one('stock.quant.package', string="Package")
    product_qty = fields.Float(string="Quantity")


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
