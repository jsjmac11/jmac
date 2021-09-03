# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE URL <https://store.webkul.com/license.html/> for full copyright and licensing details.
#################################################################################

from odoo import api, fields, models, _
from odoo.exceptions import  UserError,RedirectWarning, ValidationError ,Warning
from odoo.addons.amazon_odoo_bridge import const
from odoo.addons.odoo_multi_channel_sale import tools as mtools

import logging
_logger = logging.getLogger(__name__)


class ExportMwsProducts(models.TransientModel):
    _inherit = ['export.templates']

    def compute_product_count(self):
        for record in self:
            record.processed = len(record.product_tmpl_ids)

    def _get_feed_type(self):
        update = [
            # ('image','Image'),
            # ('relationship','Relationship'),
            ('price_quantity','Price + Quantity'),
            # ('price_quantity_image','Price + Quantity+Image'),
        ]
        return update

    feed_type = fields.Selection(
        selection = _get_feed_type,
        string='Feed Type',
        default='price_quantity',
    )
    feed_type_product = fields.Selection(
        selection = [('product','Product')],
        string='Product Type',
        default='product',
    )
    processed = fields.Integer(
        string='Processed',
        compute='compute_product_count'
    )
    amazon_category_id = fields.Many2one(
        related='channel_id.mws_default_product_categ_id',
        string = 'Default Export Product Category'
    )

    def mws_submit_create_feed(self):
        Feed  = self.env['mws.feed']
        Operation  = self.env['channel.operation']
        excl_tmpl_barcode_ids =  self.env['product.template']
        ex_create_ids,ex_update_ids,create_ids,update_ids= [],[],[],[]
        feed_ids=[]
        message=''
        for record in self:
            sync_vals = dict(
                status ='error',
                action_on ='template',
                action_type ='export',
            )
            channel_id = record.channel_id
            exclude_res=Operation.exclude_export_data(record.product_tmpl_ids,channel_id,'export')
            tmpl_ids=self.env['product.template']
            for template in exclude_res.get('object_ids'):
                product_variant_ids = template.product_variant_ids
                variant_ids = product_variant_ids.filtered(
                    lambda var:
                    (var.wk_product_id_type !='wk_asin' and (var.barcode not in [None , False,''])) or
                    (var.wk_product_id_type =='wk_asin' and (var.wk_asin not in [None , False,'']) )
                )
                if len(variant_ids)==len(product_variant_ids):
                    tmpl_ids+=template
                else:
                    excl_tmpl_barcode_ids+=template
            if not len(tmpl_ids):
                # pass
                message+='No product template filter for exported over amazon.Please ensure the barcode must exits and they are not already exported.'
            else:
                vals = dict(
                    state='submit',
                    channel_id=channel_id.id,
                    product_tmpl_ids=[(6,0,tmpl_ids.ids)]
                )
                wk_feed_obj = Feed.create(vals)
                node_id = self.amazon_category_id.store_category_id
                sequence_id = self.sku_sequence_id
                product_feed_res=wk_feed_obj.post_product_data(tmpl_ids,channel_id,node_id,sequence_id)
                message +=  product_feed_res.get('message')
                feed_id = product_feed_res.get('feed_id')
                if feed_id:
                    wk_feed_obj.feed_id=feed_id
                    feed_ids+=[wk_feed_obj]
                    sync_vals['status'] = 'success'
                    sync_vals['ecomstore_refrence'] =feed_id
                    sync_vals['summary'] = 'Product Post Feed Request send to amazon.'
                sync_vals['odoo_id'] = tmpl_ids.ids
                channel_id._create_sync(sync_vals)
                # Feed.post_odoo_feed(product_tmpl_ids, channel_id, 'image')
                Feed.post_odoo_feed(tmpl_ids,channel_id, 'inventory')
                Feed.post_odoo_feed(tmpl_ids,channel_id,'price')
                # Feed.post_odoo_feed(product_tmpl_ids, channel_id,'relationship')

        if len(feed_ids):
            return {
                'type': 'ir.actions.act_window',
                'name': 'Feeds',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'mws.feed',
                'domain': [('id', 'in', mtools.MapId(feed_ids))],
                'target': 'current',
            }
        else:
            if len(excl_tmpl_barcode_ids):
               message += '<br/> Total %s  template  not exported because of missing barcode .'%(len(excl_tmpl_barcode_ids))
            message+=self.export_message(ex_create_ids,ex_update_ids,create_ids,update_ids)
            return self.env['multi.channel.sale'].display_message(message)

    def mws_submit_update_feed(self):
        Feed  = self.env['mws.feed']
        Operation  = self.env['channel.operation']
        ex_create_ids,ex_update_ids,create_ids,update_ids= [],[],[],[]
        context = dict(self._context)
        mws_update_image = context.get('mws_update_image')
        mws_update_relationship = context.get('mws_update_relationship')
        mws_update_qty = context.get('mws_update_qty')
        mws_post_product_price = context.get('mws_update_price')

        feed_ids=[]
        message=''
        for record in self:
            channel_id =  record.channel_id
            exclude_res=Operation.exclude_export_data(record.product_tmpl_ids,channel_id,'update')
            product_tmpl_ids=exclude_res.get('object_ids')
            ex_update_ids+=exclude_res.get('ex_update_ids')
            ex_create_ids+=exclude_res.get('ex_create_ids')
            if len(product_tmpl_ids):
                if mws_update_image:
                    inventory_feed_res =Feed.post_odoo_feed(product_tmpl_ids,channel_id,'image')
                    message +=  inventory_feed_res.get('message')
                    feed_ids += inventory_feed_res.get('feed_id')
                if mws_update_qty:
                    inventory_feed_res =Feed.post_odoo_feed(product_tmpl_ids,channel_id,'inventory')
                    message +=  inventory_feed_res.get('message')
                    feed_ids += inventory_feed_res.get('feed_id')
                if mws_post_product_price:
                    price_feed_res = Feed.post_odoo_feed(product_tmpl_ids,channel_id,'price')
                    message +=  price_feed_res.get('message')
                    feed_ids+= price_feed_res.get('feed_id')
                if mws_update_relationship:
                    price_feed_res = Feed.post_odoo_feed(product_tmpl_ids,channel_id,'relationship')
                    message +=  price_feed_res.get('message')
                    feed_ids+= price_feed_res.get('feed_id')

        if len(feed_ids):
            return {
                'name': _('Feed'),
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'mws.feed',
                'view_id': False,
                'type': 'ir.actions.act_window',
                'domain': [('id', 'in', mtools.MapId(feed_ids))],
            }
        else:
            message+=self.export_message(ex_create_ids,ex_update_ids,create_ids,update_ids)
            return self.env['multi.channel.sale'].display_message(message)
