# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models

class ExportProduct(models.TransientModel):
	_name = 'export.products'
	_description = 'Export Products'
	_inherit = 'export.operation'

	product_ids = fields.Many2many(
		comodel_name = 'product.product',
		string       = 'Product(s)'
	)
	sku_sequence_id = fields.Many2one(
		related = 'channel_id.sku_sequence_id',
		string  = 'SKU Sequence'
	)

	def export_odoo_products(self):
		if hasattr(self, 'export_%s_products' % self.channel_id.channel):
			return getattr(self, 'export_%s_products' % self.channel_id.channel)()

	def update_odoo_products(self):
		if hasattr(self, 'update_%s_products' % self.channel_id.channel):
			return getattr(self, 'update_%s_products' % self.channel_id.channel)()

	@api.model
	def default_get(self,fields):
		res = super(ExportProduct,self).default_get(fields)
		if not res.get('product_ids') and self._context.get('active_model')=='product.product':
			res['product_ids'] = self._context.get('active_ids')
		return res
