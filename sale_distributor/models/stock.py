# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################
from odoo import fields, models, api, _, SUPERUSER_ID
from collections import defaultdict
from itertools import groupby
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
            res['item_note'] = values['split_sale_line_id'].item_note
            res['line_split'] = self._context.get('line_split',False)
            po_line_list = []
            if not self._context.get('line_split',False):
                split_line = self.with_context(line_split=True)._prepare_purchase_order_line(
                    product_id, product_qty,
                    product_uom, company_id,
                    values, po)
                if split_line:
                    sale_line = values.get('split_sale_line_id',False)
                    split_line.update({'sale_line_id': sale_line.id if sale_line else False})
                    po_line_list.append((0,0,split_line))
            if values['split_sale_line_id'].item_note and not self._context.get('line_split',False):
                item_note_dict = {'name': values['split_sale_line_id'].item_note,'display_type': 'line_note',
                                        'line_split': False,
                                        'price_unit': 0.0,
                                        'product_qty': 0.0,
                                        'product_id': False,
                                        'order_id': po.id,}
                po_line_list.append((0,0,item_note_dict))
            if po_line_list:
                res['split_line_ids'] = po_line_list
        return res

    def _update_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, line):
        if line.line_split:
            inv_qty = line.product_qty - product_qty
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
                if line.parent_line_id:
                    split_line.update({'parent_line_id': line.parent_line_id.id})
                sale_line = values.get('split_sale_line_id',False)
                split_line.update({'sale_line_id': sale_line.id if sale_line else False})
            # if split_line:
            self.env['purchase.order.line'].sudo().create(split_line)
            # res['split_line_ids'] = [(0,0,split_line)]
            if line.line_split:
                res['product_qty'] = inv_qty
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
        other_procurements = []
        for procurement, rule in procurements:
            if procurement.values.get("split_sale_line_id"):
                if procurement.values.get("split_sale_line_id").line_type == 'allocate_po':
                    continue
            other_procurements.append((procurement, rule))
        if other_procurements:
            procurements = other_procurements

        procurements_by_po_domain = defaultdict(list)
        for procurement, rule in procurements:
            # Get the schedule date in order to find a valid seller
            procurement_date_planned = fields.Datetime.from_string(procurement.values['date_planned'])
            schedule_date = (procurement_date_planned - relativedelta(days=procurement.company_id.po_lead))

            supplier = procurement.product_id.with_context(force_company=procurement.company_id.id)._select_seller(
                partner_id=procurement.values.get("supplier_id"),
                quantity=procurement.product_qty,
                date=schedule_date.date(),
                uom_id=procurement.product_uom)

            # Fall back on a supplier for which no price may be defined. Not ideal, but better than
            # blocking the user.
            supplier = supplier or procurement.product_id._prepare_sellers(False).filtered(
                lambda s: not s.company_id or s.company_id == procurement.company_id
            )[:1]

            if not supplier:
                msg = _('There is no matching vendor price to generate the purchase order for product %s (no vendor defined, minimum quantity not reached, dates not valid, ...). Go on the product form and complete the list of vendors.') % (procurement.product_id.display_name)
                raise UserError(msg)

            partner = supplier.name
            # we put `supplier_info` in values for extensibility purposes
            procurement.values['supplier'] = supplier
            procurement.values['propagate_date'] = rule.propagate_date
            procurement.values['propagate_date_minimum_delta'] = rule.propagate_date_minimum_delta
            procurement.values['propagate_cancel'] = rule.propagate_cancel

            domain = rule._make_po_get_domain(procurement.company_id, procurement.values, partner)
            procurements_by_po_domain[domain].append((procurement, rule))

        for domain, procurements_rules in procurements_by_po_domain.items():
            # Get the procurements for the current domain.
            # Get the rules for the current domain. Their only use is to create
            # the PO if it does not exist.
            procurements, rules = zip(*procurements_rules)

            # Get the set of procurement origin for the current domain.
            origins = set([p.origin for p in procurements])
            # Check if a PO exists for the current domain.
            po = self.env['purchase.order'].sudo().search([dom for dom in domain], limit=1)
            company_id = procurements[0].company_id
            if not po:
                # We need a rule to generate the PO. However the rule generated
                # the same domain for PO and the _prepare_purchase_order method
                # should only uses the common rules's fields.
                vals = rules[0]._prepare_purchase_order(company_id, origins, [p.values for p in procurements])
                # The company_id is the same for all procurements since
                # _make_po_get_domain add the company in the domain.
                # We use SUPERUSER_ID since we don't want the current user to be follower of the PO.
                # Indeed, the current user may be a user without access to Purchase, or even be a portal user.
                po = self.env['purchase.order'].with_context(force_company=company_id.id).with_user(SUPERUSER_ID).create(vals)
            else:
                # If a purchase order is found, adapt its `origin` field.
                if po.origin:
                    missing_origins = origins - set(po.origin.split(', '))
                    if missing_origins:
                        po.write({'origin': po.origin + ', ' + ', '.join(missing_origins)})
                else:
                    po.write({'origin': ', '.join(origins)})

            procurements_to_merge = self._get_procurements_to_merge(procurements)
            procurements = self._merge_procurements(procurements_to_merge)
            po_lines_by_product = {}
            grouped_po_lines = groupby(po.order_line.filtered(lambda l: not l.display_type and l.product_uom == l.product_id.uom_po_id).sorted(lambda l: l.product_id.id), key=lambda l: l.product_id.id)
            for product, po_lines in grouped_po_lines:
                po_lines_by_product[product] = self.env['purchase.order.line'].concat(*list(po_lines))
            po_line_values = []
            for procurement in procurements:
                po_lines = po_lines_by_product.get(procurement.product_id.id, self.env['purchase.order.line'])
                po_line = po_lines._find_candidate(*procurement)
                po_inv_line = po.split_line.filtered(lambda l : l.product_id.id == procurement.product_id.id and not l.sale_line_id)
                po_inv_cancel = False
                if po_inv_line:
                    if po_inv_line.product_qty > procurement.product_qty:
                        po_line = po_inv_line
                    elif po_inv_line.product_qty == procurement.product_qty:
                        po_line = po_inv_line
                        po_inv_cancel = True
                    else:
                        po_inv_cancel = True
                if po_line:
                    # If the procurement can be merge in an existing line. Directly
                    # write the new values on it.
                    vals = self._update_purchase_order_line(procurement.product_id,
                        procurement.product_qty, procurement.product_uom, company_id,
                        procurement.values, po_line)
                    po_line.write(vals)
                    if po_inv_cancel:
                        po_inv_line.action_cancel_pol()
                else:
                    # If it does not exist a PO line for current procurement.
                    # Generate the create values for it and add it to a list in
                    # order to create it in batch.
                    partner = procurement.values['supplier'].name
                    po_line_values.append(self._prepare_purchase_order_line(
                        procurement.product_id, procurement.product_qty,
                        procurement.product_uom, procurement.company_id,
                        procurement.values, po))
            self.env['purchase.order.line'].sudo().create(po_line_values)

    # @api.model
    # def _run_buy(self, procurements):
    #     if self.env.context.get('add_to_buy') or self.env.context.get('add_to_buy_merge_po'):
    #         self._run_buy_add_to_buy(procurements)
    #     else:
    #         self.add_vendor_to_product(procurements)
    #         other_procurements = []
    #         for procurement, rule in procurements:
    #             if procurement.values.get("split_sale_line_id"):
    #                 if procurement.values.get("split_sale_line_id").line_type == 'allocate_po':
    #                     continue
    #             other_procurements.append((procurement, rule))
    #         return super(StockRule, self)._run_buy(other_procurements)

    def _prepare_purchase_order(self, company_id, origins, values):
        res = super(StockRule, self)._prepare_purchase_order(company_id, origins, values)
        if values[0].get('split_sale_line_id').line_type == "buy":
            res['add_to_buy'] = True
        return res

    def _make_po_get_domain(self, company_id, values, partner):
        gpo = self.group_propagation_option
        group = (gpo == 'fixed' and self.group_id) or \
                (gpo == 'propagate' and 'group_id' in values and values['group_id']) or False

        domain = (
            ('partner_id', '=', partner.id),
            ('picking_type_id', '=', self.picking_type_id.id),
            ('company_id', '=', company_id.id),
            ('state', 'in', ('draft', 'sent')),
        )
        if values.get('split_sale_line_id').line_type == "buy":
            domain += (('add_to_buy', '=', True),)
        if group:
            domain += (('group_id', '=', group.id),)
        return domain
