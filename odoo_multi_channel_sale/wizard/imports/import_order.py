# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models

class ImportOrder(models.TransientModel):
	_name = 'import.orders'
	_description = 'Import Order'
	_inherit = 'import.operation'

	source = fields.Selection(
		selection=[
			('all','All'),
			('order_ids','Order ID(s)'),
		],
		required = True,
		default  = 'all'
	)

	order_ids = fields.Text('Order ID(s)')
