# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models

class ImportAttribute(models.TransientModel):
	_name = 'import.attributes'
	_description = 'Import Attribute'
	_inherit = 'import.operation'

	attribute_ids = fields.Text('Attribute ID(s)')
