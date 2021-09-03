# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models


class ChannelPricelistMappings(models.Model):
	_name        = 'channel.pricelist.mappings'
	_inherit     = 'channel.mappings'
	_description = 'Pricelist Mapping'
	_order       = 'need_sync'
	_rec_name    = 'odoo_pricelist_id'


	name       = fields.Char(compute='_compute_name')
	channel_id = fields.Many2one('multi.channel.sale','Instance',required=True)

	store_currency      = fields.Many2one('res.currency','Store Currency',required=True)
	store_currency_code = fields.Char(
		string   = 'Store Currency Code',
		related  = 'store_currency.name',
		required = True
	)

	odoo_pricelist_id = fields.Many2one('product.pricelist','Odoo Pricelist',required=True)
	odoo_currency     = fields.Many2one(
		comodel_name = 'res.currency',
		string       = 'Odoo Currency',
		related      = 'odoo_pricelist_id.currency_id',
		required     = True
	)
	odoo_currency_id = fields.Integer('Odoo Currency ID',required=True)


	@api.onchange('odoo_currency')
	def set_odoo_currency_id(self):
		self.odoo_currency_id = self.odoo_currency.id

	def _compute_name(self):
		for record in self:
			record.name = record.odoo_currency.name if record.odoo_currency else 'Deleted'

	@api.model
	def _needaction_domain_get(self):
		return [('need_sync', '=', 'yes')]

	@api.model
	def ecom_storeUsed(self):
		return self.env['multi.channel.sale'].get_channel()
