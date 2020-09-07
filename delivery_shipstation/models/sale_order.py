# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from .shipstation_request import ShipstationRequest
import requests
import json
import logging

logger = logging.getLogger('Order Log')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends('order_line')
    def _compute_order_weight(self):
        for order in self:
            order.order_quantity = int(
                sum(order.order_line.filtered(lambda l: not l.is_delivery).mapped('product_uom_qty')))
            line_with_weight = order.order_line.filtered(
                lambda line: line.product_id.weight > 0.00 or line.product_id.weight_oz > 0.00)
            weight_oz = 0.0
            order_weight = 0.0
            for line in line_with_weight:
                weight_oz += line.product_qty * line.product_id.weight_oz
                order_weight += line.product_qty * line.product_id.weight
            order.weight_oz = weight_oz
            order.order_weight = order_weight

    rule_id = fields.Many2one("automation.rule", string="Rule", copy=False)
    order_weight = fields.Float(compute='_compute_order_weight', string='Order Weight')
    order_quantity = fields.Integer(compute='_compute_order_weight', string='Order Quantity')
    rule_message = fields.Text(readonly=True, copy=False)
    requested_service_id = fields.Many2one("order.service", string="Requested Shipping")
    service_price = fields.Float("Service Price")
    tag_id = fields.Many2one("order.tag", string="Order Tag")
    weight_oz = fields.Float(compute='_compute_order_weight', string='Order Weight(oz)')
    payment_received = fields.Float("Total Payment Received")
    shipping_cost = fields.Float(string="Shipping Cost", compute='_amount_all', store=True,
                                 help="Sum of Requested Service Charge in the sales order lines")

    @api.onchange('requested_service_id')
    def onchange_requested_service_id(self):
        """
        Get service price.
        :return:  service_price
        """
        self.service_price = self.requested_service_id and self.requested_service_id.price or 0.0

    def check_rule_matched(self, rules_ids, product_id):
        rule_matched = []
        for rule in rules_ids:
            matched_rule_id = rule
            for line in rule.rule_line:
                str_c = ''
                operator = str(line.operator_type_id.operator) + ' '
                if line.category_type == 'qty':
                    str_c = str(self.order_quantity)
                    if line.operator_type_id.operator in ('in', 'not in'):
                        operator += str([line.value])
                    else:
                        operator += str(line.value)
                elif line.category_type == 'wgt':
                    if line.weight_lb:
                        str_c = str(self.order_weight)
                        if line.operator_type_id.operator in ('in', 'not in'):
                            operator += str([line.weight_lb])
                        else:
                            operator += str(line.weight_lb)
                    else:
                        str_c = str(self.weight_oz)
                        if line.operator_type_id.operator in ('in', 'not in'):
                            operator += str([line.weight_oz])
                        else:
                            operator += str(line.weight_oz)
                elif line.category_type == 'val':
                    str_c = str(self.amount_total)
                    if line.operator_type_id.operator in ('in', 'not in'):
                        operator += str([line.value])
                    else:
                        operator += str(line.value)
                elif line.category_type == 'req_service':
                    str_c = str(self.requested_service_id.id)
                    operator += str(line.requested_service_id.ids)
                elif line.category_type == 'tag':
                    str_c = str(self.tag_id.id)
                    operator += str(line.tag_ids.ids)
                elif line.category_type == 'country':
                    str_c = str(self.partner_id.country_id.id)
                    operator += str(line.country_ids.ids)
                # Product specific type match
                if product_id:
                    if line.category_type == 'product':
                        str_c = str(product_id.id)
                        operator += str(line.product_ids.ids)
                    elif line.category_type == 'inventory':
                        str_c = str(product_id.qty_available)
                        if line.operator_type_id.operator in ('in', 'not in'):
                            operator += str([line.value])
                        else:
                            operator += str(line.value)
                    elif line.category_type == 'length':
                        str_c = str(product_id.length)
                        if line.operator_type_id.operator in ('in', 'not in'):
                            operator += str([line.value])
                        else:
                            operator += str(line.value)
                    elif line.category_type == 'width':
                        str_c = str(product_id.width)
                        if line.operator_type_id.operator in ('in', 'not in'):
                            operator += str([line.value])
                        else:
                            operator += str(line.value)
                    elif line.category_type == 'height':
                        str_c = str(product_id.height)
                        if line.operator_type_id.operator in ('in', 'not in'):
                            operator += str([line.value])
                        else:
                            operator += str(line.value)
                elif not product_id and not str_c:
                    matched_rule_id = False
                    break

                if str_c:
                    str_c += ' ' + operator
                    if not eval(str_c):
                        matched_rule_id = False
                        break

            if matched_rule_id:
                rule_matched.append(rule)
        return rule_matched

    def apply_automation_rule(self, picking=None):
        automation_rule_ids = self.env['automation.rule'].search([], order="sequence")
        val_dict = {}
        matched_rule_id = False
        product_id = False
        grule_matched = []
        if len(self.order_line.filtered(lambda l: l.product_id.type != 'service')) == 1:
            product_id = self.order_line.mapped('product_id')
        rule_ids = automation_rule_ids.filtered(
            lambda r: r.rule_type == 'match' and not r.is_global_rule
                      and not r.global_rule_id)
        global_rule_ids = automation_rule_ids.filtered(lambda r: r.is_global_rule)
        if global_rule_ids:
            grule_matched = self.check_rule_matched(global_rule_ids, product_id)
        if grule_matched:
            matched_global_rule_ids = [r.id for r in grule_matched]
            auto_rule_ids = automation_rule_ids.filtered(
                lambda r: r.rule_type == 'match' and not r.is_global_rule
                          and r.global_rule_id.id in matched_global_rule_ids)
            if auto_rule_ids:
                rule_ids += auto_rule_ids

        rule_ids = self.env['automation.rule'].search([('id', 'in', rule_ids.ids)], order="sequence")
        rule_matched = self.check_rule_matched(rule_ids, product_id)
        if rule_matched:
            matched_rule_id = rule_matched[0]
        global_rule = automation_rule_ids.filtered(lambda r: r.rule_type == 'all' and not r.is_global_rule)
        if global_rule:
            rule_matched.append(global_rule)
            if not matched_rule_id:
                matched_rule_id = global_rule
        if matched_rule_id:
            val_dict.update({
                'rule_id': matched_rule_id.id,
            })
            for action in matched_rule_id.rule_action_line:
                if action.action_type == 'tag':
                    val_dict.update({
                        'tag_id': action.tag_id.id
                    })
                elif action.action_type == 'dimension':
                    val_dict.update({
                        'length': action.length,
                        'width': action.width,
                        'height': action.height,
                    })
                elif action.action_type == 'carrier':
                    val_dict.update({
                        'carrier_id': action.service_id and action.service_id.id or False,
                        'ship_package_id': action.package_id and action.package_id.id or False,
                    })
                elif action.action_type == 'insure':
                    val_dict.update({
                        'insure_package_type': action.insure_package_type,
                    })
                elif action.action_type == 'weight':
                    val_dict.update({
                        'shipping_weight': action.shipping_weight_lb,
                        'shipping_weight_oz': action.shipping_weight_oz,
                    })
                elif action.action_type == 'activity':
                    val_dict.update({
                        'activity': {
                            'summary': action.msg,
                            'note': action.msg,
                            'user_id': action.responsible_id.id,
                            'date_deadline': fields.Datetime.now(),
                            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                        }
                    })

        self.write({'rule_id': matched_rule_id and matched_rule_id.id or False,
                    'rule_message': "Rules Matched are:\n%s \nApplied Rule is: %s" % (", ".join(
                        [r.name for r in rule_matched]), matched_rule_id.name) if len(rule_matched) > 1 else False
                    })
        logger.info("Rule!!!!!! %s" % val_dict)
        return val_dict

    def get_shipping_rates(self, rule_val):
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
        for sale_id in self:
            partner_id = sale_id.warehouse_id.partner_id
            to_partner_id = sale_id.partner_shipping_id
            log_xml = prod_environment = False
            delivery_nature = 'domestic'
            service_id = False
            if rule_val.get('carrier_id'):
                service_id = delivery_obj.browse(rule_val.get('carrier_id'))
                if service_id.international:
                    delivery_nature = 'international'
                log_xml = service_id.log_xml
                prod_environment = service_id.prod_environment
            srm = ShipstationRequest(log_xml, prod_environment, url, token)
            check_result = srm.check_required_value(to_partner_id, delivery_nature,
                                                    partner_id, order=sale_id)
            if check_result:
                raise UserError(check_result)
            if rule_val.get('shipping_weight'):
                shipping_weight = rule_val.get('shipping_weight')
                units = "pounds"
            elif rule_val.get('shipping_weight_oz'):
                shipping_weight = rule_val.get('shipping_weight_oz')
                units = "ounces"
            else:
                shipping_weight = sale_id.order_weight or sale_id.weight_oz
                units = "pounds" if sale_id.order_weight else "ounces"
            payload = {
                "fromPostalCode": partner_id.zip.replace(" ", "") if partner_id.zip else '',
                "toState": to_partner_id.state_id.code or '',
                "toCountry": to_partner_id.country_id.code or '',
                "toPostalCode": to_partner_id.zip.replace(" ", "") if to_partner_id.zip else '',
                "toCity": to_partner_id.city or '',
                "weight": {
                    "value": shipping_weight,
                    "units": units
                },
                "dimensions": {
                    "units": "inches",
                    "length": rule_val.get('length', 0),
                    "width": rule_val.get('width', 0),
                    "height": rule_val.get('height', 0)
                },
                "confirmation": 'none',
                "residential": False
            }
            if service_id:
                ship_carrier_id = service_id.shipstation_carrier_id
            else:
                ship_carrier_id = self.env['shipstation.carrier'].browse(rule_val.get('shipstation_carrier_id'))
            payload.update({"carrierCode": ship_carrier_id.code})
            if service_id:
                payload.update({"serviceCode": service_id.shipstation_service_code})

            if rule_val.get('ship_package_id'):
                ship_package_id = self.env['shipstation.package'].browse(rule_val.get('ship_package_id'))
                payload.update({"packageCode": ship_package_id.code})
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
                    _("No applicable services were available for the configured Order %s!" % sale_id.name))
            logger.info("Response!!!!!! %s" % response_data)
            if api_call.status_code not in (200, 201):
                raise ValidationError(_(response_data.get('ExceptionMessage')))
            data = srm.rate_response_data(response_data, api_config_obj, ship_carrier_id)
            return {'quote_lines': data.get('line_ids'),
                    'carrier_id': data.get('min_service').get('service_id', False),
                    'carrier_price': data.get('min_service').get('rate', 0),
                    'ship_package_id': data.get('min_service').get('package_id', False),
                    }
        return False

    def action_confirm(self):
        # if len(self.order_line.filtered(lambda l: l.product_id.type != 'service')) == 1:
        rule_dict = self.apply_automation_rule()
        if 'carrier_id' not in rule_dict:
            api_config_obj = self.env['shipstation.config'].search(
                [('active', '=', True)])
            default_carrier_id = api_config_obj.default_carrier_id
            rule_dict.update({'shipstation_carrier_id': default_carrier_id.id,
                              'carrier_id': False, })
        if not rule_dict.get('shipping_weight'):
            rule_dict.update({'shipping_weight': self.order_weight})
        if not rule_dict.get('shipping_weight_oz'):
            rule_dict.update({'shipping_weight_oz': self.weight_oz})
        logger.info("Rule values!!!!!! %s" % rule_dict)
        rates_dict = self.with_context(api_call=True).get_shipping_rates(rule_dict)
        if rates_dict:
            rule_dict.update(rates_dict)
        res = super(SaleOrder, self).action_confirm()
        if self.picking_ids:
            pickings = self.picking_ids.filtered(
                lambda x: x.state == 'confirmed' or (x.state in ['waiting', 'assigned']))
            if rule_dict:
                if rule_dict.get('activity'):
                    print("rule_dict", rule_dict)
                    rule_dict.get('activity').update({
                        'res_id': pickings.id,
                        'res_model_id': self.env['ir.model']._get(pickings._name).id
                    })
                    self.env['mail.activity'].sudo().create(rule_dict.pop('activity'))
                pickings.with_context(api_call=True).write(rule_dict)
        return res

    def _remove_service_line(self):
        self.env['sale.order.line'].search(
            [('order_id', 'in', self.ids), ('is_delivery', '=', True), ('is_service', '=', True)]).unlink()

    def set_price(self):
        # Remove delivery products from the sales order
        self._remove_service_line()
        for order in self:
            order_lines = order.order_line.filtered(
                lambda l: not l.is_delivery and l.display_type not in [
                    'line_section', 'line_note'])
            shipping_price = order_lines and sum(
                [line.product_id.multiple_price
                 * line.product_uom_qty for line in order_lines]) + order.service_price or 0
            line_id = order._create_delivery_line(order.requested_service_id, shipping_price)
            line_id.update({'is_service': True})
        return True

    def _remove_delivery_line(self):
        self.env['sale.order.line'].search(
            [('order_id', 'in', self.ids), ('is_delivery', '=', True), ('is_service', '=', False)]).unlink()

    @api.depends('order_line.price_total')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            amount_untaxed = amount_tax = ship_cost = 0.0
        for line in order.order_line:
            if line.is_delivery:
                ship_cost += line.price_subtotal or 0.0
            else:
                amount_untaxed += line.price_subtotal
            amount_tax += line.price_tax
        order.update({
            'shipping_cost': ship_cost,
            'amount_untaxed': amount_untaxed,
            'amount_tax': amount_tax,
            'amount_total': amount_untaxed + amount_tax,
        })

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_service = fields.Boolean('Is Service')


class OrderTag(models.Model):
    _name = "order.tag"
    _description = "Order Tags"

    name = fields.Char("Name")

    _sql_constraints = [('name_uniq', 'unique(name)', 'Tag name must be unique !')]


class OrderService(models.Model):
    _name = "order.service"
    _description = "Order Service"

    def _get_product_id(self):
        return self.env.ref('delivery_shipstation.product_product_sale_requested_service').id

    name = fields.Char("Name")
    price = fields.Float("Price")
    active = fields.Boolean("Active", default=True)
    product_id = fields.Many2one("product.product", string="Product", default=_get_product_id)
    invoice_policy = fields.Selection([('estimated', 'Estimated cost'),
                                       ('real', 'Real cost')
                                       ], string='Invoicing Policy', default='estimated', required=True,
                                      help="Estimated Cost: the customer will be invoiced the estimated cost of the shipping.\nReal Cost: the customer will be invoiced the real cost of the shipping, the cost of the shipping will be updated on the SO after the delivery.")
    free_over = fields.Boolean('Free if order amount is above',
                               help="If the order total amount (shipping excluded) is above or equal to this value, the customer benefits from a free shipping",
                               default=False)

    _sql_constraints = [('name_uniq', 'unique(name)', 'Service name must be unique !')]
