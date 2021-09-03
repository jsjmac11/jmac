# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models
from odoo.addons.odoo_multi_channel_sale.tools import parse_float,extract_list as EL

import copy
from logging import getLogger
_logger = getLogger(__name__)


OrderFields = [
	'name',
	'store_id',
	'store_source',

	'partner_id',
	'order_state',
	'carrier_id',
	'date_invoice',
	'date_order',
	'confirmation_date',
	'line_ids',
	'line_name',
	'line_price_unit',
	'line_product_id',
	'line_product_default_code',
	'line_product_barcode',
	'line_variant_ids',
	'line_source',
	'line_product_uom_qty',
	'line_taxes',
]


class OrderFeed(models.Model):
	_name        = 'order.feed'
	_inherit     = ['wk.feed','order.line.feed']
	_description = 'Order Feed'

	partner_id          = fields.Char('Store Customer ID')
	order_state         = fields.Char('Order State')
	date_order          = fields.Char('Order Date')
	confirmation_date   = fields.Char('Confirmation Date')
	date_invoice        = fields.Char('Invoice Date')
	carrier_id          = fields.Char('Delivery Method',help='Delivery Method Name')
	payment_method      = fields.Char('Payment Method',help='Payment Method Name')
	currency            = fields.Char('Currency Name')
	customer_is_guest   = fields.Boolean('Customer Is Guest')
	customer_name       = fields.Char('Customer Name')
	customer_phone      = fields.Char('Customer Phone')
	customer_mobile     = fields.Char('Customer Mobile')
	customer_last_name  = fields.Char('Customer Last Name')
	customer_email      = fields.Char('Customer Email')

	shipping_partner_id = fields.Char('Shipping Partner ID')
	shipping_name       = fields.Char('Shipping Name')
	shipping_last_name  = fields.Char('Shipping Last Name')
	shipping_email      = fields.Char('Shipping Email')
	shipping_phone      = fields.Char('Shipping Phone')
	shipping_mobile     = fields.Char('Shipping Mobile')
	shipping_street     = fields.Char('Shipping Street')
	shipping_street2    = fields.Char('Shipping street2')
	shipping_city       = fields.Char('Shipping City')
	shipping_zip        = fields.Char('Shipping Zip Code')
	shipping_state_name = fields.Char('Shipping State Name')
	shipping_state_id   = fields.Char('Shipping State Code')
	shipping_country_id = fields.Char('Shipping Country Code')

	invoice_partner_id  = fields.Char('Invoice Partner ID')
	invoice_name        = fields.Char('Invoice Name')
	invoice_last_name   = fields.Char('Invoice Last Name')
	invoice_email       = fields.Char('Invoice Email')
	invoice_phone       = fields.Char('Invoice Phone')
	invoice_mobile      = fields.Char('Invoice Mobile')
	invoice_street      = fields.Char('Invoice Street')
	invoice_street2     = fields.Char('Invoice street2')
	invoice_city        = fields.Char('Invoice City')
	invoice_zip         = fields.Char('Invoice Zip Code')
	invoice_state_name  = fields.Char('Invoice State Name')
	invoice_state_id    = fields.Char('Invoice State Code')
	invoice_country_id  = fields.Char('Invoice Country Code')

	same_shipping_billing = fields.Boolean(
		string  = 'Shipping Address Same As Billing',
		default = True
	)
	line_type = fields.Selection(
		selection = [
			('single','Single Order Line'),
			('multi','Multi Order Line')
		],
		default   = 'single',
		string    = 'Line Type',
	)
	line_ids = fields.One2many('order.line.feed','order_feed_id',string='Line Ids')

	@api.model
	def _create_feeds(self,order_data_list):
		success_ids,error_ids = [],[]
		self = self.contextualize_feeds('order')
		for order_data in order_data_list:
			order_feed = self._create_feed(order_data)
			if order_feed:
				self += order_feed
				success_ids.append(order_data.get('store_id'))
			else:
				error_ids.append(order_data.get('store_id'))
		return success_ids,error_ids,self

	def _create_feed(self,order_data):
		channel_id = order_data.get('channel_id')
		store_id = str(order_data.get('store_id'))
		feed_id = self._context.get('order_feeds').get(channel_id,{}).get(store_id)
