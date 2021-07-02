# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import fields, models, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    multiple_price = fields.Float(string='Fixed Shipping Cost',
                                  help='Define the Product Multiple used in delivery')
    free_shipping = fields.Boolean(string='Free Shipping Item')
    product_manufacturer = fields.Char(string='MPN')
    product_manufacturer_id = fields.Many2one('res.partner', string="Manufacturer")

    @api.onchange('product_manufacturer_id')
    def onchange_product_manufacturer_id(self):
        if self.product_manufacturer_id:
            self.product_manufacturer = self.product_manufacturer_id.ref
            self.phone_number = self.product_manufacturer_id.phone
        else:
            self.product_manufacturer = ''


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_manufacturer = fields.Boolean('Is Manufacturer')
