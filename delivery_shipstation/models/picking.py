# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################
from odoo import models, fields, api
import requests
from requests.auth import HTTPBasicAuth
import base64
import json

class StockPicking(models.Model):
	_inherit = 'stock.picking'

	shipstation_carrier_id = fields.Many2one('shipstation.carrier', 'Shipstation Carrier')
	shipping_provider_id = fields.Selection([('shipstation','Shipstation')],default='shipstation')
	shipping_rate = fields.Float('Shipping Rate', copy=False)

	@api.onchange('carrier_id')
	def onchange_carrier_id(self):
		"""
		Get the Server URL based on server selected.
		:return:
		"""
		if self.carrier_id:
			self.shipping_rate = 0.0

	def _convert_to_lbs(self, weight_in_kg):
		# Return weight in LBS as prefered by eShipper
		return round(weight_in_kg * 2.20462, 3)

	def get_shipping_rates(self):
		self.ensure_one()
		partner_id = self.sale_id.warehouse_id.partner_id
		to_partner_id = self.partner_id
		total_weight = self._convert_to_lbs(self.shipping_weight)
		carrier_id = self.carrier_id
		payload = {
		  "carrierCode": carrier_id.shipstation_carrier_code,
		  "serviceCode": carrier_id.shipstation_service_code,
		  "packageCode": carrier_id.shipstation_default_packaging_id.shipper_package_code,
		  "fromPostalCode": partner_id.zip.replace(" ", "") if partner_id.zip else '',
		  "toState": to_partner_id.state_id.code or '',
		  "toCountry": to_partner_id.country_id.code or '',
		  "toPostalCode": to_partner_id.zip.replace(" ", "") if to_partner_id.zip else '',
		  "toCity": to_partner_id.city or '',
		  "weight": {
				    "value": total_weight,
				    "units": "pounds"
					  },
		  "dimensions": {
					    "units": "inches",
					    "length": carrier_id.shipstation_default_packaging_id.length,
					    "width": carrier_id.shipstation_default_packaging_id.width,
					    "height": carrier_id.shipstation_default_packaging_id.height
					  	},
		  "confirmation": "delivery",
		  "residential": False
		}
		api_config_obj = self.env['shipstation.config'].search(
		    [('active', '=', True)])
		url = api_config_obj.server_url + '/shipments/getrates'
		headers = {
					'Host': 'ssapi.shipstation.com',
					'Content-Type': 'application/json',
					'Authorization' : 'Basic %s' % api_config_obj.auth_token()
					}
		api_call = requests.request("POST", url, headers=headers, data = json.dumps(payload))
		response_data = json.loads(api_call.text)
		shipping_rate = 0.0
		for data in response_data:
			shipping_rate += data.get('shipmentCost')
			shipping_rate += data.get('otherCost')
		self.carrier_price = shipping_rate
		return True
