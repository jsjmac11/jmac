# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models


class ChannelAccountJournalMappings(models.Model):
	_name        = 'channel.account.journal.mappings'
	_inherit     = 'channel.mappings'
	_description = 'Account Journal Mapping'

	store_journal_name = fields.Char('Store Payment Method',required=True)
	odoo_journal       = fields.Many2one('account.journal','Odoo Journal Name',required=True)
	journal_code       = fields.Char('Journal Code',required=True,related='odoo_journal.code')
	odoo_journal_id    = fields.Integer('Odoo Journal ID',required=True)


	@api.onchange('odoo_journal')
	def change_odoo_id(self):
		self.odoo_journal_id = self.odoo_journal.id

	def _compute_name(self):
		for record in self:
			record.name = record.store_journal_name if record.store_journal_name else 'Deleted'
