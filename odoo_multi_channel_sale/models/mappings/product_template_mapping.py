# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models


class ChannelTemplateMappings(models.Model):
	_name        = 'channel.template.mappings'
	_inherit     = 'channel.mappings'
	_description = 'Product Template Mapping'

	store_product_id = fields.Char('Store Product ID',required=True)
	template_name    = fields.Many2one('product.template','Product Template')
	odoo_template_id = fields.Char('Odoo Template ID',required=True)
	default_code     = fields.Char('Default code/SKU')
	barcode          = fields.Char('Barcode/EAN/UPC or ISBN')

	# _sql_constraints = [
	# 	(
	# 		'channel_store_store_product_id_uniq',
	# 		'unique(channel_id,store_product_id)',
	# 		'Store Product ID must be unique for channel product mapping!'
	# 	),
	# 	(
	# 		'channel_odoo_odoo_template_id_uniq',
	# 		'unique(channel_id,odoo_template_id)',
	# 		'Odoo Template ID must be unique for channel template mapping!'
	# 	)
	# ]


	def unlink(self):
		for record in self:
			if record.store_product_id:
				match = record.channel_id.match_product_feeds(record.store_product_id)
				if match:
					match.unlink()
		channel_ids = self.mapped('channel_id.id')
		product_ids = list(map(int, self.mapped('odoo_template_id')))
		mappings = self.env['channel.product.mappings'].search(
			[
				('channel_id','in',channel_ids),
				('odoo_template_id','in',product_ids)
			]
		)
		mappings.unlink()
		return super(ChannelTemplateMappings,self).unlink()

	@api.onchange('template_name')
	def change_odoo_id(self):
		self.odoo_template_id = self.template_name.id

	def _compute_name(self):
		for record in self:
			record.name = record.template_name.name if record.template_name else 'Deleted/Undefined'
