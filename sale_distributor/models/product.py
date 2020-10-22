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


class ProductProduct(models.Model):
    _inherit = "product.product"


class ProductSupplierinfo(models.Model):
    _inherit = "product.supplierinfo"

    active = fields.Boolean("Active", default=True)
    ignore_cost = fields.Boolean("Ignore Cost?", default=False)

    @api.onchange('ignore_cost')
    def onchange_ignore_cost(self):
        self.active = False if self.ignore_cost else True
