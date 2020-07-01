# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################
from odoo import models, fields, api, _
import logging

logger = logging.getLogger('Order Log')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends('order_line')
    def _compute_order_weight(self):
        for order in self:
            order.order_quantity = int(
                sum(order.order_line.filtered(lambda l: not l.is_delivery).mapped('product_uom_qty')))
            line_with_weight = order.order_line.filtered(lambda line: line.product_id.weight > 0.00)
            order.order_weight = sum([(line.product_qty * line.product_id.weight) for line in line_with_weight])
            # order.order_weight = sum(line.product_id.weight for line in order.order_line)

    rule_id = fields.Many2one("automation.rule", string="Rule", copy=False)
    order_weight = fields.Float(compute='_compute_order_weight', string='Order Weight')
    order_quantity = fields.Integer(compute='_compute_order_weight', string='Order Quantity')
    rule_message = fields.Text(readonly=True, copy=False)
    requested_service_id = fields.Many2one("order.service", string="Service")
    tag_id = fields.Many2one("order.tag", string="Tags")

    def apply_automation_rule(self, picking=None):
        automation_rule_ids = self.env['automation.rule'].search([], order="sequence")
        val_dict = {}
        matched_rule_id = False
        rule_matched = []
        product_id = self.order_line.filtered(lambda l: l.product_id.type != 'service').mapped('product_id')
        for rule in automation_rule_ids.filtered(lambda r: r.rule_type == 'match'):
            if not rule_matched:
                matched_rule_id = rule
            for line in rule.rule_line:
                str_c = ''
                operator = str(line.operator_type_id.operator) + ' '
                if line.category_type == 'qty':
                    str_c = str(self.order_quantity)
                    operator += str(line.value)
                elif line.category_type == 'wgt':
                    str_c = str(self.order_weight)
                    operator += str(line.total_weight)
                elif line.category_type == 'val':
                    str_c = str(self.amount_untaxed)
                    operator += str(line.value)
                elif line.category_type == 'product':
                    str_c = str(product_id.id)
                    operator += str(line.product_ids.ids)
                elif line.category_type == 'req_service':
                    str_c = str(self.requested_service_id.id)
                    operator += str(line.requested_service_id.ids)
                elif line.category_type == 'tag':
                    str_c = str(self.tag_id.id)
                    operator += str(line.tag_ids.ids)
                elif line.category_type == 'country':
                    str_c = str(self.partner_id.country_id.id)
                    operator += str(line.country_ids.ids)
                elif line.category_type == 'inventory':
                    str_c = str(product_id.qty_available)
                    operator += str(line.value)
                elif line.category_type == 'length':
                    str_c = str(product_id.length)
                    operator += str(line.value)
                elif line.category_type == 'width':
                    str_c = str(product_id.width)
                    operator += str(line.value)
                elif line.category_type == 'height':
                    str_c = str(product_id.height)
                    operator += str(line.value)
                if str_c:
                    str_c += ' ' + operator
                    if not eval(str_c):
                        matched_rule_id = False
                        break

            if matched_rule_id:
                rule_matched.append(rule)
                # break
        if rule_matched:
            matched_rule_id = rule_matched[0]
        global_rule = automation_rule_ids.filtered(lambda r: r.rule_type == 'all')
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
                elif action.action_type == 'activity' and picking:
                    activity_type_id = self.env.ref('mail.mail_activity_data_todo').id
                    activity = self.env['mail.activity'].create({
                        'res_id': picking.id,
                        'res_model_id': self.env['ir.model']._get(picking._name).id,
                        'summary': action.msg,
                        'note': action.msg,
                        'date_deadline': fields.Datetime.now(),
                        'activity_type_id': activity_type_id,
                        'user_id': self.env.user.id,
                    })
                    # activity._onchange_activity_type_id()
                    # pass
            self.write({'rule_id': matched_rule_id.id,
                        'rule_message': "Rules Matched are:\n%s \nApplied Rule is: %s" % (", ".join(
                            [r.name for r in rule_matched]), matched_rule_id.name) if len(rule_matched) > 1 else False
                        })
        else:
            self.rule_id = False
        logger.info("Rule!!!!!! %s" % val_dict)
        return val_dict

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        if self.picking_ids and len(self.order_line.filtered(lambda l: l.product_id.type != 'service')) == 1:
            pickings = self.picking_ids.filtered(
                lambda x: x.state == 'confirmed' or (x.state in ['waiting', 'assigned']))
            rule_dict = self.apply_automation_rule(picking=pickings)
            if 'carrier_id' not in rule_dict:
                api_config_obj = self.env['shipstation.config'].search(
                    [('active', '=', True)])
                default_carrier_id = api_config_obj.default_carrier_id
                rule_dict.update({'shipstation_carrier_id': default_carrier_id.id,
                                  'carrier_id': False, })
            if rule_dict:
                pickings.with_context(api_call=True).write(rule_dict)

            # else:
            #     pickings.write({'shipstation_carrier_id': default_carrier_id.id,
            #                     'carrier_id': False, })
            pickings.with_context(api_call=True).get_shipping_rates()
        return res


class OrderTag(models.Model):
    _name = "order.tag"
    _description = "Order Tags"

    name = fields.Char("Name")

    _sql_constraints = [('name_uniq', 'unique(name)', 'Tag name must be unique !')]


class OrderService(models.Model):
    _name = "order.service"
    _description = "Order Service"

    name = fields.Char("Name")
    price = fields.Float("Price")

    _sql_constraints = [('name_uniq', 'unique(name)', 'Service name must be unique !')]
