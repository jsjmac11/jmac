# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################
from odoo import models, fields, api


class AutomationRule(models.Model):
    _name = 'automation.rule'
    _description = "Automation Rule for Carrier"
    _order = "sequence"

    name = fields.Char("Rule Name")
    rule_type = fields.Selection(
        [('all', 'Apply these actions to EVERY order that is imported'),
         ('match', 'Only apply these actions to orders that match specific criteria')],
        default='all', copy=False)
    # category_type = fields.Selection(
    # 	[('qty', 'Total Quantity'),
    # 	('val', 'Order Total'),
    # 	('wgt', 'Total Weight')],
    # 	default='qty', copy=False, string="Type")
    # operator_type = fields.Selection(
    # 	[('eq', 'Is Equal To...'),
    # 	('uneq', 'Is Not Equal To...'),
    # 	('gt', 'Is Greater Than...'),
    # 	('gteq', 'Is Greater Than or Equal To...'),
    # 	('lt', 'Is Less Than...'),
    # 	('lteq', 'Is Less Than or Equal To...')],
    # 	default='eq', copy=False, string="Operator")
    # value = fields.Float(string="Value")
    active = fields.Boolean(string="Active", default=True)
    rule_line = fields.One2many("automation.rule.line", 'rule_id', string="Criteria")
    sequence = fields.Integer("Sequence")
    rule_action_line = fields.One2many("automation.rule.action", 'rule_id', string="Action")


class AutomationRuleLine(models.Model):
    _name = 'automation.rule.line'
    _description = "Automation Rule Line for Carrier"

    rule_id = fields.Many2one("automation.rule", string="Rule")
    category_type = fields.Selection(
        [('qty', 'Total Quantity'),
         ('val', 'Order Total'),
         ('wgt', 'Total Weight')],
        default='qty', copy=False, string="Type")
    # fields_option_id = fields.Many2one('ir.model.fields',string='Options')
    operator_type_id = fields.Many2one('operator.type', string='Operator')
    # operator_type = fields.Selection(
    # 	[('eq', 'Is Equal To...'),
    # 	('uneq', 'Is Not Equal To...'),
    # 	('gt', 'Is Greater Than...'),
    # 	('gteq', 'Is Greater Than or Equal To...'),
    # 	('lt', 'Is Less Than...'),
    # 	('lteq', 'Is Less Than or Equal To...')],
    # 	default='eq', copy=False, string="Operator")
    value = fields.Float(string="Value")


class OperatorType(models.Model):
    _name = 'operator.type'
    _description = 'Dynamic Operator'

    name = fields.Char("Name")
    operator = fields.Char('operator')
    sequence = fields.Char("Sequence")
    field_id = fields.Many2many('ir.model.fields', string='Field')
    category_type = fields.Selection(
        [('qty', 'Total Quantity'),
         ('val', 'Order Total'),
         ('wgt', 'Total Weight')],
        default='qty', copy=False, string="Type")


class AutomationRuleAction(models.Model):
    _name = 'automation.rule.action'
    _description = "Automation Rule Action for Carrier"

    rule_id = fields.Many2one("automation.rule", string="RUle")
    action_type = fields.Selection(
        [('tag', 'Add a Tag...'),
         ('dimension', 'Set Package Dimension...'),
         ('carrier', 'Set Carrier/Service/Package...'),
         ('insure', 'Insure the Package...'),
         ('weight', 'Set the Total Order Weight...')],
        copy=False, string="Add a Tag")
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
    tag_id = fields.Char("Tag")
