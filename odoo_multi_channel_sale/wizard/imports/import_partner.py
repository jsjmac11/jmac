# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models

class ImportPartner(models.TransientModel):
	_name = 'import.partners'
	_description = 'Import Partner'
	_inherit = 'import.operation'

	partner_ids = fields.Text('Partners ID(s)')
