# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models

class ExportOrder(models.TransientModel):
	_name = 'export.orders'
	_description = 'Export Order'
	_inherit = 'export.operation'

	order_ids = fields.Many2many(
		comodel_name = 'sale.order',
		string       = 'Sale orders'
	)

	@api.model
	def _get_order_domain(self):
		return []

	@api.model
	def default_get(self,fields):
		res = super(ExportOrder,self).default_get(fields)
		if not res.get('order_ids') and self._context.get('active_model')=='sale.order':
			res['order_ids'] = self._context.get('active_ids')
		return res
