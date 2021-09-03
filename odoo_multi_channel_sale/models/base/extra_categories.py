# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models


class ExtraCategories(models.Model):
	_name        = 'extra.categories'
	_description = 'Extra Categories'

	@api.model
	def get_category_list(self):
		mapping_ids = self.env['channel.category.mappings'].search(
			[('channel_id','=',self.instance_id.id)]
		)
		if mapping_ids:
			return [i.odoo_category_id for i in mapping_ids]
		return []

	@api.depends('instance_id')
	def _compute_extra_categories_domain(self):
		for record in self:
			record.extra_category_domain_ids = [(6,0,record.get_category_list())]


	instance_id = fields.Many2one('multi.channel.sale','Instance')
	product_id  = fields.Many2one('product.template','Template')
	category_id = fields.Many2one('product.category','Internal Category')

	extra_category_ids = fields.Many2many(
		comodel_name = 'product.category',
		string       = 'Extra Categories',
		domain       = '[("id","in",extra_category_domain_ids)]',
	)

	extra_category_domain_ids = fields.Many2many(
		comodel_name = 'product.category',
		relation     = 'extra_categ_ref',
		column1      = 'product_categ_ref',
		column2      = 'table_ref',
		string       = 'Category Domain',
		compute      = '_compute_extra_categories_domain',
	)


	@api.onchange('instance_id')
	def change_domain(self):
		return {
			'domain': {
				'extra_category_ids': [
					('id','in',self.get_category_list())
				]
			}
		}
