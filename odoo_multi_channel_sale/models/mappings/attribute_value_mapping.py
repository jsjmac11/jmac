# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models


class ChannelAttributeValueMappings(models.Model):
	_name        = 'channel.attribute.value.mappings'
	_inherit     = 'channel.mappings'
	_description = 'Attribute Value Mapping'

	store_attribute_value_id   = fields.Char('Store Attribute Value ID',required=True)
	store_attribute_value_name = fields.Char('Store Attribute Value Name' )
	attribute_value_name       = fields.Many2one(
		comodel_name = 'product.attribute.value',
		string       = 'Odoo Attribute Value Name',
		required     = True
	)
	odoo_attribute_value_id = fields.Integer('Odoo Value ID',required=True)


	@api.onchange('attribute_value_name')
	def change_odoo_id(self):
		self.odoo_attribute_value_id = self.attribute_value_name.id
		
	def _compute_name(self):
		for record in self:
			record.name = record.attribute_value_name.name if record.attribute_value_name else 'Deleted'
