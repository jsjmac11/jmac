# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models


class ChannelAccountMappings(models.Model):
	_name        = 'channel.account.mappings'
	_inherit     = 'channel.mappings'
	_description = 'Tax Mapping'

	store_tax_value_id = fields.Char('Store Tax Value',required=True)
	odoo_tax_id        = fields.Integer('Odoo Tax ID',required=True)
	tax_name           = fields.Many2one('account.tax','Odoo Tax Name',required=True)
	include_in_price   = fields.Boolean('Include in price')
	tax_type           = fields.Selection(
		selection = [('fixed','Fixed'),('percent','Percentage')],
		string    = 'Tax Type',
		default   = 'percent',
		required  = True,
	)


	@api.onchange('tax_name')
	def change_odoo_id(self):
		self.odoo_tax_id = self.tax_name.id

	def _compute_name(self):
		for record in self:
			record.name = record.tax_name.name if record.tax_name else 'Deleted'
