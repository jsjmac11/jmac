# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE URL <https://store.webkul.com/license.html/> for full copyright and licensing details.
#################################################################################
from odoo.addons.odoo_multi_channel_sale.tools import DomainVals, MapId, JoinList
from odoo.addons.amazon_odoo_bridge.tools.tools import FIELDS, MAPPINGDOMAIN, ProductIdType
from odoo.addons.amazon_odoo_bridge.tools.tools import CHANNELDOMAIN, extract_item
from odoo import api, fields, models, _
from odoo.addons.amazon_odoo_bridge.tools.wk_mws_api import WKMWSAPI
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

try:
    from mws import Products, Reports, Feeds, MWSError, Sellers, Orders, Inventory
    from mws import utils
except Exception as e:
    _logger.error("install mws")

Estore = [('ecom_store', '=', 'amazon')]

from cryptography.fernet import Fernet

key = b'l7p4j1uA2K9wMEpSD8dWHnaAGsibITIxZHspHYLT4lw='

HeaderSelection = [
    ('sku', 'sku'),
    ('asin', 'asin'),
    ('item-name', 'item-name'),
    ('item-description', 'item-description'),
    ('listing-id', 'listing-id'),
    ('seller-sku', 'seller-sku'),
    ('price', 'price'),
    ('quantity', 'quantity'),
    ('open-date', 'open-date'),
    ('image-url', 'image-url'),
    ('item-is-marketplace', 'item-is-marketplace'),
    ('product-id-type', 'product-id-type'),
    ('zshop-shipping-fee', 'zshop-shipping-fee'),
    ('item-note', 'item-note'),
    ('item-condition', 'item-condition'),
    ('zshop-category1', 'zshop-category1'),
    ('zshop-browse-path', 'zshop-browse-path'),
    ('zshop-storefront-feature', 'zshop-storefront-feature'),
    ('asin1', 'asin1'),
    ('asin2', 'asin2'),
    ('asin3', 'asin3'),
    ('will-ship-internationally', 'will-ship-internationally'),
    ('expedited-shipping', 'expedited-shipping'),
    ('zshop-boldface', 'zshop-boldface'),
    ('product-id', 'product-id'),
    ('bid-for-featured-placement', 'bid-for-featured-placement'),
    ('add-delete', 'add-delete'),
    ('pending-quantity', 'pending-quantity'),
    ('fulfillment-channel', 'fulfillment-channel'),

]


class MWSReportsFields(models.Model):
    _name = "mws.report.fields"
    _description = "MWS Report Fields"

    name = fields.Char(
        string='Name',
        required=1
    )
    mws_header_mapping_ids = fields.One2many(
        comodel_name='mws.report.header',
        inverse_name='report_field_id',
        string='Header Mapping'
    )


class MWSReportsHeader(models.Model):
    _name = "mws.report.header"
    _description = "MWS Report Header"

    name = fields.Char(
        string='Name'
    )
    field = fields.Selection(
        selection=HeaderSelection,
        string='Field',
        required=1
    )
    report_field_id = fields.Many2one(
        comodel_name='mws.report.fields',
        string='Report Field',
    )
    channel_id = fields.Many2one(
        comodel_name='multi.channel.sale',
        string='Channel Id',
    )


