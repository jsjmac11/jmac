# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import fields, models, api
from datetime import datetime
import string


class SaleOrder(models.Model):
    _inherit = "sale.order"

    partner_shipping_id_address = fields.Char(
        compute="_shipping_as_address",
        string="Delivery Address",
    )
    partner_invoice_id_address = fields.Char(
        compute="_invoice_as_address",
        string="Invoice Address",
    )

    @api.depends(
        "partner_shipping_id",
        "partner_shipping_id.street",
        "partner_shipping_id.city",
        "partner_shipping_id.state_id",
        "partner_shipping_id.zip",
    )
    def _shipping_as_address(self):
        """
        Computes when the shipping partner is changed, or any of the address information changes.
        This is the computed value for the Delivery Addess field that is on a sale order, showing
        the address rather than the customer name.
        """
        for order in self:
            if order.partner_shipping_id:
                order.partner_shipping_id_address = self._res_partner_as_address(
                    order.partner_shipping_id
                )
            else:
                order.partner_shipping_id_address = ""

    @api.depends(
        "partner_invoice_id",
        "partner_invoice_id.street",
        "partner_invoice_id.city",
        "partner_invoice_id.state_id",
        "partner_invoice_id.zip",
    )
    def _invoice_as_address(self):
        """
        Computes when the partner invoice is changed, or any of the address information changes.
        This is the computed value for the Invoice Addess field that is on a sale order, showing
        the address rather than the customer name.
        """
        for order in self:
            if order.partner_invoice_id:
                order.partner_invoice_id_address = self._res_partner_as_address(
                    order.partner_invoice_id
                )
            else:
                order.partner_invoice_id_address = ""

    def _res_partner_as_address(self, res_partner):
        """
        For the given res_partner, returns a string which concatenates into
        a human readable address.
        """
        street = str(res_partner.street) + ", " if res_partner.street else ""
        street2 = str(res_partner.street2) + ", " if res_partner.street2 else ""
        city = str(res_partner.city) + ", " if res_partner.city else ""
        state = str(res_partner.state_id.code) + " " if res_partner.state_id else ""
        zipcode = str(res_partner.zip) if res_partner.zip else ""
        country = (
            ", " + str(res_partner.country_id.name) if res_partner.country_id else ""
        )
        return street + street2 + city + state + zipcode + country
