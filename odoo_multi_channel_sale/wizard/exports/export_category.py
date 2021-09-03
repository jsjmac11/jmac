# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models

class ExportCategory(models.TransientModel):
	_name = 'export.categories'
	_description = 'Export Category'
	_inherit = 'export.operation'

	category_ids = fields.Many2many(
		comodel_name = 'product.category',
		string       = 'Category'
	)

	@api.model
	def default_get(self,fields):
		res = super(ExportCategory,self).default_get(fields)
		if not res.get('category_ids') and self._context.get('active_model')=='product.category':
			res['category_ids'] = self._context.get('active_ids')
		return res
