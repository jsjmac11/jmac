#############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
#############################################################################
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.depends('order_line.price_total')
    def _compute_amount_undiscounted(self):
        for order in self:
            total = 0.0
            for line in order.order_line:
                if not line.is_delivery:
                    # why is there a discount in a field named amount_undiscounted ??
                    total += line.price_subtotal + line.price_unit * ((line.discount or 0.0) / 100.0) * line.product_uom_qty

            order.amount_undiscounted = total

    @api.depends('order_line.discount')
    def _order_percent(self):
        """
        Compute the total discount of the SO.
        """
        for order in self:
            if order.amount_undiscounted:
                order.discount_rate = ((
                                               order.amount_undiscounted - order.amount_untaxed) / order.amount_undiscounted) * 100
            else:
                order.discount_rate = 0.0

    discount_type = fields.Selection([('percent', 'Percentage'), ('amount', 'Amount')], string='Discount type',
                                     readonly=True,
                                     default='percent')
    discount_rate = fields.Float('Order Discount %',
                                 readonly=True, store=True, compute='_order_percent',
                                 track_visibility='always')


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.onchange('discount')
    def onchange_discount(self):
        """
        Discount % validation.
        :return: raise
        """
        if not (0 <= self.discount <= 100):
            raise ValidationError(_("Discount Limit is invalid!"))
