# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import fields,models,exceptions

from ...ApiTransaction import Transaction


class ImportOperation(models.TransientModel):
	_name  = 'import.operation'
	_description = 'Import Operation'
	_inherit = 'channel.operation'


	object = fields.Selection(selection=[
		('product.template', 'Product'),
		('sale.order', 'Order'),
		('product.category', 'Category'),
		('res.partner', 'Customer'),
		('delivery.carrier', 'Shipping Method'),
	])

	operation = fields.Selection(
		selection = [
			('import',"Import"),
			('update','Update')
		],
		default ='import',
		required = True
	)

	def import_button(self):
		kw = {'object':self.object}
		if hasattr(self,f'{self.channel}_get_filter'):
			kw.update(getattr(self,f'{self.channel}_get_filter')())
			return self.import_with_filter(**kw)
		else:
			raise exceptions.UserError('Filters for this channel not implemented properly')

	def import_with_filter(self,**kw):
		return Transaction(channel=self.channel_id).import_data(**kw)
