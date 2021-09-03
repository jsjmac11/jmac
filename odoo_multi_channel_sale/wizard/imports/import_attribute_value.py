# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models

class ImportAttributeValue(models.TransientModel):
	_name = 'import.attributes.value'
	_description = 'Import Attribute Value'
	_inherit = 'import.operation'

	attribute_value_ids = fields.Text('Attribute Value ID(s)')
