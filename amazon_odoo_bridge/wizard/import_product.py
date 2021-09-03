# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE URL <https://store.webkul.com/license.html/> for full copyright and licensing details.
#################################################################################

import requests
import binascii
from operator import itemgetter
import logging
_logger = logging.getLogger(__name__)

from odoo import api, fields, models, _
from odoo.exceptions import  UserError,RedirectWarning, ValidationError
from odoo.addons.amazon_odoo_bridge.tools.tools import extract_item as ET
from odoo.addons.amazon_odoo_bridge.tools.tools import chunks
from odoo.addons.amazon_odoo_bridge.tools.tools import CHANNELDOMAIN
from odoo.addons.amazon_odoo_bridge.tools.tools import JoinList as JL

PRODUCT_ID_TYPE=[
    ('1','wk_asin'),
    ('2','wk_isbn'),
    ('3','wk_upc'),
    ('4','wk_ean')
]

class ImportMwsProducts(models.TransientModel):
    _inherit = ['import.products']
    _name = "import.mws.products"

    report_id = fields.Many2one(
        string='Report',
        comodel_name='mws.report',
        domain=[
            ('state','=','receive'),
            ('report_type','in', ['OPEN_LISTINGS_MERCHANT_LISTINGS']),
            ('ml_data','!=',False),
            ('data','!=',False),
        ]
    )
    domain= lambda self:[('state','=','receive')]

    @api.model
    def default_get(self,fields):
        res=super(ImportMwsProducts,self).default_get(fields)
        context = dict(self._context)
        params =context.get('params',{})
        active_id = context.get('active_id') or params.get('id')
        model = 'multi.channel.sale'
        if (active_id and
            (context.get('active_model')==model or params.get('model')==model)):
            context['channel_id'] = active_id
            report_status = self.channel_id.with_context(context).mws_ensure_report()
            report_id = report_status.get('report_id')
            if report_status.get('message'):
                action_id = self.env.ref('amazon_odoo_bridge.action_reports').id
                raise RedirectWarning(report_status.get('message'), action_id, _('Go to the report panel.'))
        return res

    @staticmethod
    def get_mws_product_attribute( rel_key, rel_data):
        """ rel_key : VariationParent , VariationChild"""
        res = {}
        data = dict(rel_data)
        for key, val in data.items():
            if key == 'Identifiers':
                res[rel_key] = ET(
                    val.get('MarketplaceASIN', {}).get('ASIN', {}))
            else:
                if key in ['Size', 'Color']:res[key] = ET(val) #For multi-variant type
        return res

    @classmethod
    def extract_mws_product_rel_data(cls, product):
        res = {}

        for rel_key, rel_data in product.get('Relationships', {}).items():
            if isinstance(rel_data, dict):  # single Variation
                attribute = cls.get_mws_product_attribute(rel_key, rel_data)
                res[attribute.get(rel_key, 'undefined')] = attribute
            elif isinstance(rel_data, list):  # multi Variation
                for variation in rel_data:
                    attribute = cls.get_mws_product_attribute(rel_key, variation)
                    res[attribute.get(rel_key, 'undefined')] = attribute
        return res

    @classmethod
    def get_mws_product_parent_data_for_asin(cls, asin, api_sdk):
        parents = api_sdk.get_mws_product_by_asins([asin])
        product = parents.get('data', {}).get('Product', {})
        return cls.extract_mws_product_rel_data(product)

    @classmethod
    def process_mws_product_data(cls, product,api_sdk):
        asin = ET(product.get('ASIN'))
        product = product.get('Product', {})
        res = {}
        res.update(product.get('AttributeSets', {}))
        rel_id = cls.extract_mws_product_rel_data(product)
        for rel_id_key in rel_id.keys():
            variation_attr = cls.get_mws_product_parent_data_for_asin(rel_id_key,api_sdk).get(asin)
            if variation_attr and variation_attr.pop('VariationChild', None):
                res['parent_asin'] = rel_id_key
            if variation_attr and variation_attr.pop('VariationParent', None):
                res['child_asin'] = rel_id_key
            res['feed_variants'] = variation_attr
            break
        return res

    @classmethod
    def get_mws_product_data(cls, asins,channel_id):
        res={}
        api_sdk = channel_id.get_mws_api_sdk()
        products =api_sdk.get_mws_product_by_asins(asins).get('data', {})
        if isinstance(products,list):
            for record in products:
                res[ET(record.get('ASIN'))] = cls.process_mws_product_data(record,api_sdk)
        else:
            res[ET(products.get('ASIN'))] = cls.process_mws_product_data(products,api_sdk)
        return res


    @staticmethod
    def merge_sku_asin_data(asin_key_data,sku_key_data,header):
        # data = sku_key_data.copy()
        asin_dict =  dict(filter(itemgetter(0), asin_key_data.items()))
        data = dict()
        for sku , sku_data in sku_key_data.items():
            asin = sku_data.get(header.get('asin')) if header.get('asin') and sku_data.get(header.get('asin')) else sku_data.get(header.get('asin1'))
            asin_data  =asin_dict.get(asin)
            if asin_data:
                data[sku] =sku_data
                data[sku].update(asin_data)
        return data


    @classmethod
    def fetch_mws_products_report(cls,channel_id,report_id,
        product_ids,source='product_ids',operation='import'):
        data =None
        message = ''
        header = channel_id.get_mws_header()
        report_asins = set()
        report_data = None
        if not header :
            message +='No header mappings created'
        if header :
            report_data=report_id.get_report_data(header=header)
            if report_data:
                sku_keys = set(report_data)
                if  source=='product_ids' and product_ids :
                    keys=sku_keys.intersection(set(product_ids.split(',')))
                    if not  len(keys):
                         message +='<br/>ASIN not found in report, please verify the ASIN {0} or regenerate the report '.format(JL(list(keys)))
                    rem_keys = sku_keys-keys
                    if channel_id.debug=='enable':
                        _logger.info("=sku_keys==%r \nkeys====%r==\nproduct_ids==%rrem_keys=\n=%r"%(sku_keys,keys,product_ids,rem_keys))
                    if rem_keys:
                        # pass
                        map(lambda asin: report_data.pop(asin,None),rem_keys)
                    sku_keys = keys
                unique_report_data =  [report_data.get(sku) for sku in sku_keys]
                match = channel_id.match_product_mappings(limit=None).mapped('store_product_id')
                for sku in sku_keys:
                    sku_data = report_data.get(sku)
                    asin = sku_data.get(header.get('asin')) if header.get('asin') and sku_data.get(header.get('asin')) else sku_data.get(header.get('asin1'))
                    if asin:
                        if operation=='import' and (str(asin) not in  match):
                            report_asins.add(asin)
                        elif operation=='update' and  (str(asin) in  match):
                            report_asins.add(asin)
        return dict(
            report_asins = report_asins,
            report_data=report_data,
            message=message
        )

    @classmethod
    def get_mws_product_categ_data(cls, asin,channel_id):
        api_sdk = channel_id.get_mws_api_sdk()
        categ_res = api_sdk.get_mws_product_categ_for_asin(asin)
        categ_data = categ_res.get('data')
        message = categ_res.get('message')
        data =None
        if categ_data:
            data= api_sdk.process_mws_categ_data(categ_data.get('Self', {}))
        return dict(
            data =data,
            message=message
        )


    def create_mws_categ_report(self, store_id, channel_id):
        Report = self.env['mws.report']
        domain = [
            ('browse_node_id','=',store_id),
            ('report_type','=','_GET_XML_BROWSE_TREE_DATA_')
        ]
        match = Report.search(domain)
        if not match:
            vals = DomainVals(domain)
            vals['channel_id'] = channel_id.id
            Report.create(vals).send_request()
        elif match.state=='request':
            match.generate_report()
            match.receive_data()
            match.create_category()
        elif match.state=='generate':
            match.receive_data()
            match.create_category()

    def _mws_create_product_categories(self, product_asin,channel_id):
        categ_res = self.get_mws_product_categ_data(product_asin,channel_id)
        # _logger.info("=categ_res==%r==="%(categ_res))
        items = categ_res.get('data')
        message = categ_res.get('message','')
        if items and len(items):
            reversed_items = items[::-1]
            # size = len(reversed_items)
            for index,item in enumerate(reversed_items,1):
                if index==1:
                    item.pop('parent_id','')
                    # self.create_mws_categ_report(item.get('store_id'),channel_id)
                channel_id._match_create_product_categ(item)
        return dict(
            categ_id = items and items[0].get('store_id'),
            message=message
        )

    @staticmethod
    def get_mws_variants(variants,data,vals):
        #FIX THE MULTI LINE ATTRIBUTE IN FUTURE [variants,variants]
         # {'Color': 'Black', 'Size': '15.6'}
        variants_vals = vals.copy()
        variants_vals['store_id'] = vals['default_code']
        feed_variants= []
        name_value=[]
        for attribute,value in variants.items():
            feed_variant = dict(
                name=attribute,
                value=value,
            )
            name_value+=[feed_variant]
        variants_vals['name_value'] = name_value
        feed_variants+=[(0, 0, variants_vals)]
        return feed_variants

    @classmethod
    def get_product_vals(cls,categ_id,asin,data,header):
        attr = data.get('ItemAttributes',{})
        # _logger.info("===%r==="%(data))
        wk_asin = None
        if  header.get('asin') and data.get(header.get('asin')):
            wk_asin = data.get(header.get('asin'))
        elif header.get('asin1') and data.get(header.get('asin1')):
            wk_asin = data.get(header.get('asin1'))
        elif header.get('asin2') and data.get(header.get('asin2')):
            wk_asin = data.get(header.get('asin2'))
        elif header.get('asin3') and data.get(header.get('asin3')):
            wk_asin = data.get(header.get('asin3'))
        quantity = '0'
        if  header.get('quantity') and data.get(header.get('quantity')):
            quantity = data.get(header.get('quantity'))

        vals = dict(
            store_id=asin,
            name=header.get('item-name') and (data.get(header.get('item-name'))) or ET(data.get('Title')),
            description_sale=header.get('item-description') and data.get(header.get('item-description')),
            default_code= header.get('seller-sku') and  data.get(header.get('seller-sku')) or data.get(header.get('sku')),
            wk_asin= wk_asin,
            type='product',
            qty_available=float(quantity),
        )
        if categ_id :
            vals['extra_categ_ids'] =categ_id
        if  header.get('price') and data.get(header.get('price')):
            vals['list_price'] =float(data.get(header.get('price')))

        ItemDimensions = attr.get('ItemDimensions')
        if ItemDimensions:
            vals['dimensions_unit'] = ET(ItemDimensions.get('Height',{}).get('Units',''))
            vals['length'] = float(ET(ItemDimensions.get('Length','0')))
            vals['width'] = float(ET(ItemDimensions.get('Width','0')))
            vals['height'] =float(ET(ItemDimensions.get('Height','0')))
            weight = float(ET(ItemDimensions.get('Weight','0')))
            vals['weight'] = weight
            weight_unit = ET(ItemDimensions.get('Weight',{}).get('Units',{}))
            vals['weight_unit'] = weight_unit

        image_url = ET(attr.get('SmallImage',{}).get('URL',{}))
        if image_url and image_url not in ['false','False',False]:
            vals['image_url'] =image_url.replace('._SL75_.jpg','.jpg')
        if  (header.get('product-id') and data.get(header.get('product-id'))
        and header.get('product-id-type')  and data.get(header.get('product-id-type'))):
            wk_field=dict(PRODUCT_ID_TYPE).get( data.get(header.get('product-id-type')))
            vals['wk_product_id_type'] = wk_field
            vals['barcode'] =  data.get(header.get('product-id'))
        feed_variants  = data.pop('feed_variants','')
        if feed_variants:
            vals.pop('default_code')
            vals['feed_variants'] = cls.get_mws_variants(feed_variants,data,vals)
            # _logger.info("=feed_variants==%r==="%(vals['feed_variants']))
        return vals

    @staticmethod
    def _mws_update_product_feed(match,vals):
        match.write(dict(feed_variants=[(5,0,)]))
        vals['state']='update'
        return match.write(vals)

    @staticmethod
    def _mws_create_product_feed(feed_obj,vals,channel_id):
        return channel_id._create_feed(feed_obj, vals)

    @classmethod
    def _mws_import_product(cls, feed_obj,categ_id, asin,
        sku, data,channel_id,operation='import',header=None):

        update=False
        vals =cls.get_product_vals(categ_id,asin,data,header)
        match = channel_id._match_feed(
            feed_obj, [('store_id', '=', asin),('default_code','=',sku)],
            )
        if match:
            update=cls._mws_update_product_feed( match, vals)
        else:
            vals['store_id'] =asin
            match= cls._mws_create_product_feed(feed_obj, vals,channel_id)
        return dict(
            feed_id=match,
            update=update
        )

    def _mws_import_products(self, report_asins, report_data, channel_id):
        create_ids=[]
        update_ids=[]
        feed_obj = self.env['product.feed']
        operation = self.operation
        message = ''
        header =  self.channel_id.get_mws_header()

        for index, asins in enumerate(chunks(list(set(report_asins))),1):#chunks(report_asins):
            asin_data=self.get_mws_product_data(list(asins),channel_id)
            items=dict()
            if asin_data:
                items =self.merge_sku_asin_data(asin_data,report_data,header)
                if not items:
                    _logger.info("Product data not receive==\n asin_data ==>%r \n items==> %r===="%(asin_data,items))
                    message += '<br/>Product data not receive for these asins %r'%(asins)
            else:
                message += '<br/>Product  ASIN data not receive for these asins %r'%(asins)
            # if channel_id.debug=='enable':
            # _logger.info("=lenitem1s==%r=\n index=%r=%r \n %r"%(len(items),index,items.keys()),message)

            for sku, data in items.items():
                asin = data.get(header.get('asin')) if header.get('asin') and data.get(header.get('asin')) else data.get(header.get('asin1'))
                categ_id = self._mws_create_product_categories(asin,channel_id).get('categ_id')
                import_res =   self._mws_import_product(feed_obj,categ_id,
                    asin, sku, data, channel_id,operation,header)
                feed_id = import_res.get('feed_id')
                if  import_res.get('update'):
                    update_ids.append(feed_id)
                else:
                    create_ids.append(feed_id)
            self._cr.commit()
        return dict(
            create_ids=create_ids,
            update_ids=update_ids,
            message=message
        )

    def import_now(self):
        create_ids,update_ids,map_create_ids,map_update_ids =[],[],[],[]
        message=''
        self.env['multi.channel.sale'].mws_receive_report_data_before_import()
        for record in self:
            channel_id = record.channel_id
            report_id = self.report_id
            if not report_id:
                report_status = channel_id.mws_ensure_report()
                report_id = report_status.get('report_id')
                if report_status.get('message'):
                    message+=report_status.get('message')
                    continue
            report_res = record.fetch_mws_products_report(channel_id,
            report_id,record.product_ids,record.source,record.operation)
            message+= report_res.get('message','')
            report_asins = report_res.get('report_asins', {})
            report_data = report_res.get('report_data', {})
            if channel_id.debug=='enable':
                _logger.info("===%r===="%(report_asins))
            if not (report_asins or report_data):
                message+="<br/>Report data not received."
            else:
                feed_res = record._mws_import_products(report_asins,report_data,channel_id)
                message += feed_res.get('message')
                post_res = self.post_feed_import_process(record.channel_id,feed_res)
                create_ids += post_res.get('create_ids')
                update_ids += post_res.get('update_ids')
                map_create_ids += post_res.get('map_create_ids')
                map_update_ids += post_res.get('map_update_ids')

        message+=self.env['multi.channel.sale'].get_feed_import_message(
            'product',create_ids,update_ids,map_create_ids,map_update_ids
        )
        _logger.info("Import product===%r=%r= %r"%(update_ids,update_ids,message))

        return self.env['multi.channel.sale'].display_message(message)

    @api.model
    def _cron_mws_import_product(self):
        for channel_id in self.env['multi.channel.sale'].search(CHANNELDOMAIN):
            channel_id = channel_id
            obj=self.create(dict(channel_id=channel_id.id))
            obj.import_now()
