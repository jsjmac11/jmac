# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models

class ImportCategory(models.TransientModel):
	_name = 'import.categories'
	_description = 'Import Category'
	_inherit = 'import.operation'

	category_ids    = fields.Text('Categories ID(s)')
	parent_categ_id = fields.Many2one('channel.category.mappings','Parent Category')
