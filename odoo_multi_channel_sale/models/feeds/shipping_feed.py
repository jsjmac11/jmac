# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models
from odoo.addons.odoo_multi_channel_sale.tools import extract_list as EL
from logging import getLogger


_logger = getLogger(__name__)

ShippingFields = [
	'name',
	'shipping_carrier',
	'is_international',
	'description',
	'store_id',
]

class ShippingFeed(models.Model):
	_name        = 'shipping.feed'
	_inherit     = 'wk.feed'
	_description = 'Shipping Feed'

	description      = fields.Text('Description')
	shipping_carrier = fields.Char('Shipping Carrier')
	is_international = fields.Boolean('Is International')

	@api.model
	def get_shipping_fields(self):
		return ShippingFields

	@api.model
	def get_shiping_carrier(self,carrier_name,channel_id=None):
		channel_id  = channel_id or self.channel_id
		return self.env['delivery.carrier'].search(
			[('name','=',carrier_name)], limit=1
		) or self.env['delivery.carrier'].create(
			{
				'name'        : carrier_name,
				'fixed_price' : 0,
				'product_id'  : channel_id.delivery_product_id.id
			}
		)

	def get_shiping_carrier_mapping(self,channel_id,shipping_service_id):
		mapping_id = channel_id.match_carrier_mappings(shipping_service_id)
		if mapping_id:
			return mapping_id
		else:
			carrier_id = self.get_shiping_carrier(shipping_service_id,channel_id)
			vals = dict(
				name     = shipping_service_id,
				store_id = shipping_service_id
			)
			return self.create_shipping_mapping(channel_id,carrier_id.id,vals)

	@api.model
	def _create_feeds(self, shipping_data_list):
		success_ids, error_ids = [], []
		self = self.contextualize_feeds('shipping')
		for shipping_data in shipping_data_list:
			feed = self._create_feed(shipping_data)
			if feed:
				self += feed
				success_ids.append(shipping_data.get('store_id'))
			else:
				error_ids.append(shipping_data.get('store_id'))
		return success_ids, error_ids, self

	@api.model
	def _create_feed(self, shipping_data):
		channel_id = shipping_data.get('channel_id')
		store_id = str(shipping_data.get('store_id'))
		feed_id = self._context.get('shipping_feeds').get(
			channel_id, {}).get(store_id)
		try:
			if feed_id:
				feed = self.browse(feed_id)
				shipping_data.update(state='draft')
				feed.write(shipping_data)
			else:
				feed = self.create(shipping_data)
		except Exception as e:
			_logger.error(
				"Failed to create feed for Collection: "
				f"{shipping_data.get('store_id')}"
				f" Due to: {e.args[0]}"
			)
		else:
			return feed

	@api.model
	def create_shipping_mapping(self,channel_id,carrier_id,vals):
		return self.env['channel.shipping.mappings'].create(
			dict(
				channel_id             = channel_id.id,
				ecom_store             = channel_id.channel,
				odoo_carrier_id        = carrier_id,
				odoo_shipping_carrier  = carrier_id,
				shipping_service       = vals.get('name'),
				international_shipping = vals.get('international_shipping'),
				shipping_service_id    = vals.get('store_id')
			)
		)

	def import_item(self):
		self.ensure_one()
		message        = ""
		mapping_id     = None
		update_id      = None
		create_id      = None
		state          = 'done'
		carrier_id     = False
		vals           = EL(self.read(self.get_shipping_fields()))

		shipping_carrier = vals.pop('shipping_carrier')
		if not vals.get('name'):
			message += "<br/>Shipping Method without name can't evaluated"
			state = 'error'
		if not vals.get('store_id'):
			message += "<br/>Shipping Method without store ID can't evaluated"
			state = 'error'
		if not shipping_carrier:
			message += "<br/>Shipping Method without shipping carrier can't evaluated"
			state = 'error'
		try:
			carrier_id = self.get_shiping_carrier(shipping_carrier).id
		except Exception as e:
			state = 'error'
			message += '<br/> Error in evaluating Shipping carrier %s' % (
				vals.get('name',''))


		map_domain = self.get_channel_domain() + [
			('shipping_service_id','=',vals.get('store_id'))
		]
		match = self.env['channel.shipping.mappings'].search(map_domain,limit=1)
		if state == 'done':
			if match:
				res = match.write({
					'shipping_service'      : vals.get('name', match.shipping_service),
					'international_shipping': vals.get('is_international', False),
					'shipping_service_id'   : vals.get('store_id', match.shipping_service_id)
				})
				mapping_id = match
				update_id  = mapping_id
				if res:
					message += 'Some Shipping carriers have been updated'
			else:
				mapping_id = self.create_shipping_mapping(self.channel_id,carrier_id,vals)
				message += '<br/> Shipping carrier %s Successfully Evaluated' % (
					vals.get('name',''))
				create_id = mapping_id

		self.set_feed_state(state=state)
		self.message = "%s <br/> %s" % (self.message,message)
		return dict(
			mapping_id = mapping_id,
			message    = message,
			update_id  = update_id,
			create_id  = create_id
		)

	def import_items(self):
		mapping_ids = []
		message     = ''
		update_ids  = []
		create_ids  = []
		sync_vals = dict(
			status      = 'error',
			action_on   = 'shipping',
			action_type = 'import',
		)
		for record in self:
			res         = record.import_item()
			message    += res.get('message','')
			mapping_id  = res.get('mapping_id')
			update_id   = res.get('update_id')
			if update_id:
				update_ids.append(update_id)
			create_id = res.get('create_id')
			if create_id:
				create_ids.append(create_id)
			if mapping_id:
				mapping_ids.append(mapping_id.id)
				sync_vals['status']             = 'success'
				sync_vals['ecomstore_refrence'] = mapping_id.shipping_service_id
				sync_vals['odoo_id']            = mapping_id.odoo_shipping_carrier
			sync_vals['summary'] = message
			record.channel_id._create_sync(sync_vals)
		if self._context.get('get_mapping_ids'):
			return dict(
				update_ids=update_ids,
				create_ids=create_ids,
			)
		message = self.get_feed_result(feed_type='Shipping')
		return self.env['multi.channel.sale'].display_message(message)
