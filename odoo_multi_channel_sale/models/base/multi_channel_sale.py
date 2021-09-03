# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
import binascii
import codecs
import logging
import requests

from dateutil import parser
from io import BytesIO
from PIL import Image

from odoo import fields, models, api, _

from ...tools import DomainVals, ReverseDict

_logger = logging.getLogger(__name__)

HelpImportOrderDate  = _(
"""A date used for selecting orders created after (or at) a specified time."""
)

HelpUpdateOrderDate = _(
"""
	A date used for selecting orders that were last updated after (or at) a specified time.
	 An update is defined as any change in order status,includes updates made by the seller.
"""
)

STATE = [
	('draft', 'Draft'),
	('validate', 'Validate'),
	('error', 'Error')
]
DEBUG = [
	('enable', 'Enable'),
	('disable', 'Disable')
]
ENVIRONMENT = [
	('production', 'Production Server'),
	('sandbox', 'Testing(Sandbox) Server)')
]
FEED = [
	('all', 'For All Models'),
	('order', 'For Order Only'),
]
ProductIdType = [
	('wk_upc', 'UPC'),
	('wk_ean', 'EAN'),
	('wk_isbn', 'ISBN'),
]

MAPPINGMODEL = {
	'product.product' : 'channel.product.mappings',
	'product.template': 'channel.template.mappings',
	'res.partner'     : 'channel.partner.mappings',
	'product.category': 'channel.category.mappings',
	'sale.order'      : 'channel.order.mappings',
}


