# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import fields, models, api, _


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    product_pack_id = fields.Many2one("product.pack.uom",string="Product Pack")
    pack_quantity = fields.Float(string='Pack Quantity', digits='Product Unit of Measure', required=True, default=1.0)

    @api.onchange('product_pack_id')
    def product_pack_id_change(self):
        self.product_id = False
        if self.product_pack_id:
            self.product_id = self.product_pack_id.product_tmpl_id.product_variant_id.id
            self.quantity = 1.0
            self.pack_quantity = self.product_pack_id.quantity

    def _get_computed_price_unit(self):
        self.ensure_one()
        price_unit = super(AccountMoveLine, self)._get_computed_price_unit()
        if self.product_pack_id and not self.product_pack_id.is_auto_created:
            if self.move_id.is_sale_document(include_receipts=True):
                # Out invoice.
                price_unit = self.product_pack_id.price
            if self.product_uom_id != self.product_id.uom_id:
                price_unit = self.product_id.uom_id._compute_price(price_unit, self.product_uom_id)

        return price_unit