# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models


class ChannelAttributeMappings(models.Model):
	_name        = 'channel.attribute.mappings'
	_inherit     = 'channel.mappings'
	_description = 'Attribute Mapping'

	store_attribute_id   = fields.Char('Store Attribute ID' ,required=True)
	store_attribute_name = fields.Char('Store Attribute Name' )
	attribute_name       = fields.Many2one('product.attribute','Odoo Attribute Name',required=True)
	odoo_attribute_id    = fields.Integer('Odoo Attribute ID',required=True)


	@api.onchange('attribute_name')
	def change_odoo_id(self):
		self.odoo_attribute_id = self.attribute_name.id

	def _compute_name(self):
		for record in self:
			record.name = record.attribute_name.name if record.attribute_name else 'Deleted'
