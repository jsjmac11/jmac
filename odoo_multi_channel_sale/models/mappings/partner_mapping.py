# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models


class ChannelOrderMappings(models.Model):
	_name        = 'channel.partner.mappings'
	_inherit     = 'channel.mappings'
	_description = 'Partner Mapping'

	type = fields.Selection(
		selection = [
			('contact','Contact'),
			('invoice','Invoice'),
			('delivery','Delivery'),
		],
		default  = 'contact',
		required = True
	)
	store_customer_id = fields.Char('Store Customer ID',required=True)
	odoo_partner      = fields.Many2one('res.partner','Odoo Partner', required=True)
	odoo_partner_id   = fields.Integer('Odoo Partner ID',required=True)

	_sql_constraints = [
		(
			'channel_store_customer_id_uniq',
			'unique(channel_id, store_customer_id,type)',
			'Store partner ID must be unique for channel partner mapping!'
		),
		# (
		# 	'channel_odoo_partner_id_uniq',
		# 	'unique(channel_id, odoo_partner_id)',
		# 	'Odoo partner ID must be unique for channel partner mapping!'
		# )
	]

	@api.onchange('odoo_partner')
	def change_odoo_id(self):
		self.odoo_partner_id = self.odoo_partner.id

	def _compute_name(self):
		for record in self:
			record.name = record.odoo_partner.name if record.odoo_partner else 'Deleted'
