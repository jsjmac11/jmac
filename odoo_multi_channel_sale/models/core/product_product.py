# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models
import odoo.addons.decimal_precision as dp


class ProductProduct(models.Model):
	_inherit = 'product.product'

	@api.depends('wk_extra_price')
	def _get_price_extra(self):
		for product in self:
			price_extra = 0.0
			for value_id in product.product_template_attribute_value_ids:
				if value_id.product_tmpl_id.id == product.product_tmpl_id.id:
					price_extra += value_id.price_extra
			product.price_extra = price_extra + product.wk_extra_price
			product.attr_price_extra = price_extra


	channel_mapping_ids = fields.One2many(
		string       = 'Mappings',
		comodel_name = 'channel.product.mappings',
		inverse_name = 'product_name',
		copy         = False
	)

	wk_extra_price  = fields.Float(
		string = 'Extra Price',
		digits = 'Product Price',
	)

	price_extra  = fields.Float(
		string  = 'Price Extra',
		compute = _get_price_extra,
		digits  = 'Product Price',
		help    = "This shows the sum of all attribute price and additional price of variant (All Attribute Price+Additional Variant price)",
	)

	attr_price_extra  = fields.Float(
		string  = 'Variant Extra Price',
		compute = _get_price_extra,
		digits  = 'Product Price',
	)

	def write(self, vals):
		for record in self:
			mapping_ids = record.channel_mapping_ids
			vals = record.pre_product_write(vals, mapping_ids)
			mapping_ids.write({'need_sync': 'yes'})
			res = super(ProductProduct, record).write(vals)
			record.post_product_write(vals, mapping_ids)
		return res

	def pre_product_write(self, vals, mapping_ids):
		r""" Adds functionality to modify product Vals
			Return vals
		"""

		_channel_ids = self.env['multi.channel.sale']
		for product_mapping in mapping_ids:
			channel_id = product_mapping.channel_id
			_channel_ids |= channel_id
			if hasattr(channel_id,'%s_mapped_pre_product_write'%channel_id.channel):
				vals.update(getattr(
					channel_id,'%s_mapped_pre_product_write'%channel_id.channel
				)(self, product_mapping, vals) or vals)

		channel_ids = self.env['multi.channel.sale'].search([
						('state','=','validate'),
						('id', 'not in', _channel_ids.ids)])
		for channel_id in channel_ids:
			if hasattr(channel_id,'%s_pre_product_write'%channel_id.channel):
				vals.update(getattr(
					channel_id,'%s_pre_product_write'%channel_id.channel
				)(self, vals) or vals)
		return vals

	def post_product_write(self, vals, mapping_ids):
		r"""Adds functionality after product write is called
			Return True
		"""

		_channel_ids = self.env['multi.channel.sale']
		for product_mapping in mapping_ids:
			channel_id = product_mapping.channel_id
			_channel_ids |= channel_id
			if hasattr(channel_id,'%s_mapped_post_product_write'%channel_id.channel):
				vals.update(getattr(
					channel_id,'%s_mapped_post_product_write'%channel_id.channel
				)(self, product_mapping, vals) or vals)

		channel_ids = self.env['multi.channel.sale'].search([
						('state','=','validate'),
						('id', 'not in', _channel_ids.ids)])
		for channel_id in channel_ids:
			if hasattr(channel_id,'%s_post_product_write'%channel_id.channel):
				vals.update(getattr(
					channel_id,'%s_post_product_write'%channel_id.channel
				)(self, vals) or vals)
		return True

	@api.model
	def check_for_new_price(self,template_id,value_id,price_extra):
		exists = self.env['product.template.attribute.value'].search(
			[
				('product_tmpl_id','=',template_id),
				('product_attribute_value_id','=',value_id)
			]
		)
		if exists:
			exists.write({'price_extra': price_extra})
			return exists
		else:
			pal_id = self.env['product.template.attribute.value'].create(
				{
					'product_tmpl_id'           : template_id,
					'product_attribute_value_id': value_id,
					'price_extra'               : price_extra
				}
			)
			return pal_id

	@api.model
	def get_product_attribute_id(self,attribute_id):
		context = self._context or {}
		product_attribute_id = 0
		store_attribute_id = attribute_id.get('attrib_name_id') or attribute_id.get('name')

		channel_id = context.get('channel_id')
		if not isinstance(channel_id, int):
			channel_id = channel_id.id

		attribute_mapping = self.env['channel.attribute.mappings'].search(
			[
				('channel_id','=',channel_id),
				('store_attribute_id','=',store_attribute_id)
			],
			limit=1
		)

		if attribute_mapping:
			product_attribute_id = attribute_mapping.odoo_attribute_id
		else:
			product_attribute = self.env['product.attribute'].search(
				[('name','=',attribute_id.get('name'))]
			)
			if product_attribute:
				product_attribute_id = product_attribute[0].id
			else:
				product_attribute_id = self.env['product.attribute'].create(
					{'name': attribute_id.get('name')}
				).id

			self.env['channel.attribute.mappings'].create(
				{
					'store_attribute_id'  : store_attribute_id,
					'store_attribute_name': attribute_id.get('name'),
					'attribute_name'      : product_attribute_id,
					'odoo_attribute_id'   : product_attribute_id,
					'channel_id'          : context.get('channel_id').id,
					'ecom_store'          : context.get('channel')
				}
			)
		return product_attribute_id

	@api.model
	def get_product_attribute_value_id(self,attribute_id,product_attribute_id,template_id):
		context = dict(self._context or {})
		product_attribute_value_id = 0
		store_attribute_value_id = attribute_id.get('attrib_value_id') or attribute_id.get('value')

		channel_id = context.get('channel_id')
		if not isinstance(channel_id, int):
			channel_id = channel_id.id
		attribute_value_mapping = self.env['channel.attribute.value.mappings'].search(
			[
				('channel_id','=',channel_id),
				('store_attribute_value_id','=',store_attribute_value_id),
				('attribute_value_name.attribute_id','=',product_attribute_id)
			],
			limit=1
		)

		if attribute_value_mapping:
			product_attribute_value_id = attribute_value_mapping.odoo_attribute_value_id
		else:
			product_attribute_value = self.env['product.attribute.value'].search(
				[
					('name','=',attribute_id.get('value')),
					('attribute_id','=',product_attribute_id),
				]
			)
			if product_attribute_value:
				product_attribute_value_id = product_attribute_value[0].id
			else:
				context['active_id']       = template_id.id
				product_attribute_value_id = self.env[
					'product.attribute.value'
				].with_context(context).create(
					{
						'name'        : attribute_id.get('value'),
						'attribute_id': product_attribute_id
					}
				).id
			self.env['channel.attribute.value.mappings'].create(
				{
					'store_attribute_value_id'  : store_attribute_value_id,
					'store_attribute_value_name': attribute_id.get('value'),
					'attribute_value_name'      : product_attribute_value_id,
					'odoo_attribute_value_id'   : product_attribute_value_id,
					'channel_id'                : context.get('channel_id').id,
					'ecom_store'                : context.get('channel')
				}
			)
		return product_attribute_value_id

	def check_for_new_attrs(self,template_id,variant):
		context                = dict(self._context or {})
		product_template       = self.env['product.template']
		product_attribute_line = self.env['product.template.attribute.line']
		all_values             = []
		attributes             = variant.name_value

		for attribute_id in eval(attributes):
			product_attribute_id       = self.get_product_attribute_id(attribute_id)
			product_attribute_value_id = self.get_product_attribute_value_id(
				attribute_id,
				product_attribute_id,
				template_id
			)

			exists = product_attribute_line.search(
				[
					('product_tmpl_id','=',template_id.id),
					('attribute_id','=',product_attribute_id)
				]
			)
			if exists:
				pal_id = exists[0]
			else:
				pal_id = product_attribute_line.create(
					{
						'product_tmpl_id': template_id.id,
						'attribute_id'   : product_attribute_id,
						'value_ids'      : [[4,product_attribute_value_id]]
					}
				)

			value_ids = pal_id.value_ids.ids
			if product_attribute_value_id not in value_ids:
				pal_id.write({'value_ids': [[4,product_attribute_value_id]]})

			product_template_attribute_value_id = self.with_context(context).check_for_new_price(
				template_id.id,
				product_attribute_value_id,
				attribute_id.get('price')
			)
			all_values.append(product_template_attribute_value_id.id)
		return [(6,0,all_values)]