class MultiChannelSale(models.Model):
    _inherit = "multi.channel.sale"

    mws_import_ord_cron_run = fields.Boolean("MWS Activate Toggle", help='''
        If True, means this channel import order cron will execute, if False means this channel import order cron will not execute
    ''')

    def write(self, vals):
        for record in self:
            if vals.get("mws_import_ord_cron_run"):
                seller_channels = record.search([('mws_import_ord_cron_run','=',True),('mws_merchant_id','=',record.mws_merchant_id)])
                if seller_channels:
                    raise UserError("Only One Channel for every seller account can select MWS Activate Toggle, Already (%s) channel is activated."%(seller_channels.name))
        return super(MultiChannelSale, self).write(vals)

    @api.model
    def get_mws_header(self):
        return dict(self.mws_report_field_id.mws_header_mapping_ids.mapped(lambda header: (header.field, header.name)))

    @api.model
    def mws_receive_report_data_before_import(self):
        Report = self.env['mws.report']
        Report._cron_generate_report()
        Report._cron_receive_data()
        return True

    @api.model
    def mws_default_report(self):
        context_channel_id = self._context.get(
            'channel_id') or self._context.get('wk_channel_id')
        _logger.info("=context_channel_id==%r====" %
                     (context_channel_id or self.id))
        domain = [
            ('channel_id', '=', context_channel_id or self.id),
            ('state', '=', 'receive'),
            ('report_type', '=', 'OPEN_LISTINGS_MERCHANT_LISTINGS'),
            ('ml_data', '!=', False),
            ('data', '!=', False),
        ]
        return self.env['mws.report'].search(domain, limit=1, order='id desc')

    @api.model
    def mws_ensure_report(self):
        res = dict(
            message='',
            report_id=None
        )
        report_id = self.mws_default_report()
        if not report_id:
            msg = _(
                'No report is ready for import, before importing the records firstly create report and receive the data.')
            res['message'] += msg
        else:
            res['report_id'] = report_id
            #action_id = self.env.ref('amazon_odoo_bridge.action_reports').id
            #raise RedirectWarning(msg, action_id, _('Go to the report panel'))
        return res

    def import_amazon_products(self):
        self.ensure_one()
        vals = dict(
            channel_id=self.id,
            source='all',
            operation='import',
        )
        obj = self.env['import.mws.products'].create(vals)
        return obj.import_now()

    def import_amazon_orders(self):
        self.ensure_one()
        vals = dict(
            channel_id=self.id,
            source='all',
            operation='import',
        )
        obj = self.env['import.mws.orders'].create(vals)
        return obj.import_now()

    @api.model
    def get_mws_api_sdk(self):
        mws_access_key, mws_secret_key = self.mws_access_key, self.mws_secret_key
        mws_merchant_id, mws_marketplace_id = self.mws_merchant_id, self.mws_marketplace_id
        region, domain = self.mws_domain_id.region, self.mws_domain_id.name        
        cipher_suite = Fernet(key)
        mws_access_key = bytes(mws_access_key, 'utf-8')
        mws_access_key_uncipher_text = (cipher_suite.decrypt(mws_access_key))
        mws_access_key_text_encryptedpassword = bytes(mws_access_key_uncipher_text).decode("utf-8") #convert to string
        
        mws_secret_key = bytes(mws_secret_key, 'utf-8')
        mws_secret_key_uncipher_text = (cipher_suite.decrypt(mws_secret_key))
        mws_secret_key_text_encryptedpassword = bytes(mws_secret_key_uncipher_text).decode("utf-8") #convert to string
        mws_access_key = mws_access_key_text_encryptedpassword
        mws_secret_key = mws_secret_key_text_encryptedpassword

        return WKMWSAPI(
            mws_access_key=mws_access_key,
            mws_secret_key=mws_secret_key,
            mws_merchant_id=mws_merchant_id,
            mws_marketplace_id=mws_marketplace_id,
            region=region,
            domain=domain,
        )

    @api.model
    def _get_mws(self, obj):
        mws_access_key, mws_secret_key = self.mws_access_key, self.mws_secret_key
        mws_merchant_id, mws_marketplace_id = self.mws_merchant_id, self.mws_marketplace_id
        region, domain = self.mws_domain_id.region, self.mws_domain_id.name        

        cipher_suite = Fernet(key)
        mws_access_key = bytes(mws_access_key, 'utf-8')
        mws_access_key_uncipher_text = (cipher_suite.decrypt(mws_access_key))
        mws_access_key_text_encryptedpassword = bytes(mws_access_key_uncipher_text).decode("utf-8") #convert to string
        
        mws_secret_key = bytes(mws_secret_key, 'utf-8')
        mws_secret_key_uncipher_text = (cipher_suite.decrypt(mws_secret_key))
        mws_secret_key_text_encryptedpassword = bytes(mws_secret_key_uncipher_text).decode("utf-8") #convert to string
        mws_access_key = mws_access_key_text_encryptedpassword
        mws_secret_key = mws_secret_key_text_encryptedpassword

        if obj == 'Sellers':
            return Sellers(mws_access_key, mws_secret_key, mws_merchant_id, region=region, domain=domain)
        elif obj == 'Reports':
            return Reports(mws_access_key, mws_secret_key, mws_merchant_id, region=region, domain=domain)
        elif obj == 'Products':
            return Products(mws_access_key, mws_secret_key, mws_merchant_id, egion=region, domain=domain)
        elif obj == 'Feeds':
            return Feeds(mws_access_key, mws_secret_key, mws_merchant_id, region=region, domain=domain)
        elif obj == "Inventory":
            return Inventory(mws_access_key, mws_secret_key, mws_merchant_id, region=region, domain=domain)
        elif obj == 'Orders':
            return Orders(mws_access_key, mws_secret_key, mws_merchant_id, region=region, domain=domain, version='2013-09-01')

    @api.model
    def get_channel(self):
        result = super(MultiChannelSale, self).get_channel()
        result.append(("amazon", "Amazon"))
        return result

    def test_amazon_connection(self):
        for obj in self:
            mws_marketplace_id = obj.mws_marketplace_id
            state = 'error'
            message = ''
            try:
                sellers = obj._get_mws('Sellers')
                response = sellers.list_marketplace_participations().parsed
                state = 'validate'
            except MWSError as me:
                message += '<br/> %r' % me
            except Exception as e:
                message += '<br/> %r' % e
            if state == 'validate' and response:
                Marketplace = response.get(
                    'ListMarketplaces', {}).get('Marketplace', {})
                if type(Marketplace) == utils.object_dict:
                    Marketplace = [Marketplace]
                MarketplaceIds = map(lambda i: extract_item(
                    i.get('MarketplaceId')), Marketplace)
                MarketplaceMatch = None
                for mp_id in Marketplace:
                    if extract_item(mp_id.get('MarketplaceId')) == mws_marketplace_id:
                        MarketplaceMatch = mp_id
                        currency = extract_item(
                            mp_id.get('DefaultCurrencyCode'))
                        currency_domain = [('name', '=', currency)]
                        currency_id = self.env['res.currency'].search(
                            currency_domain)
                        if not currency_id:
                            message += '<br/>  Please enable the %s currency .' % (
                                currency)
                            state = 'error'
                        elif currency_id.name != obj.pricelist_name.currency_id.name:
                            message += '<br/> Currency not matched .'
                            state = 'error'
                        break
                if not MarketplaceMatch:
                    message += '<br/>  No Marketplace [%r] match for MarketplaceId %s.' % (
                        JoinList(MarketplaceIds), mws_marketplace_id)
                if state != 'error':
                    state = 'validate'
                    message += '<br/> Credentials successfully validated.'
            obj.state = state

        return self.display_message(message)

    mws_domain_id = fields.Many2one(
        comodel_name='mws.domain',
        string='Domain'
    )
    mws_access_key = fields.Char(
        string='Access Key'
    )
    mws_secret_key = fields.Char(
        string='Secret Key'
    )
    mws_merchant_id = fields.Char(
        string='Merchant ID'
    )
    mws_marketplace_id = fields.Char(
        string='Marketplace ID'
    )
    mws_report_field_id = fields.Many2one(
        comodel_name='mws.report.fields',
        string='Report Fields'
    )
    mws_report_cron = fields.Boolean(
        string='Request/Generate Report'
    )
    mws_imp_product_cron = fields.Boolean(
        string='Import Product'
    )
    mws_imp_order_cron = fields.Boolean(
        string='Import Order'
    )
    mws_imp_order_status_cron = fields.Boolean(
        string='Import Order Status'
    )
    mws_default_product_price = fields.Float(
        string='Default Price',
        default=0.01
    )
    mws_default_product_qty = fields.Integer(
        string='Default Quantity',
        default=0
    )
    mws_default_product_categ_id = fields.Many2one(
        comodel_name='channel.category.mappings',
        string='Amazon Category',
    )

    @api.model
    def create(self, vals):
        if 'mws_access_key' in vals  and vals.get('mws_access_key'):
            cipher_suite = Fernet(key)
            v = bytes(vals.get('mws_access_key'), 'utf-8')
            ciphered_text = cipher_suite.encrypt(v)
            vals.update({'mws_access_key': ciphered_text})
        if 'mws_secret_key' in vals  and vals.get('mws_secret_key'):
            cipher_suite_a = Fernet(key)
            v = bytes(vals.get('mws_secret_key'), 'utf-8')
            ciphered_text_a = cipher_suite_a.encrypt(v)
            vals.update({'mws_secret_key': ciphered_text_a})
        res = super(MultiChannelSale, self).create(vals)
        return res 

    def write(self, vals):
        if 'mws_access_key' in vals  and vals.get('mws_access_key'):
            cipher_suite = Fernet(key)
            v = bytes(vals.get('mws_access_key'), 'utf-8')
            ciphered_text = cipher_suite.encrypt(v)
            vals.update({'mws_access_key': ciphered_text})
        if 'mws_secret_key' in vals  and vals.get('mws_secret_key'):
            cipher_suite_a = Fernet(key)
            v = bytes(vals.get('mws_secret_key'), 'utf-8')
            ciphered_text_a = cipher_suite_a.encrypt(v)
            vals.update({'mws_secret_key': ciphered_text_a})
        res = super(MultiChannelSale, self).write(vals)
        return res
        
    @api.onchange('mws_imp_product_cron')
    def set_mws_import_product_cron(self):
        self.set_channel_cron(
            ref_name='amazon_odoo_bridge.cron_import_product_from_mws',
            active=self.mws_imp_product_cron
        )

    @api.onchange('mws_imp_order_cron')
    def set_mws_import_order_cron(self):
        self.set_channel_cron(
            ref_name='amazon_odoo_bridge.cron_import_order_from_mws',
            active=self.mws_imp_order_cron
        )

    @api.onchange('mws_imp_order_status_cron')
    def set_mws_import_order_status_cron(self):
        self.set_channel_cron(
            ref_name='amazon_odoo_bridge.cron_import_order_status_from_mws',
            active=self.mws_imp_order_status_cron
        )

    @api.onchange('mws_report_cron')
    def set_mws_report_cron(self):
        self.set_channel_cron(
            ref_name='amazon_odoo_bridge.cron_send_request_mws_report',
            active=self.mws_report_cron
        )
        self.set_channel_cron(
            ref_name='amazon_odoo_bridge.cron_send_generate_mws_report',
            active=self.mws_report_cron
        )
        self.set_channel_cron(
            ref_name='amazon_odoo_bridge.cron_send_receive_mws_report',
            active=self.mws_report_cron
        )

    def action_update_mws_products(self):
        return {
            'name': 'Update Product Price/Quantity',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_model': 'export.mws.products',
            'type': 'ir.actions.act_window',
            'context':   {'wk_state': 'update'},
        }

    def mws_import_product_type(self, vals, channel_id):
        create_ids, update_ids = self.env['mws.product.type'], self.env['mws.product.type']
        Type = self.env['mws.product.type']
        for val in vals:
            domain = [('name', '=', val.get('name')),
                      ('channel_id', '=', channel_id.id)]
            match = Type.search(domain)
            if match:
                update_ids += match
            else:
                create_ids += Type.create(DomainVals(domain))
        _logger.info("=IMPORT Product Type===%r=====%r" %
                     (update_ids, create_ids))
        return dict(
            create_ids=create_ids,
            update_ids=update_ids,
        )

    def mws_import_attribute_value(self, store_id, name,
                                   store_attribute_value_name, attribute_id, channel_id):
        match = channel_id.match_attribute_value_mappings(store_id)
        if match:
            return match
        erp_id = channel_id.get_store_attribute_value_id(
            name, attribute_id, create_obj=True)
        return channel_id.create_attribute_value_mapping(
            erp_id=erp_id, store_id=store_id,
            store_attribute_value_name=store_attribute_value_name
        )

    def mws_import_attribute(self, store_id, name,
                             store_attribute_name, channel_id):
        match = channel_id.match_attribute_mappings(
            store_attribute_id=store_id)
        if match:
            return match
        erp_id = channel_id.get_store_attribute_id(name, create_obj=True)
        return channel_id.create_attribute_mapping(
            erp_id=erp_id,
            store_id=store_id,
            store_attribute_name=store_attribute_name
        )

    def mws_import_attributes(self, attribute_vals_list, channel_id):
        create_attr_ids = []
        create_attr_vals_ids = []
        for attr_vals in attribute_vals_list:
            name = attr_vals.get('name')
            store_attribute_name = attr_vals.get('store_attribute_name')
            store_attribute_id = attr_vals.get('store_attribute_id')
            attr_map_id = self.mws_import_attribute(
                store_id=store_attribute_id,
                name=name,
                store_attribute_name=store_attribute_name,
                channel_id=channel_id
            )
            attribute_id = attr_map_id.attribute_name
            create_attr_ids += [attribute_id]
            store_attribute_value_name_list = attr_vals.get(
                'store_attribute_value_name_list')
            for value_name in store_attribute_value_name_list:
                attr_val_map_id = self.mws_import_attribute_value(
                    store_id=value_name,
                    name=value_name,
                    store_attribute_value_name=value_name,
                    attribute_id=attribute_id.id,
                    channel_id=channel_id
                )
                create_attr_vals_ids += [attr_val_map_id.attribute_value_name]
        _logger.info("=IMPORT ATTRIBUTE===%r=====%r" %
                     (create_attr_ids, create_attr_vals_ids))
        return dict(
            create_attr_ids=create_attr_ids,
            create_attr_vals_ids=create_attr_vals_ids,
        )

    def mws_order_status_update(self, order_ids):
        Feed = self.env['mws.feed']
        Feed.post_odoo_feed(order_ids, self, 'order')
    
    def sync_quantity_amazon(self, mapping, product_qty):
        channel_id = self
        variant = mapping.product_name
        items=dict(
            default_code = variant.default_code,
            qty_available = product_qty
        )
        return self.env['mws.feed']\
            .create({'channel_id': channel_id.id, 'product_ids':[(6,0,[variant.id])]})\
            .update_inventory([items],channel_id)