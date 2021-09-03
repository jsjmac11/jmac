# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE URL <https://store.webkul.com/license.html/> for full copyright and licensing details.
#################################################################################
from odoo.exceptions import RedirectWarning, ValidationError  # ,Warning
from odoo import api, tools
from odoo import fields, models, _
from odoo.addons.amazon_odoo_bridge.tools.tools import Mapname
from odoo.addons.amazon_odoo_bridge.tools.tools import MapId
from odoo.addons.amazon_odoo_bridge.tools.tools import extract_item as EI
from odoo.addons.amazon_odoo_bridge.tools.tools import JoinList as JL
from odoo.addons.amazon_odoo_bridge.tools.tools import FIELDS
from odoo.addons.amazon_odoo_bridge.tools.tools import add_text as AT
from odoo.addons.amazon_odoo_bridge.tools.tools import extract_list as EL
from odoo.addons.amazon_odoo_bridge.tools.tools import get_fd
from odoo.addons.amazon_odoo_bridge.tools.tools import prettify
from odoo.addons.amazon_odoo_bridge.tools.tools import ProductIdType
from odoo.addons.amazon_odoo_bridge.tools.tools import CHANNELDOMAIN
from operator import itemgetter
from urllib import parse as urlparse
from xml.etree.ElementTree import SubElement
from xml.etree.ElementTree import Element
from xml.etree import ElementTree
import logging
_logger = logging.getLogger(__name__)


_logger = logging.getLogger(__name__)

FeedReportType = [
    ('product', '_POST_PRODUCT_DATA_'),
    ('price', '_POST_PRODUCT_IMAGE_DATA_'),
    ('inventory', '_POST_INVENTORY_AVAILABILITY_DATA_'),
    ('image', '_POST_PRODUCT_IMAGE_DATA_'),
    ('order', '_POST_ORDER_FULFILLMENT_DATA_')
]

FEED_STATE = [
    ('draft', 'Draft'),
    ('submit', 'Export'),
    ('error', 'Error'),
    ('inactive', 'In Active')
]
FeedType = [
    ('product', 'Product'),
    ('price', 'Price'),
    ('inventory', 'Inventory'),
    ('relationship', 'Relationship'),
    ('image', 'Image'),
    ('order', 'Order')
]
OperationType = [
    ('export', 'Export'),
    ('update', 'Update')
]


