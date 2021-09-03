# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models


class ChannelShippingMappings(models.Model):
	_name        = 'channel.shipping.mappings'
	_inherit     = 'channel.mappings'
	_description = 'Shipping Mapping'
	_rec_name    = 'shipping_service'

	shipping_service       = fields.Char("Store Shipping Service")
	shipping_service_id    = fields.Char("Shipping Serivce ID")
	odoo_shipping_carrier  = fields.Many2one('delivery.carrier','Odoo Shipping Carrier', required=True)
	odoo_carrier_id        = fields.Integer('Odoo Carrier ID')
	international_shipping = fields.Boolean('Is International')


	@api.onchange('odoo_shipping_carrier')
	def change_odoo_id(self):
		self.odoo_carrier_id = self.odoo_shipping_carrier.id

	def _compute_name(self):
		for record in self:
			record.name = record.odoo_shipping_carrier.name if record.odoo_shipping_carrier else 'Deleted'
