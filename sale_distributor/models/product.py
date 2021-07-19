# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import fields, models, api
from datetime import datetime

from odoo.tools import float_compare
from odoo.osv import expression

class ProductProduct(models.Model):
    _inherit = "product.product"

    def name_get(self):
        if self._context.get('split_line_product'):
            result = []
            for prod in self:
                default_code = ''
                if prod.product_tmpl_id.default_code:
                    default_code = "[%s] " % (prod.product_tmpl_id.default_code)
                name = "%s" % (default_code)
                if not name:
                    name = '%s' % prod.product_tmpl_id.name or ''
                result.append((prod.id, name))
            return result
        return super(ProductProduct, self).name_get()

class ProductTemplate(models.Model):
    _inherit = "product.template"

    product_pack_line = fields.One2many("product.pack.uom", "product_tmpl_id",
                                        string="Product Pack's",
                                        domain=[('is_auto_created','!=',True)],
                                        help="Define product packs.")
    phone_number = fields.Char(string="Phone Number")
    dropship_selection = fields.Selection([('Yes', 'Yes'), ('No', 'No')], string='Dropships')
    dropship_fee = fields.Float(string="Dropship Fee")
    order_min = fields.Char(string="Order Minimum")
    below_min_fee = fields.Float(string="Below Minimum Fee")
    free_freight_level = fields.Char(string="Free Freight Level")
    ships_from = fields.Char(string="Ship From")
    ship_cutoff_time = fields.Char(string="Shipping Cutoff Time")
    note = fields.Text(string="Note")
    product_dimension_line = fields.One2many(
        "product.dimension.line", 'name', string="Dimensions")
    parent_manufacture = fields.Many2one("res.partner", string="Parent Manufacture")

    @api.model
    def default_get(self, fields_list):
        res = super(ProductTemplate, self).default_get(fields_list)
        res.update({
                    'type': 'product'
                   })
        return res

    @api.model
    def create(self, vals):
        if vals.get('name'):
            pack_auto_line = (0, 0, {
                     'quantity': 1.0,
                     'is_auto_created': True})
            if vals.get('product_pack_line'):
                vals['product_pack_line'].append(pack_auto_line)
            else:
                vals['product_pack_line'] = [pack_auto_line]
        return super(ProductTemplate, self).create(vals)

class ProductSupplierinfo(models.Model):
    _inherit = "product.supplierinfo"

    active = fields.Boolean("Active", default=True)
    ignore_cost = fields.Boolean("Ignore Cost?", default=False)

    @api.onchange('ignore_cost')
    def onchange_ignore_cost(self):
        self.active = False if self.ignore_cost else True

    @api.model
    def create(self, vals):
        if vals.get('product_code'):
            v = {'name': vals.get('product_code'),
                     'product_template_id': vals.get('product_tmpl_id')}
            self.env['product.search.keyword'].create(v)
        return super(ProductSupplierinfo, self).create(vals)
    
    def write(self, vals):
        if vals.get('product_code'):
            v = {'name': vals.get('product_code'),
                     'product_template_id': self.product_tmpl_id}
            self.env['product.search.keyword'].create(v)
        return super(ProductSupplierinfo, self).write(vals)
    
class ProductPackUom(models.Model):
    _name="product.pack.uom"
    _description = "Product Pack Uom"
    _order="product_tmpl_id, name"

    name = fields.Char("Name")
    product_id = fields.Many2one("product.product",'Product')
    product_tmpl_id = fields.Many2one("product.template","Product Template")
    quantity = fields.Float("Quantity", digits='Product Unit of Measure')
    is_auto_created = fields.Boolean("Auto Created", default=False)
    price = fields.Float("Price")

    def name_get(self):
        result = []
        for prod in self:
            default_code = ''
            if prod.product_tmpl_id.default_code:
                default_code = "[%s] " % (prod.product_tmpl_id.default_code)
            name = "%s" % (default_code)
            if prod.name:
                name = name + '-%s' % prod.name or ''
            if not prod.name:
                name = '%s' % prod.product_tmpl_id.name or ''
            result.append((prod.id, name))
        return result

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = ['|','|', ('name', 'ilike', name), ('product_tmpl_id.default_code', 'ilike', name), ('product_tmpl_id.name', 'ilike', name)]
        sat_code_ids = self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
        return models.lazy_name_get(self.browse(sat_code_ids).with_user(name_get_uid))


class ProductDimensionLine(models.Model):
    """This class store dimension of products with weight."""

    _name = "product.dimension.line"
    _description = "Product Dimensions Details"

    name = fields.Many2one("product.template", 'Product Template')
    product_id = fields.Many2one("product.product", 'Product')
    quantity = fields.Float("Qty")
    weight_lbs = fields.Float("Weight lbs")
    weight_oz = fields.Float("Weight Oz")
    length = fields.Float("Length(in)")
    width = fields.Float("Width(in)")
    height = fields.Float("Height(in)")
