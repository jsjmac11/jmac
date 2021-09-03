# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models


class StockPicking(models.Model):
	_inherit = 'stock.picking'

	def _action_done(self):
		for rec in self:
			rec.wk_pre_do_transfer()
			result = super(StockPicking, rec)._action_done()
			rec.wk_post_do_transfer(result)


	def wk_pre_do_transfer(self):
		if self.sale_id:
			mapping_ids = self.sale_id.channel_mapping_ids
			if mapping_ids:
				channel_id = mapping_ids[0].channel_id
				if hasattr(channel_id,'%s_pre_do_transfer'%channel_id.channel) and channel_id.sync_shipment:
					getattr(channel_id,'%s_pre_do_transfer'%channel_id.channel)(self,mapping_ids)

	def wk_post_do_transfer(self,result):
		if self.sale_id:
			mapping_ids = self.sale_id.channel_mapping_ids
			if mapping_ids:
				channel_id = mapping_ids[0].channel_id
				if hasattr(channel_id,'%s_post_do_transfer'%channel_id.channel) and channel_id.sync_shipment:
					getattr(channel_id,'%s_post_do_transfer'%channel_id.channel)(self,mapping_ids,result)
