# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models

class ImportTemplate(models.TransientModel):
	_name = 'import.templates'
	_description = 'Import Template'
	_inherit = 'import.operation'

	product_tmpl_ids = fields.Text('Product Template ID(s)')
	source           = fields.Selection(
		selection=[
			('all','All'),
			('product_tmpl_ids','Product ID(s)'),
		],
		required = True,
		default  = 'all'
	)