# Todo(Pankaj Kumar): Change feed field from state_id,country_id to state_code,country_code
		order_data['invoice_state_id'] = order_data.pop('invoice_state_code',False)
		order_data['invoice_country_id'] = order_data.pop('invoice_country_code',False)

		if not order_data.get('same_shipping_billing'):
			order_data['shipping_state_id'] = order_data.pop('shipping_state_code',False)
			order_data['shipping_country_id'] = order_data.pop('shipping_country_code',False)
# & remove this code
		try:
			if feed_id:
				feed = self.browse(feed_id)
				feed.line_ids=False
				order_data.update(state='draft')
				feed.write(order_data)
			else:
				feed = self.create(order_data)
		except Exception as e:
			_logger.error(
				"Failed to create feed for Order: "
				f"{order_data.get('store_id')}"
				f" Due to: {e.args[0]}"
			)
		else:
			return feed

	@api.model
	def _get_order_line_vals(self, vals, carrier_id, channel_id):
		message = ''
		status=True
		lines = []
		line_ids = vals.pop('line_ids')
		line_name = vals.pop('line_name')
		line_price_unit = vals.pop('line_price_unit')
		if line_price_unit:
			line_price_unit = parse_float(line_price_unit)
		line_product_id = vals.pop('line_product_id')
		line_variant_ids = vals.pop('line_variant_ids')
		line_product_uom_qty = vals.pop('line_product_uom_qty')
		line_product_default_code = vals.pop('line_product_default_code')
		line_source = vals.pop('line_source')
		line_product_barcode = vals.pop('line_product_barcode')
		line_taxes = vals.pop('line_taxes')
		if line_ids:
			for line_id in self.env['order.line.feed'].browse(line_ids):
				line_price_unit = line_id.line_price_unit
				if line_price_unit:
					line_price_unit = parse_float(line_price_unit)
				if line_id.line_source =='delivery':
					product_id = carrier_id.product_id if carrier_id else False
				elif line_id.line_source =='discount':
					if not channel_id.discount_product_id:
						product_id  =channel_id.create_product('discount')
						channel_id.discount_product_id = product_id.id
					product_id = channel_id.discount_product_id
					line_price_unit = -line_price_unit
				elif line_id.line_source =='product':
					product_res = self.get_product_id(
						line_id.line_product_id,
						line_id.line_variant_ids or 'No Variants',
						channel_id,
						line_id.line_product_default_code,
						line_id.line_product_barcode,

					)
					product_id = product_res.get('product_id')
					if product_res.get('message'):
						_logger.error("OrderLineError1 %r"%product_res)
						message += product_res.get('message')
				if product_id:
					product_uom_id = product_id.uom_id.id
					line = dict(
						name=line_id.line_name,
						price_unit=line_price_unit,
						product_id=product_id.id,
						customer_lead=product_id.sale_delay,
						product_uom_qty=line_id.line_product_uom_qty,
						is_delivery = line_id.line_source =='delivery',
						product_uom=product_uom_id,
					)
					line['tax_id'] = self.get_taxes_ids(line_id.line_taxes,channel_id)
					####ADD TAX
					lines += [(0,0,line)]
				else:
					status=False
		else:
			product_res = self.get_product_id(
				line_product_id,
				line_variant_ids or 'No Variants',
				channel_id,
				line_product_default_code,
				line_product_barcode,

			)
			product_id = product_res.get('product_id')
			if product_id:
				if line_product_uom_qty:
					line_product_uom_qty = parse_float(line_product_uom_qty) or 1
				line = dict(
					name=line_name or '',
					price_unit=(line_price_unit),
					product_id=product_id.id,
					customer_lead=product_id.sale_delay,
					is_delivery = line_source =='delivery',
					product_uom_qty=(line_product_uom_qty),
					product_uom=product_id.uom_id.id,
				)
				line['tax_id'] = self.get_taxes_ids(line_taxes,channel_id)
				####ADD TAX
				lines += [(0,0,line)]
			else:
				_logger.error("OrderLineError2 %r"%product_res)
				message += product_res.get('message')
				status=False
		return dict(
			message=message,
			order_line=lines,
			status =status
		)

	def  get_taxes_ids(self,line_taxes,channel_id):
		if line_taxes:
			line_taxes=eval(line_taxes)
			if line_taxes:
				tax_record=self.env['account.tax']
				tax_mapping_obj= self.env['channel.account.mappings']
				tax_list=[]
				domain=[]
				channel=str(self.channel)
				for tax in line_taxes:
					name=""
					tax_type="percent"
					inclusive=False
					if tax.get('name'):
						name = tax['name']
					else:
						name = channel+"_"+str(channel_id.id)+"_"+str(float(tax['rate']))
					if tax.get('include_in_price'):
						inclusive=tax['include_in_price']
						# domain += [('include_in_price','=',tax['include_in_price'])]
					if tax.get('tax_type'):
						tax_type=tax['tax_type']
						domain += [('tax_type','=',tax['tax_type'])]
					domain += [('store_tax_value_id','=',(tax['rate']))]
					tax_rec = channel_id._match_mapping(tax_mapping_obj,domain, 1)
					if tax_rec:
						# tax_rec.tax_name.price_include = inclusive
						tax_list.append(tax_rec.tax_name.id)
					else:
						tax_dict={
						  'name'            : name,
						  'amount_type'     : tax_type,
						  'price_include'   : inclusive,
						  'amount'          : float(tax['rate']),
						}
						tax_id = tax_record.search([('name','=',tax_dict['name'])],limit=1)
						if not tax_id:
							tax_id=tax_record.create(tax_dict)
						tax_map_vals={
						  'channel_id'      : channel_id.id,
						  'tax_name'        : tax_id.id,
						  'store_tax_value_id' : tax_id.amount,
						  'tax_type'        : tax_id.amount_type,
						  'include_in_price': tax_id.price_include,
						  'odoo_tax_id'     : tax_id.id,
						}
						channel_id._create_mapping(tax_mapping_obj,tax_map_vals)
						tax_list.append(tax_id.id)
				return [(6,0,tax_list)]
		return False
	@api.model
	def get_order_date_info(self,channel_id,vals):
		date_order = None
		confirmation_date = None
		date_invoice = None
		date_order_res =  channel_id.om_format_date_time(vals.pop('date_order'))
		if date_order_res.get('om_date_time'):
			date_order = date_order_res.get('om_date_time')

		confirmation_date_res =  channel_id.om_format_date_time(vals.pop('confirmation_date'))
		if confirmation_date_res.get('om_date_time'):
			confirmation_date = confirmation_date_res.get('om_date_time')

		date_invoice_res =  channel_id.om_format_date(vals.pop('date_invoice'))
		if date_invoice_res.get('om_date'):
			date_invoice = date_invoice_res.get('om_date')
		return dict(
			date_order = date_order,
			confirmation_date = confirmation_date,
			date_invoice = date_invoice,
		)

	@api.model
	def get_order_fields(self):
		return copy.deepcopy(OrderFields)

	def import_order(self,channel_id):
		message = ""
		update_id=None
		create_id=None
		self.ensure_one()
		vals = EL(self.read(self.get_order_fields()))
		store_id = vals.pop('store_id')

		store_source = vals.pop('store_source')
		match = self._context.get('order_mappings').get(channel_id.id,{}).get(store_id)
		if match:
			match = self.env['channel.order.mappings'].browse(match)
		state = 'done'
		store_partner_id = vals.pop('partner_id')


		date_info = self.get_order_date_info(channel_id,vals)
		if date_info.get('confirmation_date'):
			vals['date_order']=date_info.get('confirmation_date')
		elif date_info.get('date_order'):
			vals['date_order']=date_info.get('date_order')

		date_invoice =  date_info.get('date_invoice')
		confirmation_date = date_info.get('confirmation_date')

		if store_partner_id:
			if not match:
				res_partner = self.get_order_partner_id(store_partner_id,channel_id)
				message += res_partner.get('message','')
				partner_id = res_partner.get('partner_id')
				partner_invoice_id = res_partner.get('partner_invoice_id')
				partner_shipping_id = res_partner.get('partner_shipping_id')
				if partner_id and partner_invoice_id and partner_shipping_id:
					vals['partner_id'] = partner_id.id
					vals['partner_invoice_id'] = partner_invoice_id.id
					vals['partner_shipping_id'] = partner_shipping_id.id
				else:
					message += '<br/>Partner,Invoice,Shipping Address must present.'
					state = 'error'
					_logger.error('#OrderError1 %r'%message)
		else:
			message += '<br/>No partner in sale order data.'
			state = 'error'
			_logger.error('#OrderError2 %r'%message)


		if state=='done':
			carrier_id = vals.pop('carrier_id','')

			if carrier_id:
				carrier_res = self.get_carrier_id(carrier_id,channel_id=channel_id)
				message += carrier_res.get('message')
				carrier_id = carrier_res.get('carrier_id')
				if carrier_id:
					vals['carrier_id'] = carrier_id.id
			order_line_res = self._get_order_line_vals(vals,carrier_id,channel_id)
			message += order_line_res.get('message','')
			if not order_line_res.get('status'):
				state = 'error'
				_logger.error('#OrderError3 %r'%order_line_res)
			else:
				order_line = order_line_res.get('order_line')
				if len(order_line):
					vals['order_line'] = order_line
					state = 'done'
		currency=self.currency

		if state=='done' and currency:
			currency_id = channel_id.get_currency_id(currency)
			if not currency_id:
				message += '<br/> Currency %s no active in Odoo'%(currency)
				state = 'error'
				_logger.error('#OrderError4 %r'%message)
			else:
				pricelist_id = channel_id.match_create_pricelist_id(currency_id)
				vals['pricelist_id']=pricelist_id.id

		vals.pop('name')
		vals.pop('id')
		vals.pop('website_message_ids','')
		vals.pop('message_follower_ids','')
		vals['team_id'] = channel_id.crm_team_id.id
		vals['warehouse_id'] = channel_id.warehouse_id.id


		if match and match.order_name:
			if  state =='done' :
				try:
					order_state = vals.pop('order_state')
					if match.order_name.state=='draft':
						match.order_name.write(dict(order_line=[(5,0)]))
						match.order_name.write(vals)
						message +='<br/> Order %s successfully updated'%(vals.get('name',''))
					else:
						message+='Only order state can be update as order not in draft state.'
					message += self.env['multi.channel.skeleton']._SetOdooOrderState(match.order_name,channel_id,
							order_state,self.payment_method,date_invoice=date_invoice,confirmation_date=confirmation_date)
				except Exception as e:
					message += '<br/>%s' % (e)
					_logger.error('#OrderError5  %r'%message)
					state = 'error'
				update_id = match
			elif state =='error':
				message+='<br/>Error while order update.'
		else:
			if state == 'done':
				try:
					order_state = vals.pop('order_state')
					erp_id = self.env['sale.order'].create(vals)
					message += self.env['multi.channel.skeleton']._SetOdooOrderState(erp_id,channel_id,order_state,self.payment_method,date_invoice=date_invoice,confirmation_date=confirmation_date)
					message  += '<br/> Order %s successfully evaluated'%(self.store_id)
					create_id =  channel_id.create_order_mapping(erp_id,store_id,store_source)

				except Exception as e:
					message += '<br/>%s' % (e)
					_logger.error('#OrderError6 %r'%message)
					state = 'error'
		self.set_feed_state(state=state)
		self.message = "%s <br/> %s" % (self.message,message)
		return dict(
			create_id=create_id,
			update_id=update_id,
			message=message
		)

	def import_items(self):
		self = self.contextualize_feeds('category',self.mapped('channel_id').ids)
		self = self.contextualize_mappings('category',self.mapped('channel_id').ids)
		self = self.contextualize_feeds('product',self.mapped('channel_id').ids)
		self = self.contextualize_mappings('product',self.mapped('channel_id').ids)
		self = self.contextualize_mappings('order',self.mapped('channel_id').ids)
		update_ids=[]
		create_ids=[]
		message=''
		for record in self:
			channel_id = record.channel_id
			sync_vals = dict(
			status ='error',
			action_on ='order',
			action_type ='import',
			)
			res = record.import_order(channel_id)
			msz= res.get('message','')
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
				sync_vals['ecomstore_refrence'] = mapping_id.store_order_id
				sync_vals['odoo_id'] = mapping_id.odoo_order_id
			sync_vals['summary'] = msz
			channel_id._create_sync(sync_vals)
		if self._context.get('get_mapping_ids'):
			 return dict(
				update_ids=update_ids,
				create_ids=create_ids,
			)
		message =  self.get_feed_result(feed_type='Sale Order')
		return self.env['multi.channel.sale'].display_message(message)

