# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE URL <https://store.webkul.com/license.html/> for full copyright and licensing details.
#################################################################################
from odoo.addons.amazon_odoo_bridge.tools.tools import FIELDS, MAPPINGDOMAIN, ProductIdType
from odoo import api, fields, models, _
from odoo.addons.odoo_multi_channel_sale.tools import DomainVals, MapId
from odoo.addons.amazon_odoo_bridge.tools.tools import CHANNELDOMAIN, extract_item
import logging
_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def mws_order_status_update(self):
        for rec in self:
            self.channel_mapping_ids[0].channel_id.mws_order_status_update(rec)


class ProductVariantFeed(models.Model):
    _inherit = "product.variant.feed"
    wk_asin = fields.Char(
        string='ASIN'
    )


class ProductFeed(models.Model):
    _inherit = "product.feed"

    @api.model
    def get_product_fields(self):
        res = super(ProductFeed, self).get_product_fields()
        res += ['wk_asin']
        return res

    wk_asin = fields.Char(
        string='ASIN'
    )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    wk_asin = fields.Char(
        string='ASIN'
    )
    wk_product_id_type = fields.Selection(
        selection_add=[('wk_asin', 'ASIN')],
    )


class ExtraCategories(models.Model):
    _inherit = 'extra.categories'

    @api.model
    def get_category_list(self):
        mapping_ids = self.env['channel.category.mappings'].search(
            [('channel_id', '=', self.instance_id.id)]
        )
        if self.instance_id.channel == "amazon":
            mapping_ids = mapping_ids.filtered("leaf_category")
        if mapping_ids:
            return [i.odoo_category_id for i in mapping_ids]
        return []