# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models


class ChannelProductMappings(models.Model):
	_name        = 'channel.product.mappings'
	_inherit     = 'channel.mappings'
	_description = 'Product Variant Mapping'

	store_product_id = fields.Char('Store Template ID',required=True)
	store_variant_id = fields.Char('Store Variant ID',required=True,default='No Variants')
	product_name     = fields.Many2one('product.product','Product',required=True)
	erp_product_id   = fields.Integer('Odoo Variant ID',required=True)
	odoo_template_id = fields.Many2one(string='Odoo Template',related='product_name.product_tmpl_id')
	default_code     = fields.Char("Default code/SKU")
	barcode          = fields.Char("Barcode/EAN/UPC or ISBN")
	
	_sql_constraints = [
		(
			'channel_store_store_product_id_store_variant_id_uniq',
			'unique(channel_id,store_product_id,store_variant_id)',
			'Store product + variants must be unique for channel product mapping!'
		)
	]


	@api.onchange('product_name')
	def change_odoo_id(self):
		self.erp_product_id   = self.product_name.id
		self.odoo_template_id = self.product_name.product_tmpl_id.id

	def _compute_name(self):
		for record in self:
			record.name = record.product_name.name if record.product_name.name else 'Deleted'
