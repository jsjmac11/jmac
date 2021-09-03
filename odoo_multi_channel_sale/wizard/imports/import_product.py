# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models

class ImportProduct(models.TransientModel):
	_name = 'import.products'
	_description = 'Import Product'
	_inherit = 'import.operation'

	product_ids = fields.Text('Product ID(s)')
	source      = fields.Selection(
		selection=[
			('all','All'),
			('product_ids','Product ID(s)'),
		],
		required = True,
		default  = 'all'
	)
