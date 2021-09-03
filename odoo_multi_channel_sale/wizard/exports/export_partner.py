# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models

class ExportPartner(models.TransientModel):
	_name = 'export.partners'
	_description = 'Export Partner'
	_inherit = 'export.operation'

	partner_ids = fields.Many2many(
		comodel_name = 'res.partner',
		string       = 'Partner'
	)
