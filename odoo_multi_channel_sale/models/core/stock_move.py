# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models
from logging import getLogger

_logger = getLogger(__name__)


class StockMove(models.Model):
	_inherit = 'stock.move'

	def _action_done(self, **kwargs):
		"""
			Makes the move done and if all moves are done,it will finish the picking.
			@return:
		"""
		res = super()._action_done(**kwargs)
		self.post_operation(stock_operation='_action_done')
		return res

	def _action_confirm(self, *args, **kwargs):
		""" Confirms stock move or put it in waiting if it's linked to another move.
		"""
		res = super()._action_confirm(*args, **kwargs)
		self.post_operation(stock_operation='_action_confirm')
		return res

	def _action_cancel(self, *args, **kwargs):
		cancelled = self.filtered(lambda self: self.state == 'cancel')
		res = super()._action_cancel(*args, **kwargs)
		if not cancelled:
			self.post_operation(stock_operation='_action_cancel')
		return res

	def post_operation(self, stock_operation):
		initial_channel_ids = self.env['multi.channel.sale'].search([]).ids
		for move in self:
			channel_ids = initial_channel_ids.copy()

			product_id = move.product_id
			if move.origin and move.picking_type_id.code == 'outgoing':
				sale_id = self.env['sale.order'].search([('name','=',move.origin)])
				if sale_id:
					channel_id = sale_id.channel_mapping_ids.channel_id
					if channel_id and channel_id.id in channel_ids:
						channel_ids.remove(channel_id.id)

			if channel_ids:
				source_location_id = move.location_id
				dest_location_id = move.location_dest_id

				for mapping in product_id.channel_mapping_ids:
					channel_id = mapping.channel_id
					if not channel_id.auto_sync_stock:
						continue
					if channel_id.channel_stock_action == 'qoh':
						if stock_operation == '_action_confirm':
							continue
					else:
						if stock_operation == '_action_done':
							continue
					location_ids = channel_id.location_id + channel_id.location_id.child_ids
					if source_location_id in location_ids or dest_location_id in location_ids:
						qty = channel_id.get_quantity(product_id)
						sync_quantity_channel = getattr(channel_id,'sync_quantity_%s'%channel_id.channel,None)
						if sync_quantity_channel:
							sync_quantity_channel(mapping, qty)
						else:
							_logger.error('Auto Sync Quantity method not found for %s',channel_id.channel)

	def multichannel_sync_quantity(self,pick_details):
		"""
			: Deprecated
			Method to be overridden by the multichannel modules to provide real time stock update feature
		"""
		pass
