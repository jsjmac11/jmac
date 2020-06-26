# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

categ_type = [('country', 'Country'),
              ('product', 'Item SKU'),
              ('qty', 'Total Quantity'),
              ('val', 'Order Total'),
              ('wgt', 'Total Weight'),
              ('req_service', 'Requested Services'),
              ('inventory', 'Item Inventory'),
              ('length', 'Item Length'),
              ('width', 'Item Width'),
              ('height', 'Item Height'),
              ('tag', 'Order Tags')]


class AutomationRule(models.Model):
    _name = 'automation.rule'
    _description = "Automation Rule for Carrier"
    _order = "sequence"

    name = fields.Char("Rule Name")
    rule_type = fields.Selection(
        [('all', 'Apply these actions to EVERY order that is imported'),
         ('match', 'Only apply these actions to orders that match specific criteria')],
        default='all', copy=False)
    active = fields.Boolean(string="Active", default=True)
    rule_line = fields.One2many("automation.rule.line", 'rule_id', string="Criteria")
    sequence = fields.Integer("Sequence")
    rule_action_line = fields.One2many("automation.rule.action", 'rule_id', string="Action")

    @api.constrains('rule_type', 'active')
    def _validate_rule_type(self):
        rule_id = self.env['automation.rule'].search([('rule_type', '=', 'all')])
        if len(rule_id) > 1:
            raise ValidationError(_("For rule type 'every order' already exists please inactive old rule first!"))


class AutomationRuleLine(models.Model):
    _name = 'automation.rule.line'
    _description = "Automation Rule Line for Carrier"

    rule_id = fields.Many2one("automation.rule", string="Rule")
    category_type = fields.Selection(categ_type, default='qty', copy=False, string="Type")
    operator_type_id = fields.Many2one('operator.type', string='Operator')
    value = fields.Float(string="Value")
    weight_lb = fields.Float("Weight(lb)")
    product_ids = fields.Many2many("product.product", string="Item SKU")
    country_ids = fields.Many2many("res.country", string="Country")
    # service_type = fields.Selection([('free', 'Free Shipping'),
    #                                  ('standard', 'Standard Shipping'),
    #                                  ('expedited', 'Expedited Shipping'),
    #                                  ('fast', 'Need It Fast')], string="Service")
    requested_service_id = fields.Many2one("order.service", string="Service")
    tag_ids = fields.Many2many("order.tag", string="Tags")


class OperatorType(models.Model):
    _name = 'operator.type'
    _description = 'Dynamic Operator'

    name = fields.Char("Name")
    operator = fields.Char('operator')
    sequence = fields.Char("Sequence")
    field_id = fields.Many2many('ir.model.fields', string='Field')
    category_type = fields.Selection(categ_type, default='qty', copy=False, string="Type")

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100,
                     name_get_uid=None):
        # operator = super(OperatorType, self)._name_search(
        #     name, args, operator=operator, limit=limit,
        #     name_get_uid=name_get_uid)
        ctx = self._context.copy()
        if ctx.get('category_type', False) in ('product', 'country', 'tag', 'req_service'):
            domain = [('category_type', '=', ctx.get('category_type'))]
        else:
            domain = [('category_type', '=', False)]
        res = self.search(domain + args, limit=limit)
        return res.name_get()


class AutomationRuleAction(models.Model):
    _name = 'automation.rule.action'
    _description = "Automation Rule Action for Carrier"

    rule_id = fields.Many2one("automation.rule", string="RUle")
    action_type = fields.Selection(
        [('tag', 'Add a Tag...'),
         ('dimension', 'Set Package Dimension...'),
         ('carrier', 'Set Carrier/Service/Package...'),
         ('insure', 'Insure the Package...'),
         ('weight', 'Set the Total Order Weight...'),
         ('activity', 'Schedule activity')],
        copy=False, string="Action")
    service_id = fields.Many2one("delivery.carrier", string="Service")
    package_id = fields.Many2one("shipstation.package", string="Package")
    insure_package_type = fields.Selection(
        [('shipsurance', 'Shipsurance'),
         ('carrier', 'Carrier'),
         ('provider', 'Other/External')],
        copy=False, string="Insure Type")
    length = fields.Integer('L (in)', copy=False)
    width = fields.Integer('W (in)', copy=False)
    height = fields.Integer('H (in)', copy=False)
    shipping_weight_lb = fields.Float("Weight(lb)")
    shipping_weight_oz = fields.Float("Weight(oz)")
    tag_id = fields.Many2one("order.tag", string="Tag")
    msg = fields.Char("Activity")
