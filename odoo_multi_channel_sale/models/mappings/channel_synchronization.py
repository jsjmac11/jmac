# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models


class ChannelSynchronization(models.Model):
	_name        = 'channel.synchronization'
	_description = 'Synchronization History'
	_inherit     = 'channel.mappings'
	_rec_name    = 'action_on'

	ecomstore_refrence = fields.Char('Store Ref.')
	odoo_id            = fields.Text('Odoo ID')
	summary            = fields.Text('Summary',required=True)

	status = fields.Selection(
		selection = [
			('success','Success'),
			('error','Error')
		],
		string   = 'Status',
		required = True
	)

	action_on =  fields.Selection(
		selection = [
			('variant','Variant'),
			('template','Template'),
			('product','Product'),
			('category','Category'),
			('order','Order'),
			('customer','Customer'),
			('shipping','Shipping'),
			('attribute','Attribute'),
			('attribute_value','Attribute Value')
		],
		string   = 'Action On',
		required = True
	)

	action_type = fields.Selection(
		selection = [
			('import','Import'),
			('export','Export')
		],
		string = 'Action Type'
	)


	@api.model
	def cron_clear_history(self):
		for rec in self.search([('status','=','success')]):
			rec.unlink()
