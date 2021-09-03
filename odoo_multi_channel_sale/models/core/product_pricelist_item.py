# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models
from logging import getLogger

_logger = getLogger(__name__)


class PricelistItem(models.Model):
	_inherit = 'product.pricelist.item'

	def write(self, vals):
		for rec in self:
			rec.product_tmpl_id.channel_mapping_ids.write({'need_sync': 'yes'})
			rec.product_id.channel_mapping_ids.write({'need_sync': 'yes'})
			rec.product_id.product_tmpl_id.channel_mapping_ids.write({'need_sync': 'yes'})
		return super().write(vals)
