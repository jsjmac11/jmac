# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from dateutil.relativedelta import relativedelta
from odoo import api,fields,models
from logging import getLogger
_logger=getLogger(__name__)


MappingModelData=dict(
	template=dict(
		model='channel.template.mappings',
		mapped_name='template_name',
		mapped_id='odoo_template_id'
	),
	product=dict(
		model='channel.product.mappings',
		mapped_name='product_name',
		mapped_id='erp_product_id'
	),
	category=dict(
		model='channel.category.mappings',
		mapped_name='category_name',
		mapped_id='odoo_category_id'
	),
	attribute=dict(
		model='channel.attribute.mappings',
		mapped_name='attribute_name',
		mapped_id='odoo_attribute_id'
	),
	attribute_value=dict(
		model='channel.attribute.value.mappings',
		mapped_name='attribute_value_name',
		mapped_id='odoo_attribute_value_id'
	)
)


class ChannelOperation(models.TransientModel):
	_name        = 'channel.operation'
	_description = 'Channel Operation'

	channel         =fields.Selection(related='channel_id.channel')
	api_record_limit=fields.Integer(related='channel_id.api_record_limit')

	wk_from_date=fields.Datetime.to_string(
		fields.Datetime.from_string(
			fields.Datetime.now()
		) + relativedelta(months=-1)
	)
	wk_to_date=fields.Datetime.to_string(
		fields.Datetime.from_string(
			fields.Datetime.now()
		) + relativedelta(minutes=-5)
	)
	from_date=fields.Datetime('From Date',default=wk_from_date,help='From Date')
	to_date  =fields.Datetime('To Date',default=wk_to_date,help='To Date')

	channel_id=fields.Many2one(
		comodel_name='multi.channel.sale',
		string      ='Channel ID',
		required    =True,
		domain      =[('state','=','validate')]
	)
	import_order_date=fields.Datetime(
		string ='Order Created After',
		related='channel_id.import_order_date'
	)
	update_order_date=fields.Datetime(
		string ='Order Updated After',
		related='channel_id.update_order_date'
	)
	import_product_date=fields.Datetime(
		string ='Product Created After',
		related='channel_id.import_product_date'
	)
	update_product_date=fields.Datetime(
		string ='Product Updated After',
		related='channel_id.update_product_date'
	)
	import_customer_date=fields.Datetime(
		string ='Customer Created After',
		related='channel_id.import_customer_date'
	)
	update_customer_date=fields.Datetime(
		string ='Customer Updated After',
		related='channel_id.update_customer_date'
	)


	@api.model
	def _get_ecom_store_domain(self):
		res=[]
		if self._context.get('active_model')=='multi.channel.sale':
			if self._context.get('active_id'):
				res+=[('channel_id','=',self._context.get('active_id'))]
		if self._context.get('wk_channel_id'):
			res+=[('channel_id','=',self._context.get('wk_channel_id'))]
		return res

	@api.model
	def default_get(self,fields):
		res=super(ChannelOperation,self).default_get(fields)
		if not res.get('channel_id') and self._context.get('active_model')=='multi.channel.sale':
			if self._context.get('active_id'):
				res['channel_id']=self._context.get('active_id')
		return res

	def _get_channel_obj(self):
		channel_obj=self.env["multi.channel.sale"].browse(
				self._context.get('active_id'))
		return channel_obj

	@api.model
	def post_feed_import_process(self,channel_id,feed_res):
		"""feed_res=dict(create_ids=[],update_ids=[order.feed(1),order.feed(2)])"""
		create_ids,update_ids,map_create_ids,map_update_ids=[],[],[],[]
		create_ids+=feed_res.get('create_ids',[])
		update_ids+=feed_res.get('update_ids',[])
		context=dict(self._context)
		context['get_mapping_ids']=1
		message=''
		if channel_id.auto_evaluate_feed:
			for feed_id in (create_ids+update_ids):
				try:
					mapping_res=feed_id.with_context(context).import_items()
					map_create_ids+=mapping_res.get('create_ids')
					map_update_ids+=mapping_res.get('update_ids')
				except Exception as e:
					_logger.info("==%r=post_feed_import_process==="%(e))
					message += '%s'%(e)
		return dict(
			create_ids    =create_ids,
			update_ids    =update_ids,
			map_create_ids=map_create_ids,
			map_update_ids=map_update_ids,
			message       =message
		)

	@api.model
	def exclude_export_data(self,object_ids,channel_id,operation,model='template',domain=[]):
		ex_update_ids=[]
		ex_create_ids=[]
		match        =[]

		model_data =MappingModelData.get(model)
		mapping_obj=self.env[model_data.get('model')]
		domain     += [(model_data.get('mapped_id'), 'in',object_ids.ids)]
		mapped     =model_data.get('mapped_name')
		if mapped:
			match=channel_id._match_mapping(mapping_obj,domain).mapped(mapped)
		if operation =='export':
			ex_create_ids += match
			object_ids=object_ids.filtered(lambda obj:obj not in match )
		else:
			ex_update_ids += list(set(object_ids)-set(match))
			object_ids=match
		return dict(
			ex_update_ids=ex_update_ids,
			ex_create_ids=ex_create_ids,
			object_ids   =object_ids
		)

	@staticmethod
	def export_message(ex_create_ids=[],ex_update_ids=[],create_ids=[],update_ids=[]):
		message=''
		if len(ex_create_ids):
			message+='<br/> Total %s product template are already exported.'%(len(ex_create_ids))
		if len(ex_update_ids):
			message+='<br/> Total %s product template not updated because there mapping not exits.'%(len(ex_update_ids))
		if len(create_ids):
			message+='<br/> Total %s product template exported.'%(len(create_ids))
		if len(update_ids):
			message+='<br/> Total %s product template updated.'%(len(update_ids))
		return message
