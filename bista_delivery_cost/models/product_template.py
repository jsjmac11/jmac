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
    product_manufacturer = fields.Char(string='Product Manufacturer')
