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

PartnerFields = [
	'name',
	'store_id',

	'email',
	'phone',
	'mobile',
	'website',
	'last_name',
	'street',
	'street2',
	'city',
	'zip',
	'state_id',
	'state_name',
	'country_id',
	'type',
	'parent_id'
]

class PartnerFeed(models.Model):
	_name        = 'partner.feed'
	_inherit     = 'wk.feed'
	_description = 'Partner Feed'

	email      = fields.Char('Email')
	phone      = fields.Char('Phone')
	mobile     = fields.Char('Mobile')
	website    = fields.Char('Website URL')
	last_name  = fields.Char('Last Name')
	street     = fields.Char('Street')
	street2    = fields.Char('street2')
	city       = fields.Char('City')
	zip        = fields.Char('Zip')
	state_name = fields.Char('State Name')
	state_id   = fields.Char('State Code')
	country_id = fields.Char('Country Code')
	parent_id  = fields.Char('Store Parent ID')
	type       = fields.Selection(
		selection = [
			('contact','Contact'),
			('invoice','Invoice'),
			('delivery','Delivery'),
		],
		default  = 'contact',
		required = True
	)

	@api.model
	def _create_feeds(self,partner_data_list):
		success_ids,error_ids = [],[]
		self = self.contextualize_feeds('partner')
		for partner_data in partner_data_list:
			feed = self._create_feed(partner_data)
			if feed:
				self += feed
				success_ids.append(partner_data.get('store_id'))
			else:
				error_ids.append(partner_data.get('store_id'))
		return success_ids,error_ids,self

	def _create_feed(self,partner_data):
		contact_data_list = partner_data.pop('contacts',[])
		channel_id = partner_data.get('channel_id')
		store_id = str(partner_data.get('store_id'))
		feed_id = self._context.get('partner_feeds').get(channel_id,{}).get(store_id)
# Todo(Pankaj Kumar): Change feed field from state_id,country_id to state_code,country_code
		partner_data['state_id'] = partner_data.pop('state_code',False)
		partner_data['country_id'] = partner_data.pop('country_code',False)
# & remove this code
		try:
			if feed_id:
				feed = self.browse(feed_id)
				partner_data.update(state='draft')
				feed.write(partner_data)
			else:
				feed = self.create(partner_data)
		except Exception as e:
			_logger.error(
				"Failed to create feed for Customer: "
				f"{partner_data.get('store_id')}"
				f" Due to: {e.args[0]}"
			)
		else:
			for contact_data in contact_data_list:
				feed+=self._create_feed(contact_data)
			return feed

	def import_partner(self,channel_id):
		self.ensure_one()
		message   = ""
		state     = 'done'
		update_id = None
		create_id = None

		vals = EL(self.read(PartnerFields))
		_type =vals.get('type')
		store_id = vals.pop('store_id')
		vals.pop('website_message_ids','')
		vals.pop('message_follower_ids','')
		match = channel_id.match_partner_mappings(store_id,_type)
		name = vals.pop('name')
		if not name:
			message+="<br/>Partner without name can't evaluated."
			state = 'error'
		if not store_id:
			message+="<br/>Partner without store id can't evaluated."
			state = 'error'
		parent_store_id = vals['parent_id']
		if parent_store_id:
			partner_res = self.get_partner_id(parent_store_id,channel_id=channel_id)
			message += partner_res.get('message')
			partner_id = partner_res.get('partner_id')
			if partner_id:
				vals['parent_id'] =partner_id.id
			else:
				state = 'error'
		if state == 'done':
			country_id = vals.pop('country_id')
			if country_id:
				country_id = channel_id.get_country_id(country_id)
				if country_id:
					vals['country_id'] = country_id.id
			state_id = vals.pop('state_id')
			state_name = vals.pop('state_name')

			if (state_id or state_name) and country_id:
				state_id = channel_id.get_state_id(state_id,country_id,state_name)
				if state_id:
					vals['state_id'] = state_id.id
			last_name = vals.pop('last_name','')
			if last_name:
				vals['name'] = "%s %s" % (name, last_name)
			else:
				vals['name'] =name
		if match:
			if state =='done':
				try:
					match.odoo_partner.write(vals)
					message +='<br/> Partner %s successfully updated'%(name)
				except Exception as e:
					message += '<br/>%s' % (e)
					state = 'error'
				update_id = match

			elif state =='error':
				message+='Error while partner updated.'

		else:
			if state == 'done':
				try:
					erp_id = self.env['res.partner'].create(vals)
					create_id =  channel_id.create_partner_mapping(erp_id, store_id,_type)
					message += '<br/>Partner %s successfully evaluated.'%(name)
				except Exception as e:
					message += '<br/>%s' % (e)
					state = 'error'
		self.set_feed_state(state=state)
		self.message = "%s <br/> %s" % (self.message, message)
		return dict(
			create_id=create_id,
			update_id=update_id,
			message=message
		)

	def import_items(self):
		self = self.contextualize_feeds('partner',self.mapped('channel_id').ids)
		self = self.contextualize_mappings('partner',self.mapped('channel_id').ids)
		update_ids=[]
		create_ids=[]
		message = ''

		for record in self:
			channel_id = record.channel_id
			sync_vals = dict(
			status ='error',
			action_on ='customer',
			action_type ='import',
			)
			res = record.import_partner(channel_id)
			msz= res.get('message', '')
			message+=msz
			update_id = res.get('update_id')
			if update_id:
				update_ids.append(update_id)
			create_id = res.get('create_id')
			if create_id:
				create_ids.append(create_id)
			mapping_id = update_id or create_id
			if mapping_id:
				sync_vals['status'] = 'success'
				sync_vals['ecomstore_refrence'] = mapping_id.store_customer_id
				sync_vals['odoo_id'] = mapping_id.odoo_partner_id
			sync_vals['summary'] = msz
			record.channel_id._create_sync(sync_vals)
		if self._context.get('get_mapping_ids'):
			 return dict(
				update_ids=update_ids,
				create_ids=create_ids,
			)
		message = self.get_feed_result(feed_type='Partner')
		return self.env['multi.channel.sale'].display_message(message)

	