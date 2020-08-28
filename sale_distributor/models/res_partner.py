# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import fields, models, api
from datetime import datetime


class ResPartner(models.Model):
    _inherit = 'res.partner'

    vendor_stock_master_line = fields.One2many("vendor.stock.master.line", "res_partner_id",
                                               "Vendor Stock Line")


class VendorStockMasterLine(models.Model):
    _name = 'vendor.stock.master.line'
    _description = 'Vendor Stock Line'

    res_partner_id = fields.Many2one('res.partner', string='Vendor')
    # location_id = fields.Many2one('stock.location', string='Location')
    location_id = fields.Char(string='Name')
    product_id = fields.Many2one('product.product', string="Product")
    case_qty = fields.Float(string="Stock")
    state = fields.Char('State')
    abbreviation = fields.Char('Abbv.')
    hub = fields.Char('HUB')
    zip = fields.Char('Zip')
    phone = fields.Char('Phone#')