class MultiChannelSale(models.Model):
	_name = 'multi.channel.sale'
	_description = 'Multi Channel Sale'
	_inherit = ['mail.thread', 'mail.activity.mixin']

	import_order_cron = fields.Boolean("Import Orders")
	import_product_cron = fields.Boolean("Import Products")
	import_partner_cron = fields.Boolean("Import Customers")
	import_category_cron = fields.Boolean("Import Categories")

	channel_stock_action = fields.Selection([
		('qoh', 'Quantity on hand'),
		('fq', 'Forecast Quantity')
		],
		default='qoh',
		string='Stock Management',
		help="Manage Stock")

	@api.model
	def get_quantity(self, obj_pro):
		"""
			to get quantity of product or product template
			@params : product template obj or product obj
			@return : quantity in hand or quantity forecasted
		"""
		quantity = 0.0
		ctx = self._context.copy() or {}
		if not 'location' in ctx:
			ctx.update({
				'location': self.location_id.id
			})
		qty = obj_pro.with_context(ctx)._product_available(None, False)
		if self.channel_stock_action =="qoh":
			quantity = qty[obj_pro.id]['qty_available']
		else:
			quantity = qty[obj_pro.id]['virtual_available']
		if type(quantity) == str:
			quantity = quantity.split('.')[0]
		if type(quantity) == float:
			quantity = quantity.as_integer_ratio()[0]
		return quantity

	@api.model
	def create(self, vals):
		res = super().create(vals)
		channels = self.get_core_feature_compatible_channels()
		if res.channel in channels:
			res.use_core_feature = True
		return res

	url     = fields.Char()
	email   = fields.Char(string='Api User')
	api_key = fields.Char()

	def test_connection(self):
		self.ensure_one()
		if hasattr(self, 'connect_%s' % self.channel):
			res,msg = getattr(self, 'connect_%s' % self.channel)()
			if res:
				self.state = 'validate'
			else:
				self.state = 'error'
			return self.display_message(msg)
		elif hasattr(self, 'test_%s_connection' % self.channel):
			_logger.warn(
				'Error in use of MultiChannelSale class: '
				'use of test_connection function to establish connection to Channel.'
			)
			return getattr(self, 'test_%s_connection' % self.channel)()
		else:
			return self.display_message('Connection protocol missing.')

	def display_message(self, message):
		return self.env['wk.wizard.message'].genrated_message(message,'Summary')

	def get_core_feature_compatible_channels(self):
		'''
			Channels supporting core features such as import/export
			operation wizard to be appended by bridges.

			Returns:
				list -- names of channels
		'''
		return []

	def set_to_draft(self):
		self.state = 'draft'

	def open_mapping_view(self):
		self.ensure_one()
		res_model = self._context.get('mapping_model')
		store_field = self._context.get('store_field')
		domain = [
			('channel_id', '=', self.id),
		]
		mapping_ids = self.env[res_model].search(domain).ids
		return {
			'name': ('Mapping'),
			'type': 'ir.actions.act_window',
			'view_mode': 'tree,form',
			'res_model': res_model,
			'view_id': False,
			'domain': [('id', 'in', mapping_ids)],
			'target': 'current',
		}

	def open_record_view(self):
		self.ensure_one()
		res_model = self._context.get('mapping_model')
		odoo_mapping_field = self._context.get('odoo_mapping_field')
		domain = [
			('channel_id', '=', self.id),
		]
		erp_ids = self.env[res_model].search(domain).mapped(odoo_mapping_field)
		erp_model = ReverseDict(MAPPINGMODEL).get(res_model)
		domain = [('id', 'in', erp_ids)]
		if erp_model == 'res.partner':
			domain.append(('parent_id', '=', False))
		return {
			'name': ('Record'),
			'type': 'ir.actions.act_window',
			'view_mode': 'tree,form',
			'res_model': erp_model,
			'view_id': False,
			'domain': domain,
			'target': 'current',
		}

	def _get_count(self):
		for rec in self:
			domain = [('channel_id', '=', rec.id)]
			rec.channel_products   = self.env['channel.template.mappings'].search_count(domain)
			rec.channel_categories = self.env['channel.category.mappings'].search_count(domain)
			rec.channel_orders     = self.env['channel.order.mappings'].search_count(domain)
			domain.append(('odoo_partner.parent_id', '=', False))
			rec.channel_customers  = self.env['channel.partner.mappings'].search_count(domain)

	active = fields.Boolean(default=True)
	color_index  = fields.Integer(string='Color Index')


	# @api.model
	# def get_channel(self):
	# 	return self.fields_get(allfields=['channel'])['channel']['selection']

	@api.model
	def get_channel(self):
		channel_list = []
		return channel_list

	@api.model
	def get_info_urls(self):
		return {}

	def set_info_urls(self):
		for instance in self:
			url_info = self.get_info_urls().get(instance.channel,{})
			instance.blog_url = url_info.get('blog','https://webkul.com/blog/odoo-multi-channel-sale/')
			instance.store_url = url_info.get('store','https://store.webkul.com/Odoo-Multi-Channel-Sale.html')


	use_core_feature = fields.Boolean(readonly=True)
	channel = fields.Selection(selection='get_channel',required=True,inverse=set_info_urls)
	name = fields.Char('Name',required=True)
	state = fields.Selection(STATE,default='draft')
	color = fields.Char(default='#000')
	image = fields.Image(max_width=256,max_height=256)
	blog_url = fields.Char()
	store_url = fields.Char()
	debug = fields.Selection(DEBUG,default='enable',required=True)

	environment = fields.Selection(
		selection=ENVIRONMENT,
		string='Environment',
		default='sandbox',
		help="""Set environment to  production while using live credentials.""",
	)
	sku_sequence_id = fields.Many2one(
		comodel_name='ir.sequence',
		string='Sequence For SKU',
		help="""Default sequence used as sku/default code for product(in case product not have sku/default code).""",
	)
	language_id = fields.Many2one(
		comodel_name='res.lang',
		default = lambda self: self.env['res.lang'].search([], limit=1),
		help="""The language used over e-commerce store/marketplace.""",
	)

	pricelist_id = fields.Many2one('channel.pricelist.mappings','Pricelist Mapping')

	pricelist_name = fields.Many2one(
		comodel_name='product.pricelist',
		string='Default Pricelist',
		default=lambda self: self.env['product.pricelist'].search([], limit=1),
		help="""Select the same currency of pricelist used  over e-commerce store/marketplace.""",
	)
	default_category_id = fields.Many2one(
		comodel_name='product.category',
		string='Category',
		default=lambda self: self.env['product.category'].search([], limit=1),
		help="""Default category used as product internal category for imported products.""",
	)
	delivery_product_id = fields.Many2one(
		comodel_name='product.product',
		string='Delivery Product',
		domain=[('type', '=', 'service')],
		help="""Delivery product used in sale order line.""",
	)
	discount_product_id = fields.Many2one(
		comodel_name='product.product',
		string='Discount Product',
		domain=[('type', '=', 'service')],
		help="""Discount product used in sale order line.""",
	)
	warehouse_id = fields.Many2one(
		comodel_name='stock.warehouse',
		string='Warehouse',
		default=lambda self: self.env['stock.warehouse'].search([], limit=1),
		help='Warehouse used for imported product.',
	)
	location_id = fields.Many2one(
		related='warehouse_id.lot_stock_id',
		string='Stock Location',
		help='Stock Location used for imported product.',
	)
	company_id = fields.Many2one(
		related='warehouse_id.company_id',
		string='Company Id',
	)
	crm_team_id = fields.Many2one(
		comodel_name='crm.team',
		string='Sales Team',
		default=lambda self: self.env['crm.team'].search([], limit=1),
		help='Sales Team used for imported order.',
	)
	order_state_ids = fields.One2many(
		comodel_name='channel.order.states',
		inverse_name='channel_id',
		string='Default Odoo Order States',
		help='Imported order will process in odoo on basis of these state mappings.',
		copy = True,
	)

	feed = fields.Selection(FEED,default='all',required=True)

	auto_evaluate_feed = fields.Boolean(
		string='Auto Evaluate Feed',
		default=1,
		help='Auto Evaluate Feed Just After Import.',
	)
	auto_sync_stock = fields.Boolean(
		string='Auto Sync Stock',
		default=0,
		help='Enable this for real time stock sync over channel.',
	)

	sync_cancel = fields.Boolean(
		string='Cancel Status',
		help='Enable for cancel status at E-commerce',
	)
	sync_invoice = fields.Boolean(
		string='Invoice Status',
		help='Enable for update invoice status at E-commerce',
	)
	sync_shipment = fields.Boolean(
		string='Shipment Status',
		help='Enable for update shipment status at E-commerce',
	)

	import_order_date =  fields.Datetime(
		string='Order Imported',
		# default = fields.Datetime.now(),
		help = HelpImportOrderDate
	)

	update_order_date =  fields.Datetime(
		string='Order Updated',
		# default = fields.Datetime.now(),
		help = HelpUpdateOrderDate
	)

	import_product_date =  fields.Datetime(
		string='Product Imported',
		# default = fields.Datetime.now(),

	)
	update_product_price = fields.Boolean(
		string = 'Update Price',
	)
	update_product_stock = fields.Boolean(
		string = 'Update Stock',
	)
	update_product_image = fields.Boolean(
		string = 'Update Image',
	)
	update_product_date =  fields.Datetime(
		string='Product Updated',
		# default = fields.Datetime.now(),
	)

	import_customer_date =  fields.Datetime(
		string='Customer Imported',
		# default = fields.Datetime.now(),
	)
	update_customer_date =  fields.Datetime(
		string='Customer Updated',
		# default = fields.Datetime.now(),

	)
	api_record_limit = fields.Integer(
		string = 'API Record Limit',
		default = 100,
	)

	channel_products   = fields.Integer(compute='_get_count')
	channel_categories = fields.Integer(compute='_get_count')
	channel_orders     = fields.Integer(compute='_get_count')
	channel_customers  = fields.Integer(compute='_get_count')

	@api.constrains('api_record_limit')
	def check_api_record_limit(self):
		if self.api_record_limit<=0:
			raise Warning("""The api record limit should be postive.""")

	@api.model
	def set_channel_cron(self,ref_name='',active=False):
		try:
			cron_obj= self.env.ref(ref_name,False)
			if cron_obj:
				cron_obj.sudo().write(dict(active=active))
		except Exception as e:
			_logger.error("#1SetCronError  \n %r"%(e))
			raise Warning(e)

	@api.model
	def get_data_isoformat(self,date_time):
		try:
			return date_time and fields.Datetime.from_string(date_time).isoformat()
		except Exception as e:
			_logger.info("==%r="%(e))


	@api.onchange('channel')
	def _on_change_channel(self):
		if self.channel:
			if self.order_state_ids:
				rec = self.env['channel.order.states'].search([('channel_id','=',self._origin.id),('channel_name','=',self.channel)])

				if rec:
					self.order_state_ids = [(6,0,rec.ids)]
				else:
					self.order_state_ids = [(5,0,0)]
					if hasattr(self,'%s_default_order_state'%self.channel):
						"""
						Add default values to order state ids
						@field channel_state: state of the channel
						@field default_order_state: True or False
						@field odoo_create_invoice: True or False
						@field odoo_ship_order: True or False
						@field odoo_order_state: draft or shipped or done etc.
						@field odoo_set_invoice_state: paid or open
						@return: A list dictionarys of the default values
						"""
						values = getattr(self,'%s_default_order_state'%self.channel)()
						rec_val = []
						for rec in values:
							rec_val.append((0,0,rec))
						self.order_state_ids = rec_val
			else:
				if hasattr(self,'%s_default_order_state'%self.channel):
					"""
					Add default values to order state ids
					@field channel_state: state of the channel
					@field default_order_state: True or False
					@field odoo_create_invoice: True or False
					@field odoo_ship_order: True or False
					@field odoo_order_state: draft or shipped or done etc.
					@field odoo_set_invoice_state: paid or open
					@return: A list dictionarys of the default values
					"""
					values = getattr(self,'%s_default_order_state'%self.channel)()
					rec_val = []
					for rec in values:
						rec_val.append((0,0,rec))
					self.order_state_ids = rec_val


	@api.model
	def set_channel_date(self, operation = 'import',record = 'product'):
		current_date = fields.Datetime.now()
		if operation == 'import':
			if record == 'order':
				self.import_order_date = current_date
			elif record == 'product':
				self.import_product_date = current_date
			elif record == 'customer':
				self.import_customer_date = current_date
		else:
			if record == 'order':
				self.update_order_date = current_date
			elif record == 'product':
				self.update_product_date = current_date
			elif record == 'customer':
				self.update_customer_date = current_date
		return True

	def toggle_enviroment_value(self):
		production = self.filtered(
			lambda channel: channel.environment == 'production')
		production.write({'environment': 'sandbox'})
		(self - production).write({'environment': 'production'})
		return True

	def toggle_debug_value(self):
		enable = self.filtered(lambda channel: channel.debug == 'enable')
		enable.write({'debug': 'disable'})
		(self - enable).write({'debug': 'enable'})
		return True

	def toggle_active_value(self):
		for record in self:
			record.write({'active': not record.active})
		return True

	def toggle_enviroment_value(self):
		production = self.filtered(
			lambda channel: channel.environment == 'production')
		production.write({'environment': 'sandbox'})
		(self - production).write({'environment': 'production'})
		return True

	def toggle_debug_value(self):
		enable = self.filtered(lambda channel: channel.debug == 'enable')
		enable.write({'debug': 'disable'})
		(self - enable).write({'debug': 'enable'})
		return True

	def toggle_active_value(self):
		for record in self:
			record.write({'active': not record.active})
		return True

	@api.model
	def om_format_date(self, date_string):
		om_date = None
		message = ''
		try:
			if date_string:
				om_date = parser.parse(date_string).astimezone().replace(tzinfo=None)
		except Exception as e:
			message += '%r'%e
		return dict(
		message = message,
		om_date = om_date
		)
	@api.model
	def om_format_date_time(self, date_time_string):
		om_date_time = None
		message = ''
		try:
			if date_time_string:
				om_date_time = parser.parse(date_time_string).astimezone().replace(tzinfo=None)
		except Exception as e:
			message += '%r'%e
		return dict(
		message = message,
		om_date_time = om_date_time
		)

	@api.model
	def get_state_id(self, state_code, country_id, state_name=None):
		if (not state_code) and state_name:
			state_code = state_name[:2]
		state_name = state_name or ''
		domain = [
			('code', '=', state_code),
			('name', '=', state_name),
			('country_id', '=', country_id.id)
		]
		state_id = country_id.state_ids.filtered(
			lambda st:(
				st.code in [state_code,state_name[:3],state_name])
				or (st.name == state_name )
			)
		if not state_id:
			vals = DomainVals(domain)
			vals['name'] = state_name and state_name or state_code
			if (not vals['code']) and state_name:
				vals['code'] = state_name[:2]
			state_id = self.env['res.country.state'].create(vals)
		else:
			state_id =state_id[0]
		return state_id

	@api.model
	def get_country_id(self, country_code):
		domain = [
			('code', '=', country_code),
		]
		return self.env['res.country'].search(domain, limit=1)

	@api.model
	def get_currency_id(self, name):
		domain = [
			('name', '=', name),
		]
		return self.env['res.currency'].search(domain, limit=1)

	@api.model
	def create_model_objects(self, model_name, vals, **kwargs):
		"""
			model_name:'res.partner'
			vals:[{'name':'demo','type':'customer'},{'name':'portal':'type':'contact'}]
		"""
		message = ''
		data = None
		try:
			ObjModel = self.env[model_name]
			data = self.env[model_name]
			for val in vals:
				if kwargs.get('extra_val'):
					val.update( kwargs.get('extra_val'))
				match =False
				if val.get('store_id'):
					obj = ObjModel.search([('store_id', '=', val.get('store_id'))],limit= 1)
					if obj:
						obj.write(val)
						data += obj
						match = True
				if not match :
					data += ObjModel.create(val)
		except Exception as e:
			_logger.error("#1CreateModelObject Error  \n %r"%(e))
			message += "%r"%(e)
		return dict(
			data = data,
			message = message,
		)

	@api.model
	def create_product(self, name, _type='service', vals=None):
		vals = vals or {}
		vals['name'] = name
		vals['type'] = _type
		return self.env['product.product'].create(vals)

	@api.model
	def create_tax(self, name, amount, amount_type='percent', price_include=False):
		raise NotImplementedError

	@api.model
	def match_create_pricelist_id(self, currency_id):
		map_obj = self.env['channel.pricelist.mappings']
		channel_domain = self.get_channel_domain()
		domain = [
			('store_currency_code', '=', currency_id.name),
		]
		match = self._match_mapping(map_obj, domain)
		if match:
			return match.odoo_pricelist_id
		else:
			pricelist_id = self.env['product.pricelist'].create(
				dict(
					currency_id=currency_id.id,
					name=self.name
				)
			)
			vals = dict(
				store_currency=currency_id.id,
				store_currency_code=currency_id.name,
				odoo_pricelist_id=pricelist_id.id,
				odoo_currency_id=currency_id.id,
			)
			return self._create_mapping(map_obj, vals).odoo_pricelist_id

	@api.model
	def get_uom_id(self, name):
		domain = [
			('name', '=', name),
		]
		return self.env['uom.uom'].search(domain)

	@api.model
	def get_store_attribute_id(self, name, create_obj = False):
		domain = [
			('name', '=', name),
		]
		match = self.env['product.attribute'].search(domain)
		if (not match) and create_obj:
			match = self.env['product.attribute'].create(DomainVals(domain))
		return match

	@api.model
	def get_store_attribute_value_id(self, name, attribute_id , create_obj = False):
		domain = [
			('name', '=', name),
			('attribute_id', '=', attribute_id),
		]
		match = self.env['product.attribute.value'].search(domain)
		if (not match) and create_obj:
			match = self.env['product.attribute.value'].create(DomainVals(domain))
		return match

	@api.model
	def get_channel_domain(self,pre_domain=None):
		domain= []
		if type(self.id) == int:
			domain+= [('channel_id', '=', self.id)]
		if pre_domain:
			domain+=pre_domain
		return domain

	@api.model
	def get_channel_vals(self):
		return dict(
			channel_id=self.id,
			ecom_store = self.channel
		)
	@api.model
	def _create_obj(self, obj, vals):
		channel_vals = self.get_channel_vals()
		if self._context.get('obj_type') == 'feed':
			channel_vals.pop('ecom_store')
		vals.update(channel_vals)
		obj_id = obj.create(vals)
		return obj_id


	@api.model
	def _match_obj(self, obj, domain=None, limit=None):
		channel_domain = self.get_channel_domain(domain)
		new_domain = channel_domain
		if limit:
			return obj.search(new_domain, limit=limit)
		return obj.search(new_domain)


	@api.model
	def _create_mapping(self, mapping_obj, vals):
		return self._create_obj(mapping_obj, vals)


	@api.model
	def _match_mapping(self, mapping_obj, domain, limit=None):
		return self._match_obj(mapping_obj, domain, limit)


	@api.model
	def _create_feed(self, mapping_obj, vals):
		return self.with_context(obj_type='feed')._create_obj(mapping_obj, vals)


	@api.model
	def _match_feed(self, mapping_obj, domain, limit=None):
		return self._match_obj(mapping_obj, domain, limit)


	@api.model
	def _create_sync(self, vals):
		if self.debug=='enable':
			nvals = vals.copy()
			channel_vals = self.get_channel_vals()
			nvals.update(channel_vals)
			return self.env['channel.synchronization'].create(nvals)
		return self.env['channel.synchronization']


	@api.model
	def match_attribute_mappings(self, store_attribute_id=None,
	odoo_attribute_id=None,domain = None, limit=1):

		map_domain = self.get_channel_domain(domain)

		if store_attribute_id:
			map_domain += [('store_attribute_id', '=', store_attribute_id)]
		if odoo_attribute_id:
			map_domain += [('odoo_attribute_id', '=', odoo_attribute_id)]

		return self.env['channel.attribute.mappings'].search(map_domain, limit=limit)


	@api.model
	def match_attribute_value_mappings(self, store_attribute_value_id=None,
		attribute_value_id=None,domain = None, limit=1):

		map_domain = self.get_channel_domain(domain)
		if store_attribute_value_id:
			map_domain +=  [('store_attribute_value_id', '=', store_attribute_value_id)]
		if attribute_value_id:
			map_domain +=   [('odoo_attribute_value_id', '=', attribute_value_id)]
		return self.env['channel.attribute.value.mappings'].search(map_domain, limit=limit)


	@api.model
	def match_product_mappings(self, store_product_id=None, line_variant_ids=None,
			domain=None,limit=1,**kwargs):
		map_domain = self.get_channel_domain(domain)
		if store_product_id:
			map_domain+=[('store_product_id', '=', store_product_id), ]
		if line_variant_ids:
			map_domain += [('store_variant_id', '=', line_variant_ids)]
		if kwargs.get('default_code'):
			map_domain += [('default_code', '=', kwargs.get('default_code'))]
		if kwargs.get('barcode'):
			map_domain += [('barcode', '=', kwargs.get('barcode'))]
		#_logger.info("111===%r===="%(map_domain))
		return self.env['channel.product.mappings'].search(map_domain, limit=limit)


	@api.model
	def match_template_mappings(self, store_product_id = None, domain = None, limit = 1,**kwargs):
		map_domain = self.get_channel_domain(domain)
		if store_product_id:
			map_domain += [('store_product_id', '=', store_product_id)]
		if kwargs.get('default_code'):
			map_domain += [('default_code', '=', kwargs.get('default_code'))]
		if kwargs.get('barcode'):
			map_domain += [('barcode', '=', kwargs.get('barcode'))]
		return self.env['channel.template.mappings'].search(map_domain, limit=limit)


	@api.model
	def match_partner_mappings(self, store_id = None, _type='contact',domain=None, limit=1):
		map_domain = self.get_channel_domain(domain)+[('type', '=', _type)]
		if store_id:
			map_domain +=[('store_customer_id', '=', store_id)]
		return self.env['channel.partner.mappings'].search(map_domain, limit=limit)


	@api.model
	def match_order_mappings(self, store_order_id=None,domain=None, limit=1):
		map_domain = self.get_channel_domain(domain)
		if store_order_id:
			map_domain += [('store_order_id', '=', store_order_id)]
		return self.env['channel.order.mappings'].search(map_domain, limit=limit)


	@api.model
	def match_carrier_mappings(self, shipping_service_name=None, domain=None, limit=1):
		map_domain = self.get_channel_domain(domain)
		if shipping_service_name:
			map_domain +=[('shipping_service', '=', shipping_service_name)]
		return self.env['channel.shipping.mappings'].search(map_domain, limit=limit)


	@api.model
	def match_category_mappings(self, store_category_id=None,odoo_category_id=None, domain=None, limit=1):
		map_domain = self.get_channel_domain(domain)
		if store_category_id:
			map_domain += [('store_category_id', '=', store_category_id)]
		if odoo_category_id:
			map_domain += [('odoo_category_id', '=', odoo_category_id)]
		return self.env['channel.category.mappings'].search(map_domain, limit=limit)


	@api.model
	def match_category_feeds(self, store_id=None,domain=None,limit=1):
		map_domain = self.get_channel_domain(domain)
		if store_id:
			map_domain  += [('store_id', '=', store_id)]
		return self.env['category.feed'].search(map_domain, limit=limit)


	@api.model
	def match_product_feeds(self, store_id=None,domain=None,limit=1):
		map_domain = self.get_channel_domain(domain)
		if store_id:
			map_domain  += [('store_id', '=', store_id)]

		return self.env['product.feed'].search(map_domain, limit=limit)


	@api.model
	def match_product_variant_feeds(self, store_id=None,domain=None,limit=1):
		map_domain = self.get_channel_domain(domain)
		if store_id:map_domain  += [('store_id', '=', store_id)]
		map_domain+=[('feed_templ_id', '!=',False)]
		#_logger.info("=map_domain==%r==="%(map_domain))
		return self.env['product.variant.feed'].search(map_domain, limit=limit)


	@api.model
	def match_partner_feeds(self, store_id=None, _type='contact',domain=None,limit=1):
		map_domain = self.get_channel_domain(domain)+[('type', '=', _type)]
		if store_id:
			map_domain  += [('store_id', '=', store_id)]
		return self.env['partner.feed'].search(map_domain, limit=limit)
	@api.model
	def match_order_feeds(self, store_id=None,domain=None,limit=1):
		map_domain = self.get_channel_domain(domain)
		if store_id:
			map_domain  += [('store_id', '=', store_id)]

		return self.env['order.feed'].search(map_domain, limit=limit)

	@api.model
	def create_attribute_mapping(self, erp_id, store_id,store_attribute_name=''):
		self.ensure_one()
		if store_id and store_id not in ['0', -1]:
			vals = dict(
				store_attribute_id=store_id,
				store_attribute_name=store_attribute_name,
				odoo_attribute_id=erp_id.id,
				attribute_name=erp_id.id,
			)
			channel_vals = self.get_channel_vals()
			vals.update(channel_vals)
			return self.env['channel.attribute.mappings'].create(vals)
		return self.env['channel.attribute.mappings']

	@api.model
	def create_attribute_value_mapping(self, erp_id, store_id,store_attribute_value_name=''):
		self.ensure_one()
		if store_id and store_id not in ['0',' ', -1]:
			vals = dict(
				store_attribute_value_id=store_id,
				store_attribute_value_name=store_attribute_value_name,
				attribute_value_name=erp_id.id,
				odoo_attribute_value_id=erp_id.id,
			)
			channel_vals = self.get_channel_vals()
			vals.update(channel_vals)
			return self.env['channel.attribute.value.mappings'].create(vals)
		return self.env['channel.attribute.value.mappings']

	@api.model
	def create_partner_mapping(self, erp_id, store_id, _type):
		self.ensure_one()
		if store_id and store_id not in ['0', -1]:
			vals = dict(
				store_customer_id=store_id,
				odoo_partner_id=erp_id.id,
				odoo_partner=erp_id.id,
				type=_type,
			)
			channel_vals = self.get_channel_vals()
			vals.update(channel_vals)
			return self.env['channel.partner.mappings'].create(vals)
		return self.env['channel.partner.mappings']


	@api.model
	def create_carrier_mapping(self, name, service_id=None):
		carrier_obj = self.env['delivery.carrier']
		partner_id = self.env.user.company_id.partner_id
		carrier_vals = dict(
			product_id = self.delivery_product_id.id,
			name=name,
			fixed_price=0,
		)
		carrier_id = carrier_obj.sudo().create(carrier_vals)
		service_id = service_id or name
		vals = dict(
			shipping_service=name,
			shipping_service_id=service_id,
			odoo_carrier_id=carrier_id.id,
			odoo_shipping_carrier=carrier_id.id,
		)
		channel_vals = self.get_channel_vals()
		vals.update(channel_vals)
		self.sudo().env['channel.shipping.mappings'].create(vals)
		return carrier_id


	@api.model
	def create_template_mapping(self, erp_id, store_id, vals=None):
		self.ensure_one()
		vals =vals or dict()
		vals.update(dict(
			store_product_id=store_id,
			odoo_template_id=erp_id.id,
			template_name=erp_id.id,
			default_code=vals.get('default_code'),
			barcode=vals.get('barcode'),
		))
		channel_vals = self.get_channel_vals()
		vals.update(channel_vals)
		return self.env['channel.template.mappings'].create(vals)


	@api.model
	def default_multi_channel_values(self):
		return self.env['multi.channel.sale.config'].sudo().get_values()



	@api.model
	def match_odoo_template(self, vals,variant_lines):
		Template = self.env['product.template']
		record  = self.env['product.template']
		# Ensure barcode constraints first
		barcode =  vals.get('barcode')
		if barcode:
			record = Template.search([('barcode', '=', barcode)], limit=1)
		if not record:
			# Now check avoid_duplicity using default_code
			ir_values = self.default_multi_channel_values()
			default_code =  vals.get('default_code')
				#  and (not len(variant_lines))
			if ir_values.get('avoid_duplicity') and default_code:
				record = Template.search([('default_code', '=', default_code)], limit=1)
			if not record:
				# It's time to check the child
				for var in variant_lines:
					match  =self.match_odoo_product(var.read([])[0])
					if match:
						record= match.product_tmpl_id
		return record


	@api.model
	def match_odoo_product(self, vals, obj='product.product'):
		oe_env = self.env[obj]
		record = False
		# check avoid_duplicity using default_code
		barcode =  vals.get('barcode')
		if barcode:
			record = oe_env.search([('barcode', '=', barcode)], limit=1)
		if not record:
			default_code =  vals.get('default_code')
			ir_values = self.default_multi_channel_values()
			if ir_values.get('avoid_duplicity') and default_code:
				record = oe_env.search([('default_code', '=', default_code)], limit=1)
			if not record:
				if 'product_template_attribute_value_ids' in vals and 'product_tmpl_id' in vals:
					_ids = vals['product_template_attribute_value_ids'][0][2]
					ids = ','.join([str(i) for i in sorted(_ids)])
					domain = [('product_tmpl_id','=',vals['product_tmpl_id'])]
					if ids:
						domain += [('product_template_attribute_value_ids','in', _ids)]
					record = oe_env.search(domain) \
					.filtered(lambda prod: prod.product_template_attribute_value_ids._ids2str()==ids)
		return record


	@api.model
	def create_product_mapping(self, odoo_template_id, odoo_product_id,
		store_id, store_variant_id, vals=None):
		self.ensure_one()
		vals =dict(vals or dict())
		vals.update(dict(
			store_product_id=store_id,
			store_variant_id=store_variant_id,
			erp_product_id=odoo_product_id.id,
			product_name=odoo_product_id.id,
			odoo_template_id=odoo_template_id.id,
			default_code=vals.get('default_code'),
			barcode=vals.get('barcode'),
		))
		channel_vals = self.get_channel_vals()
		vals.update(channel_vals)
		#_logger.info("vals=%r==="%(vals))
		return self.env['channel.product.mappings'].create(vals)


	@api.model
	def create_category_mapping(self, erp_id, store_id, leaf_category=True):
		self.ensure_one()
		vals = dict(
			store_category_id=store_id,
			odoo_category_id=erp_id.id,
			category_name=erp_id.id,
			leaf_category=leaf_category,
		)
		channel_vals = self.get_channel_vals()
		vals.update(channel_vals)
		return self.env['channel.category.mappings'].create(vals)


	@api.model
	def create_order_mapping(self, erp_id, store_id,store_source=None):
		self.ensure_one()
		vals = dict(
			odoo_partner_id=erp_id.partner_id,
			store_order_id=store_id,
			store_id=store_source,
			odoo_order_id=erp_id.id,
			order_name=erp_id.id,
		)
		channel_vals = self.get_channel_vals()
		vals.update(channel_vals)
		return self.env['channel.order.mappings'].create(vals)


	@api.model
	def csv_pre_do_transfer(self, picking_id, mapping_ids):
		return True


	@api.model
	def csv_post_do_transfer(self, picking_id, mapping_ids, result):
		return True


	@api.model
	def csv_pre_confirm_paid(self, invoice_id, mapping_ids):
		return True


	@api.model
	def csv_post_confirm_paid(self, invoice_id, mapping_ids, result):
		return True


	def open_website_url(self, url, name='Open Website URL'):
		self.ensure_one()
		return {
			'name': name,
			'url': url,
			'type': 'ir.actions.act_url',
			'target': 'new',
		}

	def sync_order_feeds(self, vals,**kwargs):
		"""
			==Vals is a List of dictionaries==
			vals:list(dict(),dict())
			partner_vals:list(dict(),dict())
			category_vals:list(dict(),dict())
			product_vals:list(dict(),dict())
			channel_vals: dict(channel_id=id)
		"""
		self.ensure_one()
		message=''
		contextualize_data = dict()
		contextualize_data.update(dict(self.env['wk.feed'].contextualize_mappings('order',self.ids)._context))
		contextualize_data.update(dict(self.env['wk.feed'].contextualize_mappings('product',self.ids)._context))
		contextualize_data.update(dict(self.env['wk.feed'].contextualize_mappings('category',self.ids)._context))
		contextualize_data.update(dict(self.env['wk.feed'].contextualize_feeds('category',self.ids)._context))
		contextualize_data.update(dict(self.env['wk.feed'].contextualize_feeds('product',self.ids)._context))
		self = self.with_context(contextualize_data)
		try:
			partner_vals = kwargs.get('partner_vals')
			category_vals = kwargs.get('category_vals')
			product_vals = kwargs.get('product_vals')
			channel_vals = kwargs.get('channel_vals') or self.get_channel_vals()
			channel_vals.pop('ecom_store')
			if partner_vals:
				message += self.sync_partner_feeds(
					partner_vals,channel_vals= channel_vals).get('message','')
			if kwargs.get('category_vals'):
				message += self.sync_category_feeds(
					category_vals,channel_vals= channel_vals).get('message','')
			if kwargs.get('product_vals'):
				message += self.sync_product_feeds(
					product_vals,channel_vals= channel_vals).get('message','')
			ObjModel = self.env['order.feed']
			for val in vals :
				obj = ObjModel.search([('store_id','=',val.get('store_id'))])
				obj.write(dict(line_ids=[(6,0,[])]))
			res = self.create_model_objects(
				'order.feed',vals,extra_val= channel_vals)
			message += res.get('message','')
			data = res.get('data')
			if data:
				for data_item in data:
					import_res = data_item.import_order(self)
					message += import_res.get('message', '')
		except Exception as e:
			_logger.error("#SyncOrderFeeds Error  \n %r"%(e))
			message += '%r'%(e)
		return dict(
			kwargs = kwargs,
			message = message
		)

	def sync_partner_feeds(self, vals, **kwargs):
		self.ensure_one()
		channel_vals = kwargs.get('channel_vals') or self.get_channel_vals()
		res= self.create_model_objects('partner.feed', vals, extra_val= channel_vals)
		message = res.get('message','')
		data = res.get('data')
		if data:
			for data_item in data:
				import_res = data_item.import_partner(self)
				message += import_res.get('message', '')
		return dict(
			message = message
		)

	def sync_category_feeds(self, vals, **kwargs):
		self.ensure_one()
		channel_vals = kwargs.get('channel_vals') or self.get_channel_vals()
		res= self.create_model_objects('category.feed', vals, extra_val = channel_vals)
		message = res.get('message','')
		data = res.get('data')
		if data:
			for data_item in data:
				import_res = data_item.import_category(self)
				message += import_res.get('message', '')
		return dict(
			message = message
		)

	def sync_product_feeds(self, vals, **kwargs):
		self.ensure_one()
		channel_vals = kwargs.get('channel_vals') or self.get_channel_vals()
		res= self.create_model_objects('product.feed', vals, extra_val= channel_vals)
		context = dict(self._context)
		ObjModel = self.env['product.feed']
		for val in vals :
			obj = ObjModel.search([('store_id','=',val.get('store_id'))])
			obj.write(dict(feed_variants=[(6,0,[])]))
		res= self.with_context(context).create_model_objects('product.feed',vals,extra_val=channel_vals)
		message = res.get('message','')
		data = res.get('data')
		if data:
			for data_item in data:
				import_res = data_item.import_product(self)
				message += import_res.get('message', '')
		return dict(
			message = message
		)

	@staticmethod
	def read_website_image_url(image_url):
		data = None
		try:
			res = requests.get(image_url)
			if res.status_code == 200:
				data = binascii.b2a_base64((res.content))
		except Exception as e:
			_logger.error("#1ReadImageUrlError  \n %r"%(e))
		return data

	@staticmethod
	def get_operation_message_v1( obj='product', obj_model = 'feed' ,operation = 'created',obj_ids=None):
		"""
		Get message for operation .
		:param obj: model name ==> product , attribute , category
		:name obj_name: object name ==> feed ,mapping , object , record
		:operation: operation ==> created ,updated
		:obj_ids: list of object
		:return: message .
		"""
		obj_ids = obj_ids or []
		message = ''
		if len(obj_ids):
			message += '<br/>Total {count}  {obj} {obj_model}  {operation}.'.format(
				count = len(obj_ids), obj = obj, obj_model = obj_model , operation =operation)
		return message

	@staticmethod
	def get_feed_import_message( obj, create_ids=[], update_ids=[], map_create_ids=[], map_update_ids=[]):
		message = ''
		if map_create_ids or map_update_ids:
			if len(map_create_ids):
				message += '<br/>Total %s  new %s created.' % (
					len(map_create_ids), obj)
			if len(map_update_ids):
				message += '<br/>Total %s  %s updated.' % (
					len(map_update_ids), obj)
		else:
			if len(create_ids):
				message += '<br/>Total %s new %s feed created.' % (
					len(create_ids), obj)
			if len(update_ids):
				message += '<br/>Total %s  %s feed updated.' % (
					len(update_ids), obj)
			if not (len(create_ids) or len(update_ids)):
				message += '<br/>No  data imported/updated.'

		return message

	@api.model
	def _match_create_product_categ(self, vals):
		match = self.match_category_feeds(store_id= vals.get('store_id'))
		feed_obj = self.env['category.feed']
		update = False
		if match:
			vals['state'] = 'update'
			vals.pop('store_id','')
			update  = match.write(vals)
			data = match
		else:
			data = self._create_feed(feed_obj, vals)
		return dict(
			data = data,
			update = update
		)

	@api.model
	def get_channel_category_id(self,template_id,channel_id,limit=1):
		mapping_obj = self.env['channel.category.mappings']
		channel_category_ids = (template_id.channel_category_ids or
		template_id.categ_id.channel_category_ids)
		channel_categ = channel_category_ids.filtered(
			lambda cat:cat.instance_id==channel_id
		)
		extra_category_ids = channel_categ.mapped('extra_category_ids')
		domain = []
		if extra_category_ids:
			domain = [('odoo_category_id', 'in',extra_category_ids.ids)]
		return channel_id.match_category_mappings(domain=domain,limit=limit).mapped('store_category_id')

	@api.model
	def set_order_by_status(self,channel_id,store_id,
			status,order_state_ids,default_order_state,
			payment_method = None):
		result = dict(
			order_match  = None,
			message = ''
		)
		order_match = channel_id.match_order_mappings(store_id)
		order_state_ids = order_state_ids.filtered(
			lambda state: state.channel_state == status)
		if order_state_ids:
			state = order_state_ids[0]
		else:
			state = default_order_state
		if order_match  and order_match.order_name.state =='draft' and (
				state.odoo_create_invoice or state.odoo_ship_order):
			result['message'] += self.env['multi.channel.skeleton']._SetOdooOrderState(
				order_match.order_name, channel_id,  status, payment_method
			)
			result['order_match']=order_match
		return result

	@staticmethod
	def get_image_type(image_data):
		image_stream = BytesIO(codecs.decode(image_data, 'base64'))
		image = Image.open(image_stream)
		image_type = image.format.lower()
		if not image_type:
			image_type='jpg'
		return image_type

	@api.model
	def cron_feed_evaluation(self):
		for object_model in  ["category.feed","product.feed","partner.feed","order.feed"]:

			records = self.env[object_model].search([
				("state","!=","done"),
				("channel_id.state","=","validate")
			])
			records.with_context(channel_id=records.mapped("channel_id")).import_items()
		return True

	@api.model
	def cron_import_all(self,model):
		config_ids = self.env['multi.channel.sale'].search([("state","=","validate")])
		for config_id in config_ids:
			if model == "order" and config_id.import_order_cron:
				if hasattr(config_id, "{}_import_order_cron".format(config_id.channel)):
					getattr(config_id,"{}_import_order_cron".format(config_id.channel))()
				else:
					_logger.warn('Error in use of MultiChannelSale class : use of (%r)_import_order_cron function to import orders from channel to odoo',config_id.channel)
			elif model == "product" and config_id.import_product_cron:
				if hasattr(config_id, "{}_import_product_cron".format(config_id.channel)):
					getattr(config_id,"{}_import_product_cron".format(config_id.channel))()
				else:
					_logger.warn('Error in use of MultiChannelSale class : use of (%r)_import_product_cron function to import orders from channel to odoo',config_id.channel)
			elif model == "partner" and config_id.import_partner_cron:
				if hasattr(config_id, "{}_import_partner_cron".format(config_id.channel)):
					getattr(config_id,"{}_import_partner_cron".format(config_id.channel))()
				else:
					_logger.warn('Error in use of MultiChannelSale class : use of (%r)_import_partner_cron function to import orders from channel to odoo',config_id.channel)
			elif model == "category" and config_id.import_category_cron:
				if hasattr(config_id, "{}_import_category_cron".format(config_id.channel)):
					getattr(config_id,"{}_import_category_cron".format(config_id.channel))()
				else:
					_logger.warn('Error in use of MultiChannelSale class : use of (%r)_import_category_cron function to import orders from channel to odoo',config_id.channel)
		return True

