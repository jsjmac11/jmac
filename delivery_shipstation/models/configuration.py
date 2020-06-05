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

class ShipstationConfig(models.Model):
	_name = 'shipstation.config'
	_description = "Shipstation Configuration"

	@api.onchange('test_production')
	def onchange_test_production(self):
	    """
	    Get the Server URL based on server selected.
	    :return:
	    """
	    if self.test_production:
	        if self.test_production == 'test':
	            self.server_url = 'https://ssapi.shipstation.com'
	        else:
	            self.server_url = 'https://ssapi.shipstation.com'

	api_key = fields.Char('Username')
	api_secret = fields.Char('Password')
	server_url = fields.Char('Host')
	active= fields.Boolean('Active', default=True)
	test_production = fields.Selection([('test', 'Sandbox'), ('production', 'Production')],
		'Sandbox/Production', default='test')
	default_uom = fields.Selection([
            ('imperial', 'Imperial - LBS & Inch'), 
            ('metric', 'Metric - Kgs & Cm')], default='imperial')

	def auth_token(self):
		key_secret = self.api_key + ':' + self.api_secret
		token = base64.b64encode(bytes(key_secret, 'utf-8')).decode("ascii")
		return token

	def get_carriers(self):
		shipstation_carrier_obj = self.env['shipstation.carrier']
		url = self.server_url + "/carriers"
		payload = {}
		headers = {
					'Host': 'ssapi.shipstation.com',
					'Content-Type': 'application/json',
					'Authorization' : 'Basic %s' % self.auth_token()
					}
		api_call = requests.request("GET", url, headers=headers, data = payload)
		response_data = json.loads(api_call.text)
		for carrier in response_data:
			shipstation_carrier_id = shipstation_carrier_obj.search([('code', '=', carrier.get('code'))])
			if not shipstation_carrier_id:
				shipstation_carrier_id = shipstation_carrier_obj.create({
										'name': carrier.get('name'),
										'code': carrier.get('code')
										})
			self.get_services(shipstation_carrier_id)
			self.get_packages(shipstation_carrier_id)
		return True

	def get_packages(self, shipstation_carrier_id):
		shipstation_carrier_obj = self.env['shipstation.package']
		url = self.server_url + "/carriers/listpackages?carrierCode=%s" % shipstation_carrier_id.code
		payload = {}
		headers = {
					'Host': 'ssapi.shipstation.com',
					'Content-Type': 'application/json',
					'Authorization' : 'Basic %s' % self.auth_token()
					}
		api_call = requests.request("GET", url, headers=headers, data = payload)
		response_data = json.loads(api_call.text)
		for carrier in response_data:
			shipstation_carrier_id = shipstation_carrier_obj.search([('code', '=', carrier.get('code'))])
			if not shipstation_carrier_id:
				shipstation_carrier_id = shipstation_carrier_obj.create({
										'name': carrier.get('name'),
										'code': carrier.get('code'),
										'carrierCode': carrier.get('carrierCode'),
										'domestic': carrier.get('domestic'),
										'international': carrier.get('international'),
										})
		return True

	def get_services(self, shipstation_carrier_id):
		delivery_obj = self.env['delivery.carrier']
		url = self.server_url + "/carriers/listservices?carrierCode=%s" % shipstation_carrier_id.code
		payload = {}
		headers = {
					'Host': 'ssapi.shipstation.com',
					'Content-Type': 'application/json',
					'Authorization' : 'Basic %s' % self.auth_token()
					}
		api_call = requests.request("GET", url, headers=headers, data = payload)
		response_data = json.loads(api_call.text)
		shipstation_product = self.sudo().env.ref(
            'delivery_shipstation.product_product_delivery_shipstation')
		shipstation_default_packaging= self.sudo().env.ref(
            'delivery_shipstation.shipstation_customer_packaging')
		for result in response_data:
			service_id = delivery_obj.search([('shipstation_service_code', '=', result.get('code'))])
			if not service_id:
				service_id = delivery_obj.sudo().create({'name': 'Shipstation -> '+ shipstation_carrier_id.name + ' - ' + result.get('name'),
							                         'product_id': shipstation_product.id,
							                         'shipstation_service_code': result.get('code'),
							                         'shipstation_carrier_code': result.get('carrierCode'),
							                         'shipstation_carrier_id': shipstation_carrier_id.id,
							                         'prod_environment': True if self.test_production == 'production' else False,
							                         'shipstation_default_packaging_id': shipstation_default_packaging.id,
							                         'delivery_type': 'shipstation'})
		return True

