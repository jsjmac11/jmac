# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import models, fields, api, _
from .shipstation_request import ShipstationRequest
from odoo.exceptions import UserError
import math


class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    package_carrier_type = fields.Selection(selection_add=[('shipstation', 'Shipstation')])


class ProviderShipstation(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[('shipstation', "Shipstation")])
    shipstation_default_packaging_id = fields.Many2one(
        'product.packaging', string='Default Packaging Type', domain=[('package_carrier_type', '=', 'shipstation')])
    shipstation_default_uom = fields.Selection([
        ('imperial', 'Imperial - LBS & Inch'),
        ('metric', 'Metric - Kgs & Cm')], default='imperial')
    shipstation_carrier_code = fields.Char("Carrier Code")
    shipstation_service_code = fields.Char("Service Code")
    shipstation_carrier_id = fields.Many2one("shipstation.carrier", 'Shipstation Carrier')
    international = fields.Boolean("International")
    domestic = fields.Boolean("Domestic")

    def _shipstation_convert_weight(self, weight):
        weight_uom_id = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
        weight_in_pounds = weight_uom_id._compute_quantity(weight, self.env.ref('uom.product_uom_lb'))
        pounds = int(math.floor(weight_in_pounds))
        ounces = round((weight_in_pounds - pounds) * 16, 3)
        # ounces should be at least 1 for the api request not to fail.
        if pounds == 0 and int(ounces) == 0:
            ounces = 1
        return {'pound': pounds, 'ounce': ounces}

    def shipstation_send_shipping(self, pickings, move_line=False):
        res = []
        api_config_obj = self.env['shipstation.config'].search(
            [('active', '=', True)])
        url = api_config_obj.server_url
        token = api_config_obj.auth_token()
        srm = ShipstationRequest(self.log_xml, self.prod_environment, url, token)
        delivery_nature = 'domestic'
        if self.international:
            delivery_nature = 'international'
        for picking in pickings:
            if move_line:
                package = move_line.mapped('result_package_id')
                check_result = srm.check_required_value(picking.partner_id, delivery_nature,
                                                    picking.picking_type_id.warehouse_id.partner_id, move_line=move_line)
                carrier_id = package.carrier_id
            else:
                check_result = srm.check_required_value(picking.partner_id, delivery_nature,
                                                    picking.picking_type_id.warehouse_id.partner_id, picking=picking)
                carrier_id = picking.carrier_id
                package = False
            if check_result:
                raise UserError(check_result)
            booking = srm.shipstation_request(picking, delivery_nature, is_return=False, package=package)

            if booking.get('error_message'):
                raise UserError(booking['error_message'])

            order = picking.sale_id
            company = order.company_id or picking.company_id or self.env.company
            currency_order = picking.sale_id.currency_id
            if not currency_order:
                currency_order = picking.company_id.currency_id

            # USPS always returns prices in USD
            # if currency_order.name == "USD":
            #     price = booking['price']
            # else:
            #     quote_currency = self.env['res.currency'].search([('name', '=', "USD")], limit=1)
            #     price = quote_currency._convert(
            #       booking['price'], currency_order, company, order.date_order or fields.Date.today())

            carrier_tracking_ref = booking['tracking_number']

            logmessage = (_("Shipment created into %s <br/> <b>Tracking Number : </b>%s") % (
                carrier_id.name, carrier_tracking_ref))
            picking.message_post(body=logmessage, attachments=[('Label-%s-%s-%s.%s' % (
                picking.name.replace('/', ''), carrier_id.shipstation_service_code, carrier_tracking_ref,
                'PDF'), booking['label'])])
            picking.sale_id.message_post(body=logmessage, attachments=[('Label-%s-%s-%s.%s' % (
                picking.name.replace('/', ''), carrier_id.shipstation_service_code, carrier_tracking_ref,
                'PDF'), booking['label'])])

            shipping_data = {'exact_price': picking.carrier_price,
                             'tracking_number': carrier_tracking_ref,
                             'shipmentId': booking['shipmentId']}
            if package:
                move_line.shipmentId = booking['shipmentId']
            else:
                picking.shipmentId = booking['shipmentId']
            res = res + [shipping_data]
            if self.return_label_on_delivery:
                self.get_return_label(picking)
        return res

    def shipstation_get_tracking_link(self, picking):
        return False

    def shipstation_cancel_shipment(self, picking, move_line=False):
        result = {}
        if move_line:
            shipmentId = move_line.shipmentId
        else:
            shipmentId = picking.shipmentId
        old_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'stock.picking'), ('res_id', '=', picking.id)])
        so_old_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'sale.order'), ('res_id', '=', picking.sale_id.id)])
        api_config_obj = self.env['shipstation.config'].search(
            [('active', '=', True)])
        url = api_config_obj.server_url
        token = api_config_obj.auth_token()

        srm = ShipstationRequest(self.log_xml, self.prod_environment, url, token)
        if shipmentId != '-1':
            result = srm.cancel_shipment(int(shipmentId))
        if result.get('error_message'):
            raise UserError(result['error_message'])
        else:
            if move_line:
                logmessage = (_(u'Shipment N° %s has been cancelled') % (move_line.tracking_ref))
                picking.message_post(body=logmessage, attachments=[])
                picking.sale_id.message_post(body=logmessage, attachments=[])
                move_line.write({'tracking_ref': '',
                               'shipmentId': ''})
            else:
                logmessage = (_(u'Shipment N° %s has been cancelled') % (picking.carrier_tracking_ref))
                picking.message_post(body=logmessage, attachments=[])
                picking.write({'carrier_tracking_ref': '',
                               'shipmentId': ''})
        if so_old_attachment:
            old_attachment |= so_old_attachment
        if old_attachment:
            old_attachment.sudo().unlink()

    def send_shipping(self, pickings, move_line=False):
        ''' Send the package to the service provider

        :param pickings: A recordset of pickings
        :return list: A list of dictionaries (one per picking) containing of the form::
                         { 'exact_price': price,
                           'tracking_number': number }
                           # TODO missing labels per package
                           # TODO missing currency
                           # TODO missing success, error, warnings
        '''
        self.ensure_one()
        if self.delivery_type == 'shipstation':
            if hasattr(self, '%s_send_shipping' % self.delivery_type):
                return getattr(self, '%s_send_shipping' % self.delivery_type)(pickings, move_line)
        else:
            return super(ProviderShipstation, self).send_shipping(pickings)

    def cancel_shipment(self, pickings, move_line=False):
        ''' Cancel a shipment

        :param pickings: A recordset of pickings
        '''
        self.ensure_one()
        if self.delivery_type == 'shipstation':
            if hasattr(self, '%s_cancel_shipment' % self.delivery_type):
                return getattr(self, '%s_cancel_shipment' % self.delivery_type)(pickings, move_line)
        else:
            return super(ProviderShipstation, self).cancel_shipment(pickings)
class ShipstationCarrier(models.Model):
    _name = 'shipstation.carrier'
    _description = 'Shipstation Carrier'

    name = fields.Char('Carrier')
    code = fields.Char('Code')


class ShipstationPackage(models.Model):
    _name = 'shipstation.package'
    _description = 'Shipstation Packages'

    carrierCode = fields.Char("Carrier Code")
    code = fields.Char("Code")
    name = fields.Char("Name")
    international = fields.Boolean("International")
    domestic = fields.Boolean("Domestic")
    shipstation_carrier_id = fields.Many2one("shipstation.carrier", 'Shipstation Carrier')