class MWSFeed(models.Model):
    _name = "mws.feed"
    _description = "MWS Feed"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def default_get(self, fields):
        res = super(MWSFeed, self).default_get(fields)
        if not res.get('channel_id') and self._context.get('active_model') == 'multi.channel.sale':
            res.update({'channel_id': self._context.get('active_id')})
        return res

    def compute_product_count(self):
        for record in self:
            record.processed = [(product.id, product.name)
                                for product in record.product_tmpl_ids]
    name = fields.Char(
        string='Name'
    )
    data = fields.Text(
        string='Data'
    )
    response = fields.Text(
        string='Response'
    )
    state = fields.Selection(
        selection=FEED_STATE,
        default='draft',
        required=1
    )
    operation = fields.Selection(
        selection=OperationType,
        default='export'
    )
    feed_id = fields.Char(
        string='Feed ID'
    )
    feed_type = fields.Selection(
        selection=FeedType,  # ('order','Order')
        string='Feed Type',
        default='product',
        required=1
    )

    processed = fields.Text(
        string='Processed',
        compute='compute_product_count'
    )
    failed = fields.Text(
        tring='Failed'
    )
    channel_id = fields.Many2one(
        'multi.channel.sale',
        required=1,
        string='Channel ID',
        domain=CHANNELDOMAIN
    )
    product_ids = fields.Many2many(
        'product.product',
        string='Product',
        limit=3000,
        help='Select Only those products  which have valid UPC and SKU. \n At a time only 2 Gb data can be transfer using a feed.'
    )
    product_tmpl_ids = fields.Many2many(
        'product.template',
        string='Product Template',
        limit=3000,
        help='Select Only those products  which have valid UPC and SKU. \n At a time only 2 Gb data can be transfer using a feed.'
    )

    @api.model
    def create(self, vals):
        try:
            vals['name'] = self.env.ref(
                'amazon_odoo_bridge.feed_sequence').next_by_id()
        except Exception as e:
            pass
        return super(MWSFeed, self).create(vals)

    def post_product_relationship(self, items, channel_id, api_sdk=None):
        api_sdk = api_sdk or channel_id.get_mws_api_sdk()

        feed_type = '_POST_PRODUCT_RELATIONSHIP_DATA_'
        AmazonEnvelope = api_sdk.get_amazon_env(
            'Relationship', channel_id.mws_merchant_id)
        for message_id, item in enumerate(items, 1):
            if len(item.product_variant_ids) > 1:
                parent_sku = 'oe_template%s' % (item.id)
                child_data = item.product_variant_ids.read(['default_code'])[0]
                api_sdk.construct_product_relationship(AmazonEnvelope, message_id,
                                                       mapping_tmpl_sku, child_data)
        return api_sdk.mws_post_feed(feed_type, AmazonEnvelope)

    def post_product_image(self, template_ids, channel_id, api_sdk=None):
        api_sdk = api_sdk or channel_id.get_mws_api_sdk()
        feed_type = '_POST_PRODUCT_IMAGE_DATA_'
        base_url = self.env['ir.config_parameter'].sudo(
        ).get_param('web.base.url')
        AmazonEnvelope = api_sdk.get_amazon_env(
            'ProductImage', channel_id.mws_merchant_id)
        for template_id in template_ids:
            variant_ids = template_id.product_variant_ids
            message_id = 0
            if len(variant_ids) > 1:
                for message_id, product in enumerate(variant_ids, 1):
                    item = product.read(FIELDS)[0]
                    for mapping_id in product.channel_mapping_ids.filtered(lambda mapping: mapping.channel_id.channel == 'amazon') or product:
                        image_url = '/channel/image/product.product/%s/image/492x492.png' % (
                            product.id)
                        full_image_url = '%s' % urlparse.urljoin(
                            base_url, image_url),
                        item = dict(
                            default_code=mapping_id.default_code,
                            url=full_image_url
                        )
                        _logger.info('=1==%s' % item)
                        api_sdk.construct_image(
                            AmazonEnvelope, message_id, item, 'PT1')
            else:
                message_id += 1
                image_url = '/channel/image/product.template/%s/image/492x492.png' % (
                    template_id.id)
                full_image_url = '%s' % urlparse.urljoin(base_url, image_url),
                for mapping_id in object_id.channel_mapping_ids.filtered(lambda mapping: mapping.channel_id.channel == 'amazon') or template_id:
                    item = dict(
                        default_code=mapping_id.default_code,
                        url=full_image_url
                    )
                    _logger.info('=2==%s' % item)
                    api_sdk.construct_image(
                        AmazonEnvelope, message_id, item, 'PT1')
        return api_sdk.mws_post_feed(feed_type, AmazonEnvelope)

    @api.model
    def mws_ensure_product_sku(self, item, sku_sequence_id):
        if (not item.get('default_code')) and sku_sequence_id:
            sku_vals = {'default_code': sku_sequence_id.next_by_id()}
            self.env['product.product'].browse(item.get('id')).write(sku_vals)
            item.update(sku_vals)
        return item

    @api.model
    def mws_browse_node_id(self, product_id, channel_id):
        result = None
        match_category = channel_id.get_channel_category_id(
            product_id, channel_id)
        if match_category:
            return match_category[0]

    @api.model
    def post_product_data(self, template_ids, channel_id, default_node_id=None, sku_sequence_id=None, api_sdk=None):
        context = dict(self._context)
        context.update({'lang': channel_id.language_id.code})
        api_sdk = api_sdk or channel_id.get_mws_api_sdk()
        feed_type = '_POST_PRODUCT_DATA_'
        AmazonEnvelope = api_sdk.get_amazon_env(
            'Product', channel_id.mws_merchant_id)
        # sku_sequence_id = channel_id.sku_sequence_id
        # default_node_id = channel_id.mws_default_product_categ_id.store_category_id
        for template_id in template_ids:
            variant_ids = template_id.product_variant_ids
            message_id = 0
            for message_id, product in enumerate(variant_ids, 1):
                item = product.read(FIELDS)[0]
                for mapping_id in product.channel_mapping_ids.filtered(lambda mapping: mapping.channel_id.channel == 'amazon') or product:
                    item['default_code'] = mapping_id.default_code
                    item = self.mws_ensure_product_sku(item, sku_sequence_id)
                    node_id = self.mws_browse_node_id(
                        product, channel_id) or default_node_id
                    api_sdk.construct_product(
                        AmazonEnvelope, message_id, item, node_id)
        self.data = prettify(AmazonEnvelope)
        return api_sdk.mws_post_feed(feed_type, AmazonEnvelope)

    @api.model
    def post_order_fulfillment(self, picking_ids, channel_id, api_sdk=None):
        api_sdk = api_sdk or channel_id.get_mws_api_sdk()
        feed_type = '_POST_ORDER_FULFILLMENT_DATA_'
        AmazonEnvelope = api_sdk.get_amazon_env(
            'OrderFulfillment', channel_id.mws_merchant_id)
        # for picking_id in picking_ids:
        message_id = 1
        # date_done = picking_id.date_done
        # if not date_done:date_done =  fields.Datetime.now()
        # FulfillmentDate = fields.Datetime.from_string(date_done).isoformat()
        # ShipperTrackingNumber = picking_id.carrier_tracking_ref
        # CarrierName = picking_id.carrier_id.name or ''
        # raise Warning(FulfillmentDate)
        item = dict(
            AmazonOrderID='408-5641469-7557151',
            FulfillmentDate='FulfillmentDate',
            CarrierCode='UPS',
            ShippingMethod='UPS',
            CarrierName='UPS',
            ShipperTrackingNumber='1ZAOT5926698367358',
        )
        api_sdk.construct_order_fulfillment(AmazonEnvelope, message_id, item)
        self.data = prettify(AmazonEnvelope)
        return api_sdk.mws_post_feed(feed_type, AmazonEnvelope)

    @api.model
    def post_product_inventory(self, template_ids, channel_id, api_sdk=None):
        api_sdk = api_sdk or channel_id.get_mws_api_sdk()
        feed_type = '_POST_INVENTORY_AVAILABILITY_DATA_'
        default_qty = channel_id.mws_default_product_qty
        AmazonEnvelope = api_sdk.get_amazon_env(
            'Inventory', channel_id.mws_merchant_id)
        for template_id in template_ids:
            variant_ids = template_id.product_variant_ids
            message_id = 0
            for message_id, product in enumerate(variant_ids, 1):
                item = product.read(
                    ['qty_available', 'default_code', 'sale_delay'])[0]
                for mapping_id in product.channel_mapping_ids.filtered(lambda mapping: mapping.channel_id.channel == 'amazon') or product:
                    item['default_code'] = mapping_id.default_code
                    api_sdk.construct_inventory(
                        AmazonEnvelope, message_id, item, default_qty)
        self.data = prettify(AmazonEnvelope)
        return api_sdk.mws_post_feed(feed_type, AmazonEnvelope)

    @api.model
    def post_product_price(self, template_ids, channel_id, api_sdk=None):
        api_sdk = api_sdk or channel_id.get_mws_api_sdk()

        feed_type = '_POST_PRODUCT_PRICING_DATA_'
        AmazonEnvelope = api_sdk.get_amazon_env(
            'Price', channel_id.mws_merchant_id)
        pricelist_name = channel_id.pricelist_name
        currency = channel_id.pricelist_name.currency_id.name
        for template_id in template_ids:
            variant_ids = template_id.product_variant_ids
            message_id = 0
            for message_id, product in enumerate(variant_ids, 1):
                item = product.with_context(dict(pricelist=pricelist_name.id)).read([
                    'price', 'default_code'])[0]
                api_sdk.construct_price(
                    AmazonEnvelope, message_id, item, currency)
        self.data = prettify(AmazonEnvelope)
        return api_sdk.mws_post_feed(feed_type, AmazonEnvelope)

    def post_odoo_feed(self, object_ids, channel_id, feed_type, api_sdk=None):
        res = dict(
            message='',
            feed_id=[]
        )
        api_sdk = api_sdk or channel_id.get_mws_api_sdk()
        vals = dict(
            state='submit',
            channel_id=channel_id.id, feed_type=feed_type,
            product_tmpl_ids=[(6, 0, MapId(object_ids))]
        )
        if feed_type not in ['order']:
            vals['product_tmpl_ids'] = [(6, 0, MapId(object_ids))]
        res_feed_id = self.create(vals)

        if feed_type == 'image':
            post_res = res_feed_id.post_product_image(
                object_ids, channel_id, api_sdk)
        elif feed_type == 'relationship':
            post_res = res_feed_id.post_product_relationship(
                object_ids, channel_id, api_sdk)
        elif feed_type == 'product':
            post_res = res_feed_id.post_product_data(
                object_ids, channel_id, api_sdk)
        elif feed_type == 'inventory':
            post_res = res_feed_id.post_product_inventory(
                object_ids, channel_id, api_sdk)
        elif feed_type == 'price':
            post_res = res_feed_id.post_product_price(
                object_ids, channel_id, api_sdk)
        elif feed_type == 'order':
            post_res = res_feed_id.post_order_fulfillment(
                object_ids, channel_id, api_sdk)
        feed_id = post_res.get('feed_id')
        res['message'] += post_res.get('message', '')
        if feed_id:
            res_feed_id.feed_id = feed_id
            res['feed_id'] += [res_feed_id]
            res_feed_id.message_post(body='%s Feed Request %s Created.' % (
                feed_type.capitalize(), feed_id), subject='Feed Created')
        return res

    def wk_submit_feed(self):
        message = ''
        for record in self:
            channel_id = record.channel_id
            api_sdk = channel_id.get_mws_api_sdk()
            feed_type = dict(FeedReportType).get(record.feed_type)
            post_feed = api_sdk.mws_post_feed(
                feed_type, ElementTree.fromstring(self.data))
            feed_id = post_feed.get('feed_id')
            if feed_id:
                record.feed_id = feed_id
                record.state = 'submit'
                record.response = None
                record.message_post(
                    body=' %s Feed with mws request id %s created.' % (
                        record.feed_type.capitalize(), feed_id),
                    subject='Feed Created')

    def submit_feed(self):
        message = ''
        for record in self:
            channel_id = record.channel_id
            product_tmpl_ids = record.product_tmpl_ids
            if record.feed_type == 'product':
                product_feed_res = record.post_product_data(
                    product_tmpl_ids, channel_id)
                message += product_feed_res.get('message')
                feed_id = product_feed_res.get('feed_id')
            elif record.feed_type == 'price':
                price_feed_res = record.post_odoo_feed(
                    product_tmpl_ids, channel_id, 'price')
                message += price_feed_res.get('message')
                feed_id = price_feed_res.get('feed_id')
            elif record.feed_type == 'inventory':
                inventory_feed_res = record.post_odoo_feed(
                    product_tmpl_ids, channel_id, 'inventory')
                message += inventory_feed_res.get('message')
                feed_id = inventory_feed_res.get('feed_id')

            if feed_id:
                record.feed_id = feed_id[0].feed_id
                record.state = 'submit'
                record.message_post(
                    body=' %s Feed with mws request id %s created.' % (
                        record.feed_type.capitalize(), feed_id),
                    subject='Feed Created')

    def get_exported_product(self, product_tmpl_ids, result_node):
        asins = []
        # get_mws_product_by_asins
        root = ElementTree.fromstring(result_node)
        process = root.findtext(
            'Message/ProcessingReport/ProcessingSummary/MessagesProcessed')
        success = root.findtext(
            'Message/ProcessingReport/ProcessingSummary/MessagesSuccessful')
        error = root.findtext(
            'Message/ProcessingReport/ProcessingSummary/MessagesWithError')
        message = '<br/> Product Proceed {0} , Successful {1} , With Error {2}  <br/> '.format(
            process, success, error)
        message_ids = set()
        error_sku = dict()
        successful_sku = dict()
        with_warning_sku = dict()
        with_error_sku = dict()
        for result in root.getiterator('Result'):
            sku = result.findtext('AdditionalInfo/SKU')
            if result.findtext('ResultCode') == 'Error' and (result.findtext('ResultMessageCode') not in ['6024', '8026']):
                if sku:
                    with_error_sku[sku] = result.findtext('ResultDescription')
                    message += '<br/>Error For SKU %r  ==> %r.' % (
                        sku, with_error_sku[sku])
                MessageID = int(result.findtext('MessageID'))
                message_ids.add(MessageID)
            elif result.findtext('ResultCode') == 'Warning':
                if sku:
                    with_warning_sku[sku] = result.findtext(
                        'ResultDescription')
                    message += '<br/>Warning For SKU %r  ==> %r' % (
                        sku, with_warning_sku[sku])
            elif result.findtext('ResultCode') == 'Error':
                if sku:
                    with_error_sku[sku] = result.findtext('ResultDescription')
                    message += '<br/>Error For  SKU %r  ==> %r' % (
                        sku, with_error_sku[sku])

        invalid_product = self.env['product.product']
        exported_products = self.env['product.product']
        invalid_template = self.env['product.template']
        for template in product_tmpl_ids:
            product_variant_ids = template.product_variant_ids
            variant_ids = template.product_variant_ids.filtered(
                lambda var: var.default_code in with_error_sku.keys())
            if len(variant_ids):
                invalid_product += variant_ids
                invalid_template += template
            exported_products += product_variant_ids-variant_ids
        self.failed = len(invalid_product) and invalid_product or None
        return dict(
            exported_products=exported_products,
            message=message,
            error_sku=with_error_sku,
        )

    def update_product_mapping(self, result):
        exported_res = self.get_exported_product(self.product_tmpl_ids, result)

        msz = exported_res.get('message')
        product_ids = exported_res.get('exported_products')
        channel_id = self.channel_id
        if product_ids:
            mws_api = channel_id.get_mws_api_sdk()
            mapping_ids = []
            for product_id in product_ids:
                mapping_id = channel_id.match_product_mappings(
                    default_code=product_id.default_code,
                    domain=[('erp_product_id', '=', product_id.id)],
                )
                if mapping_id:
                    mapping_id.need_sync = 'no'
                    mapping_ids += [mapping_id]
                else:
                    product_data = product_id.read(
                        ['wk_product_id_type', 'barcode', 'wk_asin', 'default_code'])[0]
                    if product_data.get('wk_product_id_type') != 'wk_asin':
                        store_product_id = product_data.get('barcode')
                    else:
                        store_product_id = product_data.get('wk_asin')
                    mapping_id = channel_id.create_product_mapping(
                        odoo_template_id=product_id.product_tmpl_id,
                        odoo_product_id=product_id,
                        store_id=store_product_id,
                        store_variant_id='No Variants',
                        vals=product_data
                    )
                    mapping_ids += [mapping_id]

                    # Create Template Mappings Now
                    product_tmpl_data = product_id.product_tmpl_id.read(
                        ['barcode', 'default_code'])[0]

                    tmpl_mapping_id = channel_id.match_template_mappings(
                        default_code=product_tmpl_data.get('default_code'),
                        domain=[('odoo_template_id', '=', product_id.id)],
                    )
                    if not tmpl_mapping_id:
                        tmpl_mapping_id = channel_id.create_template_mapping(
                            erp_id=product_id.product_tmpl_id,
                            store_id=store_product_id,
                            vals=product_tmpl_data
                        )
            message = '{} Product exported over amazon.'.format(
                len(mapping_ids))
            msz += '<br/>%s' % (message)
        self.message_post(body=msz, subject='Product Feed Result')
        if self.failed:
            self.state = 'error'
        else:
            self.state = 'inactive'
        return self.env['multi.channel.sale'].display_message(msz)

    def wk_get_feed_result(self):
        item = len(self)
        message = ''
        for record in self:
            channel_id = record.channel_id
            api_sdk = channel_id.get_mws_api_sdk()
            result = api_sdk.get_feed_result(record.feed_id)
            if not result:
                message += 'Feed Submission Result is not ready for Feed, its may take upto few minutes.<br/> Please retry after a while.'
            elif result:
                record.response = result
                if hasattr(record, 'update_%s_mapping' % record.feed_type):
                    res = getattr(record, 'update_%s_mapping' %
                                  record.feed_type)(result)
                    if item == 1:
                        return res
                else:
                    message += api_sdk.get_result_message(result)
                    record.message_post(body=message, subject='Feed Result')
        return self.env['multi.channel.sale'].display_message(message)
    
    @api.model
    def update_inventory(self, items, channel_id):
        api_sdk = channel_id.get_mws_api_sdk()
        feed_type = '_POST_INVENTORY_AVAILABILITY_DATA_'
        AmazonEnvelope = api_sdk.get_amazon_env('Inventory',channel_id.mws_merchant_id)
        message_id = 1
        for item in items:
            api_sdk.construct_inventory(AmazonEnvelope, message_id, item)
        self.data =prettify(AmazonEnvelope)
        feed_result = api_sdk.mws_post_feed(feed_type, AmazonEnvelope)
        return feed_result