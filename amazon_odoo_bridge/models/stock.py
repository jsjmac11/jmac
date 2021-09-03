# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE URL <https://store.webkul.com/license.html/> for full copyright and licensing details.
#################################################################################
from itertools import groupby
from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def multichannel_sync_quantity(self, pick_details):
        channel_list = self._context.get('channel_list', [])
        channel_list.append('amazon')
        return super(
            StockMove, self.with_context(channel_list=channel_list)
        ).multichannel_sync_quantity(pick_details)
        
    @api.model
    def sync_amazon_item(self, channel_id, mapping, product_qty):
        result = {'data': {}, 'message': ''}
        store_id = mapping.store_product_id
        sku = mapping.default_code
        report_id = self.env['mws.report'].search(
            [('channel_id', '=', channel_id.id), ('state', '=', 'receive')], limit=1, order='id desc'
        )
        product_res = self.env['import.mws.products'].fetch_mws_products(channel_id,
                                                                         report_id, mapping.store_product_id, 'product_ids').get('data')
        if product_res:
            qty_available = int(product_res.get(
                mapping.store_product_id, {}).get('quantity') or '0')
            qty_available += product_qty
            if qty_available:
                items = dict(
                    default_code=sku,
                    qty_available=qty_available
                )
                feed_id = self.env['mws.feed'].update_inventory(
                    [items], channel_id)
        return result

    @api.model
    def sync_amazon_items(self, mappings, product_qty, source_loc_id, dest_loc_id):
        mapping_items = groupby(mappings, lambda item: item.channel_id)
        message = ''
        for channel_id, mapping_item in groupby(mappings, lambda item: item.channel_id):
            product_qty = channel_id.location_id.id == dest_loc_id and product_qty or - \
                (product_qty)
            product_mapping = list(mapping_item)
            for mapping in product_mapping:
                sync_res = self.sync_amazon_item(
                    channel_id, mapping, product_qty)
                message += sync_res.get('message')
        return True

    # def synch_quantity(self, pick_details):
    #     product_id = pick_details.get('product_id')
    #     product_qty = pick_details.get('product_qty')
    #     source_loc_id = pick_details.get('source_loc_id')
    #     dest_loc_id = pick_details.get('location_dest_id')
    #     channel_ids = pick_details.get('channel_ids')
    #     product_obj = self.env['product.product'].browse(pick_details.get('product_id'))
    #     channels = self.env['multi.channel.sale'].search(
    #         [('id','in',channel_ids),('channel','=','amazon'),('auto_sync_stock','=',True)],
    #     )
    #     mappings = product_obj.channel_mapping_ids.filtered(
    #         lambda m:m.channel_id in channels
    #         and m.channel_id.location_id.id in [source_loc_id,dest_loc_id]
    #     )
    #     if mappings:
    #         self.sync_amazon_items(mappings,product_qty,source_loc_id,dest_loc_id)
    #     return super(StockMove,self).synch_quantity(pick_details)
