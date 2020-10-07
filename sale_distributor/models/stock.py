# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime
import string
from dateutil.relativedelta import relativedelta


class StockRule(models.Model):
    _inherit = 'stock.rule'


    @api.model
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        res = super(StockRule, self)._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)
        if values.get('vendor_price_unit', False):
            partner = values['supplier'].name
            procurement_uom_po_qty = product_uom._compute_quantity(product_qty, product_id.uom_po_id)
            # _select_seller is used if the supplier have different price depending
            # the quantities ordered.
            seller = product_id.with_context(force_company=company_id.id)._select_seller(
                partner_id=partner,
                quantity=procurement_uom_po_qty,
                date=po.date_order and po.date_order.date(),
                uom_id=product_id.uom_po_id)
            taxes = product_id.supplier_taxes_id
            fpos = po.fiscal_position_id
            taxes_id = fpos.map_tax(taxes, product_id, seller.name) if fpos else taxes
            if taxes_id:
                taxes_id = taxes_id.filtered(lambda x: x.company_id.id == company_id.id)

            price_unit = self.env['account.tax']._fix_tax_included_price_company(values.get('vendor_price_unit', False), product_id.supplier_taxes_id, taxes_id, company_id) if seller else 0.0
            if price_unit and seller and po.currency_id and seller.currency_id != po.currency_id:
                price_unit = seller.currency_id._convert(
                    price_unit, po.currency_id, po.company_id, po.date_order or fields.Date.today())
            res['price_unit'] = price_unit
            res['line_split'] = self._context.get('line_split',False)
            if not self._context.get('line_split',False):
                split_line = self.with_context(line_split=True)._prepare_purchase_order_line(
                    product_id, product_qty,
                    product_uom, company_id,
                    values, po)
                if split_line:
                    sale_line = values.get('split_sale_line_id',False)
                    split_line.update({'sale_line_id': sale_line.id if sale_line else False})
                    res['split_line_ids'] = [(0,0,split_line)]
        return res

    def _update_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, line):
        res = super(StockRule, self)._update_purchase_order_line(product_id, product_qty, product_uom, company_id, values, line)
        if values.get('vendor_price_unit', False):
            partner = values['supplier'].name
            procurement_uom_po_qty = product_uom._compute_quantity(product_qty, product_id.uom_po_id)
            seller = product_id.with_context(force_company=company_id.id)._select_seller(
            partner_id=partner,
            quantity=line.product_qty + procurement_uom_po_qty,
            date=line.order_id.date_order and line.order_id.date_order.date(),
            uom_id=product_id.uom_po_id)
            price_unit = self.env['account.tax']._fix_tax_included_price_company(values.get('vendor_price_unit', False), line.product_id.supplier_taxes_id, line.taxes_id, company_id) if seller else 0.0
            if price_unit and seller and line.order_id.currency_id and seller.currency_id != line.order_id.currency_id:
                price_unit = seller.currency_id._convert(
                    price_unit, line.order_id.currency_id, line.order_id.company_id, fields.Date.today())
            
            # partner = procurement.values['supplier'].name
            split_line = self.with_context(line_split=True)._prepare_purchase_order_line(
                product_id, product_qty,
                product_uom, company_id,
                values, line.order_id)
            if split_line:
                sale_line = values.get('split_sale_line_id',False)
                split_line.update({'sale_line_id': sale_line.id if sale_line else False})
            # if split_line:
            res['split_line_ids'] = [(0,0,split_line)]
            res['price_unit'] = price_unit
        return res

    def add_vendor_to_product(self, procurements):
        for procurement, rule in procurements:
            # Get the schedule date in order to find a valid seller
            if procurement.values.get("supplier_id"):
                partner_id = procurement.values.get("supplier_id")
                product_id = procurement.product_id
                procurement_date_planned = fields.Datetime.from_string(procurement.values['date_planned'])
                schedule_date = (procurement_date_planned - relativedelta(days=procurement.company_id.po_lead))

                supplier = product_id.with_context(force_company=procurement.company_id.id)._select_seller(
                    partner_id=partner_id,
                    quantity=procurement.product_qty,
                    date=schedule_date.date(),
                    uom_id=procurement.product_uom)
                if not supplier:
                    # Do not add a contact as a supplier
                    v_price_unit = procurement.values.get("vendor_price_unit")
                    line = procurement.values.get("split_sale_line_id")
                    partner = partner_id if not partner_id.parent_id else partner_id.parent_id
                    # Convert the price in the right currency.
                    currency = partner.property_purchase_currency_id or self.env.company.currency_id
                    line_currency = line.currency_id
                    price = line_currency._convert(v_price_unit, currency, procurement.company_id.id, schedule_date.date() or fields.Date.today(), round=False)
                    # Compute the price for the template's UoM, because the supplier's UoM is related to that UoM.
                    if product_id.product_tmpl_id.uom_po_id != procurement.product_uom:
                        default_uom = product_id.product_tmpl_id.uom_po_id
                        price = procurement.product_uom._compute_price(price, default_uom)

                    supplierinfo = {
                        'name': partner.id,
                        'sequence': max(product_id.seller_ids.mapped('sequence')) + 1 if product_id.seller_ids else 1,
                        'min_qty': 0.0,
                        'price': price,
                        'currency_id': currency.id,
                        'delay': 0,
                    }
                    seller = product_id._select_seller(
                        partner_id=partner_id,
                        quantity=procurement.product_qty,
                        date=schedule_date.date(),
                        uom_id=procurement.product_uom)
                    if seller:
                        supplierinfo['product_name'] = seller.product_name
                        supplierinfo['product_code'] = seller.product_code
                    vals = {
                        'seller_ids': [(0, 0, supplierinfo)],
                    }
                    try:
                        product_id.write(vals)
                    except AccessError:  # no write access rights -> just ignore
                        break
        return


    @api.model
    def _run_buy(self, procurements):
        self.add_vendor_to_product(procurements)
        return super(StockRule, self)._run_buy(procurements)

