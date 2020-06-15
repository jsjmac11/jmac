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
	service_id = fields.Many2one("delivery.carrier", string="Service")
	package_id = fields.Many2one("shipstation.package", string="Package")
	rule_line = fields.One2many("automation.rule.line", 'rule_id', string="Criteria ")



class AutomationRuleLine(models.Model):
	_name = 'automation.rule.line'
	_description = "Automation Rule Line for Carrier"

	rule_id = fields.Many2one("automation.rule", string="Rule")
	# category_type = fields.Selection(
	# 	[('qty', 'Total Quantity'),
	# 	('val', 'Order Total'),
	# 	('wgt', 'Total Weight')],
	# 	default='qty', copy=False, string="Type")
	fields_option_id = fields.Many2one('ir.model.fields',string='Options')
	operator_type_id = fields.Many2one('operator.type',string='Operator')
	# operator_type = fields.Selection(
	# 	[('eq', 'Is Equal To...'),
	# 	('uneq', 'Is Not Equal To...'),
	# 	('gt', 'Is Greater Than...'),
	# 	('gteq', 'Is Greater Than or Equal To...'),
	# 	('lt', 'Is Less Than...'),
	# 	('lteq', 'Is Less Than or Equal To...')],
	# 	default='eq', copy=False, string="Operator")
	value = fields.Float(string="Value")
	# value = fields.Char(string="Value")


class OperatorType(models.Model):
	_name = 'operator.type'
	_description = 'Dynamic Operator'


	name = fields.Char("Name")
	code = fields.Char('Code')
	operator = fields.Char('operator')
	sequence = fields.Char("Sequence")
	field_id = fields.Many2many('ir.model.fields',string='Field')
		