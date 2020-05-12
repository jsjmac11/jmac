# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ChooseDeliveryCarrier(models.TransientModel):
    _inherit = 'choose.delivery.carrier'

    def button_confirm(self):
        """
           we have overright this method to calculate the delivery price based 
           on products multiple and delivery fix price and product qty sale.
        """
        if self.carrier_id and self.carrier_id.fixed_price:
            order_lines = self.order_id and self.order_id.order_line.filtered(
                lambda l: l.is_delivery == False and l.display_type not in [
                    'line_section', 'line_note'])
            total_delivery_price = order_lines and sum(
                [line.product_id.multiple_price 
                 * line.product_uom_qty for line in order_lines]) or 0
            total_delivery_price += self.carrier_id.fixed_price
        else:
            total_delivery_price = self.delivery_price
        self.order_id.set_delivery_line(self.carrier_id, total_delivery_price)
        self.order_id.write({
            'recompute_delivery_price': False,
            'delivery_message': self.delivery_message,
        })
