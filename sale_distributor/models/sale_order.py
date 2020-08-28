# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import fields, models, api
from datetime import datetime


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    shipping_cost = fields.Float(string="Shipping Cost")
    order_line = fields.One2many('sale.order.line', 'order_id', string='Order Lines', 
        states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=False, auto_join=True,
        domain=[('line_split','=',False)])
    all_order_line = fields.One2many('sale.order.line', 'main_order_id', string='All Order Lines', 
        states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True, auto_join=True,
        domain=[('line_split','=',True)])

    def _action_confirm(self):
        self.all_order_line._action_launch_stock_rule()
        return super(SaleOrder, self)._action_confirm()

    @api.model
    def create(self, vals):
        res = super(SaleOrder, self).create(vals)
        if res.order_line:
            child_lines = res.mapped('order_line').mapped('sale_split_lines').filtered(lambda cl: not cl.order_id)
            if child_lines:
                child_lines.update({'order_id':res.id})
        return res

    def write(self, values):
        res = super(SaleOrder, self).write(values)
        if self.order_line:
            child_lines = self.mapped('order_line').mapped('sale_split_lines').filtered(lambda cl: not cl.order_id)
            if child_lines:
                child_lines.update({'order_id':self.id})
        return res


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.model
    def default_get(self, fields):
        result = super(SaleOrderLine, self).default_get(fields)
        adi_partner_id = self.env.ref('sale_distributor.res_partner_adi_address', raise_if_not_found=False)
        nv_partner_id = self.env.ref('sale_distributor.res_partner_nv_address', raise_if_not_found=False)
        sl_partner_id = self.env.ref('sale_distributor.res_partner_sl_address', raise_if_not_found=False)
        ss_partner_id = self.env.ref('sale_distributor.res_partner_ss_address', raise_if_not_found=False)
        jne_partner_id = self.env.ref('sale_distributor.res_partner_jne_address', raise_if_not_found=False)
        bnr_partner_id = self.env.ref('sale_distributor.res_partner_bnr_address', raise_if_not_found=False)
        wr_partner_id = self.env.ref('sale_distributor.res_partner_wr_address', raise_if_not_found=False)
        dfm_partner_id = self.env.ref('sale_distributor.res_partner_dfm_address', raise_if_not_found=False)
        bks_partner_id = self.env.ref('sale_distributor.res_partner_bks_address', raise_if_not_found=False)
        result.update({
            'adi_partner_id': adi_partner_id.id,
            'nv_partner_id': nv_partner_id.id,
            'sl_partner_id': sl_partner_id.id,
            'ss_partner_id': ss_partner_id.id,
            'jne_partner_id': jne_partner_id.id,
            'bnr_partner_id': bnr_partner_id.id,
            'wr_partner_id': wr_partner_id.id,
            'dfm_partner_id': dfm_partner_id.id,
            'bks_partner_id': bks_partner_id.id
        })
        return result

    def _default_adi_vendor_id(self):
        return self.env.ref('sale_distributor.res_partner_adi_address')

    order_id = fields.Many2one('sale.order', string='Order Reference', required=False, ondelete='cascade', index=True,
                               copy=True)
    phone_number = fields.Char(string="Phone Number")
    dropship_selection = fields.Selection([('Yes', 'Yes'), ('No', 'No')], string='Dropships')
    dropship_fee = fields.Float(string="Dropship Fee")
    order_min = fields.Date(string="Order Minimum")
    below_min_fee = fields.Float(string="Below Minimum Fee")
    free_freight_level = fields.Float(string="Free Freight Level")
    ships_from = fields.Char(string="Ship From")
    ship_cutoff_time = fields.Char(string="Shipping Cutoff Time")
    note = fields.Text(string="Note")

    list_price = fields.Float(string="List Price")
    lowest_cost = fields.Float(string="Lowest Cost")
    lowest_cost_source = fields.Char(string="Lowest Cost Source")
    total_stock = fields.Float(string="Total Stock")

    # ADI TAB
    adi_part_number = fields.Char(string="ADI Part Number")
    adi_case_qty = fields.Float(string="ADI Case Qty")
    adi_mo_qty = fields.Float(string="ADI MOQ")
    adi_sale_exp_date = fields.Date(string="ADI Sale Exp Date")
    adi_note = fields.Text(string="ADI Description")
    adi_actual_cost = fields.Float(string="ADI Actual Cost")
    adi_standard_cost = fields.Float(string="ADI Standard Cost")
    adi_price_match = fields.Float(string="ADI Price Match")
    adi_coded_price_flag = fields.Float(string="ADI Coded Price Flag")
    adi_sale_cost = fields.Float(string="ADI Sale Cost")
    adi_total_stock = fields.Float(string="ADI Total Stock")
    adi_cost_last_updated = fields.Datetime(string="ADI Cost Last Updated")
    adi_stock_last_updated = fields.Datetime(string="ADI Stock Last Updated")
    adi_partner_id = fields.Many2one('res.partner', string='ADI Vendor')
    adi_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="ADI Stock")
    # NV TAB
    nv_part_number = fields.Char(string="NV Part Number")
    nv_case_qty = fields.Float(string="NV Case Qty")
    nv_mo_qty = fields.Float(string="NV MOQ")
    nv_sale_exp_date = fields.Date(string="NV Sale Exp Date")
    nv_note = fields.Text(string="NV Description")
    nv_actual_cost = fields.Float(string="NV Actual Cost")
    nv_standard_cost = fields.Float(string="NV Standard Cost")
    nv_price_match = fields.Float(string="NV Price Match")
    nv_coded_price_flag = fields.Float(string="NV Coded Price Flag")
    nv_sale_cost = fields.Float(string="NV Sale Cost")
    nv_total_stock = fields.Float(string="NV Total Stock")
    nv_cost_last_updated = fields.Datetime(string="NV Cost Last Updated")
    nv_stock_last_updated = fields.Datetime(string="NV Stock Last Updated")
    nv_partner_id = fields.Many2one('res.partner', string='NV Vendor')
    nv_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'nv_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="NV Stock")
    # SL TAB
    sl_part_number = fields.Char(string="SL Part Number")
    sl_case_qty = fields.Float(string="SL Case Qty")
    sl_mo_qty = fields.Float(string="SL MOQ")
    sl_sale_exp_date = fields.Date(string="SL Sale Exp Date")
    sl_note = fields.Text(string="SL Description")
    sl_actual_cost = fields.Float(string="SL Actual Cost")
    sl_standard_cost = fields.Float(string="SL Standard Cost")
    sl_price_match = fields.Float(string="SL Price Match")
    sl_coded_price_flag = fields.Float(string="SL Coded Price Flag")
    sl_sale_cost = fields.Float(string="SL Sale Cost")
    sl_total_stock = fields.Float(string="SL Total Stock")
    sl_cost_last_updated = fields.Datetime(string="SL Cost Last Updated")
    sl_stock_last_updated = fields.Datetime(string="SL Stock Last Updated")
    sl_partner_id = fields.Many2one('res.partner', string='SL Vendor')
    sl_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'sl_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="SL Stock")
    # SS TAB
    ss_part_number = fields.Char(string="SS Part Number")
    ss_case_qty = fields.Float(string="SS Case Qty")
    ss_mo_qty = fields.Float(string="SS MOQ")
    ss_sale_exp_date = fields.Date(string="SS Sale Exp Date")
    ss_note = fields.Text(string="SS Description")
    ss_actual_cost = fields.Float(string="SS Actual Cost")
    ss_standard_cost = fields.Float(string="SS Standard Cost")
    ss_price_match = fields.Float(string="SS Price Match")
    ss_coded_price_flag = fields.Float(string="SS Coded Price Flag")
    ss_sale_cost = fields.Float(string="SS Sale Cost")
    ss_total_stock = fields.Float(string="SS Total Stock")
    ss_cost_last_updated = fields.Datetime(string="SS Cost Last Updated")
    ss_stock_last_updated = fields.Datetime(string="SS Stock Last Updated")
    ss_partner_id = fields.Many2one('res.partner', string='SS Vendor')
    ss_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'ss_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="SS Stock")
    # JNE TAB
    jne_part_number = fields.Char(string="JNE Part Number")
    jne_case_qty = fields.Float(string="JNE Case Qty")
    jne_mo_qty = fields.Float(string="JNE MOQ")
    jne_sale_exp_date = fields.Date(string="JNE Sale Exp Date")
    jne_note = fields.Text(string="JNE Description")
    jne_actual_cost = fields.Float(string="JNE Actual Cost")
    jne_standard_cost = fields.Float(string="JNE Standard Cost")
    jne_price_match = fields.Float(string="JNE Price Match")
    jne_coded_price_flag = fields.Float(string="JNE Coded Price Flag")
    jne_sale_cost = fields.Float(string="JNE Sale Cost")
    jne_total_stock = fields.Float(string="JNE Total Stock")
    jne_cost_last_updated = fields.Datetime(string="JNE Cost Last Updated")
    jne_stock_last_updated = fields.Datetime(string="JNE Stock Last Updated")
    jne_partner_id = fields.Many2one('res.partner', string='JNE Vendor')
    jne_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'jne_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="JNE Stock")
    # BNR TAB
    bnr_part_number = fields.Char(string="BNR Part Number")
    bnr_case_qty = fields.Float(string="BNR Case Qty")
    bnr_mo_qty = fields.Float(string="BNR MOQ")
    bnr_sale_exp_date = fields.Date(string="BNR Sale Exp Date")
    bnr_note = fields.Text(string="BNR Description")
    bnr_actual_cost = fields.Float(string="BNR Actual Cost")
    bnr_standard_cost = fields.Float(string="BNR Standard Cost")
    bnr_price_match = fields.Float(string="BNR Price Match")
    bnr_coded_price_flag = fields.Float(string="BNR Coded Price Flag")
    bnr_sale_cost = fields.Float(string="BNR Sale Cost")
    bnr_total_stock = fields.Float(string="BNR Total Stock")
    bnr_cost_last_updated = fields.Datetime(string="BNR Cost Last Updated")
    bnr_stock_last_updated = fields.Datetime(string="BNR Stock Last Updated")
    bnr_partner_id = fields.Many2one('res.partner', string='BNR Vendor')
    bnr_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'bnr_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="BNR Stock")
    # WR TAB
    wr_part_number = fields.Char(string="WR Part Number")
    wr_case_qty = fields.Float(string="WR Case Qty")
    wr_mo_qty = fields.Float(string="WR MOQ")
    wr_sale_exp_date = fields.Date(string="WR Sale Exp Date")
    wr_note = fields.Text(string="WR Description")
    wr_actual_cost = fields.Float(string="WR Actual Cost")
    wr_standard_cost = fields.Float(string="WR Standard Cost")
    wr_price_match = fields.Float(string="WR Price Match")
    wr_coded_price_flag = fields.Float(string="WR Coded Price Flag")
    wr_sale_cost = fields.Float(string="WR Sale Cost")
    wr_total_stock = fields.Float(string="WR Total Stock")
    wr_cost_last_updated = fields.Datetime(string="WR Cost Last Updated")
    wr_stock_last_updated = fields.Datetime(string="WR Stock Last Updated")
    wr_partner_id = fields.Many2one('res.partner', string='WR Vendor')
    wr_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'wr_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="WR Stock")
    # DFM TAB
    dfm_part_number = fields.Char(string="DFM Part Number")
    dfm_case_qty = fields.Float(string="DFM Case Qty")
    dfm_mo_qty = fields.Float(string="DFM MOQ")
    dfm_sale_exp_date = fields.Date(string="DFM Sale Exp Date")
    dfm_note = fields.Text(string="DFM Description")
    dfm_actual_cost = fields.Float(string="DFM Actual Cost")
    dfm_standard_cost = fields.Float(string="DFM Standard Cost")
    dfm_price_match = fields.Float(string="DFM Price Match")
    dfm_coded_price_flag = fields.Float(string="DFM Coded Price Flag")
    dfm_sale_cost = fields.Float(string="DFM Sale Cost")
    dfm_total_stock = fields.Float(string="DFM Total Stock")
    dfm_cost_last_updated = fields.Datetime(string="DFM Cost Last Updated")
    dfm_stock_last_updated = fields.Datetime(string="DFM Stock Last Updated")
    dfm_partner_id = fields.Many2one('res.partner', string='DFM Vendor')
    dfm_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'dfm_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="DFM Stock")
    # JMAC TAB
    jmac_allocated = fields.Float(string="Allocated")
    jmac_available = fields.Float(string="Available")
    jmac_onhand = fields.Float(string="On Hand")
    jmac_stock_ids = fields.Many2many('stock.quant', 'jmac_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="Jmac Stock")
    # BKS TAB
    bks_part_number = fields.Char(string="BKS Part Number")
    bks_case_qty = fields.Float(string="BKS Case Qty")
    bks_mo_qty = fields.Float(string="BKS MOQ")
    bks_sale_exp_date = fields.Date(string="BKS Sale Exp Date")
    bks_note = fields.Text(string="BKS Description")
    bks_actual_cost = fields.Float(string="BKS Actual Cost")
    bks_standard_cost = fields.Float(string="BKS Standard Cost")
    bks_price_match = fields.Float(string="BKS Price Match")
    bks_coded_price_flag = fields.Float(string="BKS Coded Price Flag")
    bks_sale_cost = fields.Float(string="BKS Sale Cost")
    bks_total_stock = fields.Float(string="BKS Total Stock")
    bks_cost_last_updated = fields.Datetime(string="BKS Cost Last Updated")
    bks_stock_last_updated = fields.Datetime(string="BKS Stock Last Updated")
    bks_partner_id = fields.Many2one('res.partner', string='BKS Vendor')
    bks_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'bks_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="BKS Stock")
    # OTV TAB
    partner_id = fields.Many2one('res.partner', string='Vendor')
    otv_cost = fields.Float(string="Cost")

    # Splited Line check
    line_split = fields.Boolean('Split')
    parent_line_id = fields.Many2one('sale.order.line', string="Parent Line")
    sale_split_lines = fields.One2many("sale.order.line", 'parent_line_id', string="Process Qty")
    vendor_id = fields.Many2one('res.partner', string='Line Vendor')
    line_type = fields.Selection([('buy','Buy'),('dropship','Dropship'),('stock','Stock')])
    main_order_id = fields.Many2one('sale.order', string='Sale Order', related='parent_line_id.order_id', ondelete='cascade', index=True,
                               copy=False)

    # def _prepare_procurement_group_vals(self):
    #     if self.main_order_id:
    #         return {
    #             'name': self.main_order_id.name,
    #             'move_type': self.main_order_id.picking_policy,
    #             'sale_id': self.main_order_id.id,
    #             'partner_id': self.main_order_id.partner_shipping_id.id,
    #         }
    #     return {
    #         'name': self.order_id.name,
    #         'move_type': self.order_id.picking_policy,
    #         'sale_id': self.order_id.id,
    #         'partner_id': self.order_id.partner_shipping_id.id,
    #     }

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """
        Launch procurement group run method with required/custom fields genrated by a
        sale order line. procurement group will launch '_run_pull', '_run_buy' or '_run_manufacture'
        depending on the sale order line product rule.
        """
        if not self.parent_line_id:
            return True
        return super(SaleOrderLine, self)._action_launch_stock_rule()


    @api.onchange('product_id')
    def onchange_product_id(self):
        if not self.product_id:
            return
        if self.product_id:
            # product_tmpl_id = self.product_id.product_tmpl_id
            jmac_stock_ids = self.env["stock.quant"].search([('product_id', '=', self.product_id.id),
                ('location_id.usage', '=', 'internal')])
            if jmac_stock_ids:
                self.jmac_onhand = self.product_id.qty_available
                self.jmac_available = self.product_id.qty_available
                self.jmac_stock_ids = [(6,0,jmac_stock_ids.ids)]
            if self.adi_partner_id:
                stock_master_line_id = self.env["vendor.stock.master.line"].search(
                    [('res_partner_id', '=', self.adi_partner_id.id),
                     ('product_id', '=', self.product_id.id)])
                if stock_master_line_id:
                    self.adi_vendor_stock_ids = [(6,0,stock_master_line_id.ids)]
                pricelist_id = self.product_id.seller_ids.search([('name' ,'=', self.adi_partner_id.id)], limit=1)
                if pricelist_id:
                    actual_cost = pricelist_id.price / pricelist_id.min_qty if pricelist_id.min_qty else pricelist_id.price 
                    self.adi_part_number = pricelist_id.product_code or ''
                    self.adi_case_qty = pricelist_id.min_qty or 0.0
                    self.adi_actual_cost = actual_cost or 0.0
                    self.adi_standard_cost = pricelist_id.price or 0.0
                else:
                    actual_cost = self.product_id.standard_price 
                    # self.adi_part_number = adi_pricelist_id.product_code or ''
                    # self.adi_case_qty = adi_pricelist_id.min_qty or 0.0
                    self.adi_actual_cost = actual_cost or 0.0
                    self.adi_standard_cost = actual_cost or 0.0

            if self.nv_partner_id:
                stock_master_line_id = self.env["vendor.stock.master.line"].search(
                    [('res_partner_id', '=', self.nv_partner_id.id),
                     ('product_id', '=', self.product_id.id)])
                if stock_master_line_id:
                    self.nv_vendor_stock_ids = [(6,0,stock_master_line_id.ids)]
                pricelist_id = self.product_id.seller_ids.search([('name' ,'=', self.nv_partner_id.id)], limit=1)
                if pricelist_id:
                    actual_cost = pricelist_id.price / pricelist_id.min_qty if pricelist_id.min_qty else pricelist_id.price 
                    self.nv_part_number = pricelist_id.product_code or ''
                    self.nv_case_qty = pricelist_id.min_qty or 0.0
                    self.nv_actual_cost = actual_cost or 0.0
                    self.nv_standard_cost = pricelist_id.price or 0.0
                else:
                    actual_cost = self.product_id.standard_price 
                    # self.adi_part_number = adi_pricelist_id.product_code or ''
                    # self.adi_case_qty = adi_pricelist_id.min_qty or 0.0
                    self.nv_actual_cost = actual_cost or 0.0
                    self.nv_standard_cost = actual_cost or 0.0

            if self.sl_partner_id:
                stock_master_line_id = self.env["vendor.stock.master.line"].search(
                    [('res_partner_id', '=', self.sl_partner_id.id),
                     ('product_id', '=', self.product_id.id)])
                if stock_master_line_id:
                    self.sl_vendor_stock_ids = [(6,0,stock_master_line_id.ids)]
                pricelist_id = self.product_id.seller_ids.search([('name' ,'=', self.sl_partner_id.id)], limit=1)
                if pricelist_id:
                    actual_cost = pricelist_id.price / pricelist_id.min_qty if pricelist_id.min_qty else pricelist_id.price 
                    self.sl_part_number = pricelist_id.product_code or ''
                    self.sl_case_qty = pricelist_id.min_qty or 0.0
                    self.sl_actual_cost = actual_cost or 0.0
                    self.sl_standard_cost = pricelist_id.price or 0.0
                else:
                    actual_cost = self.product_id.standard_price 
                    # self.adi_part_number = adi_pricelist_id.product_code or ''
                    # self.adi_case_qty = adi_pricelist_id.min_qty or 0.0
                    self.sl_actual_cost = actual_cost or 0.0
                    self.sl_standard_cost = actual_cost or 0.0
            if self.ss_partner_id:
                stock_master_line_id = self.env["vendor.stock.master.line"].search(
                    [('res_partner_id', '=', self.ss_partner_id.id),
                     ('product_id', '=', self.product_id.id)])
                if stock_master_line_id:
                    self.ss_vendor_stock_ids = [(6,0,stock_master_line_id.ids)]
                pricelist_id = self.product_id.seller_ids.search([('name' ,'=', self.ss_partner_id.id)], limit=1)
                if pricelist_id:
                    actual_cost = pricelist_id.price / pricelist_id.min_qty if pricelist_id.min_qty else pricelist_id.price 
                    self.ss_part_number = pricelist_id.product_code or ''
                    self.ss_case_qty = pricelist_id.min_qty or 0.0
                    self.ss_actual_cost = actual_cost or 0.0
                    self.ss_standard_cost = pricelist_id.price or 0.0
                else:
                    actual_cost = self.product_id.standard_price 
                    # self.adi_part_number = adi_pricelist_id.product_code or ''
                    # self.adi_case_qty = adi_pricelist_id.min_qty or 0.0
                    self.ss_actual_cost = actual_cost or 0.0
                    self.ss_standard_cost = actual_cost or 0.0
            if self.jne_partner_id:
                stock_master_line_id = self.env["vendor.stock.master.line"].search(
                    [('res_partner_id', '=', self.jne_partner_id.id),
                     ('product_id', '=', self.product_id.id)])
                if stock_master_line_id:
                    self.jne_vendor_stock_ids = [(6,0,stock_master_line_id.ids)]
                pricelist_id = self.product_id.seller_ids.search([('name' ,'=', self.jne_partner_id.id)], limit=1)
                if pricelist_id:
                    actual_cost = pricelist_id.price / pricelist_id.min_qty if pricelist_id.min_qty else pricelist_id.price 
                    self.jne_part_number = pricelist_id.product_code or ''
                    self.jne_case_qty = pricelist_id.min_qty or 0.0
                    self.jne_actual_cost = actual_cost or 0.0
                    self.jne_standard_cost = pricelist_id.price or 0.0
                else:
                    actual_cost = self.product_id.standard_price 
                    # self.adi_part_number = adi_pricelist_id.product_code or ''
                    # self.adi_case_qty = adi_pricelist_id.min_qty or 0.0
                    self.jne_actual_cost = actual_cost or 0.0
                    self.jne_standard_cost = actual_cost or 0.0

            if self.bnr_partner_id:
                stock_master_line_id = self.env["vendor.stock.master.line"].search(
                    [('res_partner_id', '=', self.bnr_partner_id.id),
                     ('product_id', '=', self.product_id.id)])
                if stock_master_line_id:
                    self.bnr_vendor_stock_ids = [(6,0,stock_master_line_id.ids)]
                pricelist_id = self.product_id.seller_ids.search([('name' ,'=', self.bnr_partner_id.id)], limit=1)
                if pricelist_id:
                    actual_cost = pricelist_id.price / pricelist_id.min_qty if pricelist_id.min_qty else pricelist_id.price 
                    self.bnr_part_number = pricelist_id.product_code or ''
                    self.bnr_case_qty = pricelist_id.min_qty or 0.0
                    self.bnr_actual_cost = actual_cost or 0.0
                    self.bnr_standard_cost = pricelist_id.price or 0.0
                else:
                    actual_cost = self.product_id.standard_price 
                    # self.adi_part_number = adi_pricelist_id.product_code or ''
                    # self.adi_case_qty = adi_pricelist_id.min_qty or 0.0
                    self.bnr_actual_cost = actual_cost or 0.0
                    self.bnr_standard_cost = actual_cost or 0.0

            if self.wr_partner_id:
                stock_master_line_id = self.env["vendor.stock.master.line"].search(
                    [('res_partner_id', '=', self.wr_partner_id.id),
                     ('product_id', '=', self.product_id.id)])
                if stock_master_line_id:
                    self.wr_vendor_stock_ids = [(6,0,stock_master_line_id.ids)]
                pricelist_id = self.product_id.seller_ids.search([('name' ,'=', self.wr_partner_id.id)], limit=1)
                if pricelist_id:
                    actual_cost = pricelist_id.price / pricelist_id.min_qty if pricelist_id.min_qty else pricelist_id.price 
                    self.wr_part_number = pricelist_id.product_code or ''
                    self.wr_case_qty = pricelist_id.min_qty or 0.0
                    self.wr_actual_cost = actual_cost or 0.0
                    self.wr_standard_cost = pricelist_id.price or 0.0
                else:
                    actual_cost = self.product_id.standard_price 
                    # self.adi_part_number = adi_pricelist_id.product_code or ''
                    # self.adi_case_qty = adi_pricelist_id.min_qty or 0.0
                    self.wr_actual_cost = actual_cost or 0.0
                    self.wr_standard_cost = actual_cost or 0.0
            if self.dfm_partner_id:
                stock_master_line_id = self.env["vendor.stock.master.line"].search(
                    [('res_partner_id', '=', self.dfm_partner_id.id),
                     ('product_id', '=', self.product_id.id)])
                if stock_master_line_id:
                    self.dfm_vendor_stock_ids = [(6,0,stock_master_line_id.ids)]
                pricelist_id = self.product_id.seller_ids.search([('name' ,'=', self.dfm_partner_id.id)], limit=1)
                if pricelist_id:
                    actual_cost = pricelist_id.price / pricelist_id.min_qty if pricelist_id.min_qty else pricelist_id.price 
                    self.dfm_part_number = pricelist_id.product_code or ''
                    self.dfm_case_qty = pricelist_id.min_qty or 0.0
                    self.dfm_actual_cost = actual_cost or 0.0
                    self.dfm_standard_cost = pricelist_id.price or 0.0
                else:
                    actual_cost = self.product_id.standard_price 
                    # self.adi_part_number = adi_pricelist_id.product_code or ''
                    # self.adi_case_qty = adi_pricelist_id.min_qty or 0.0
                    self.dfm_actual_cost = actual_cost or 0.0
                    self.dfm_standard_cost = actual_cost or 0.0
            if self.bks_partner_id:
                stock_master_line_id = self.env["vendor.stock.master.line"].search(
                    [('res_partner_id', '=', self.bks_partner_id.id),
                     ('product_id', '=', self.product_id.id)])
                if stock_master_line_id:
                    self.bks_vendor_stock_ids = [(6,0,stock_master_line_id.ids)]
                pricelist_id = self.product_id.seller_ids.search([('name' ,'=', self.bks_partner_id.id)], limit=1)
                if pricelist_id:
                    actual_cost = pricelist_id.price / pricelist_id.min_qty if pricelist_id.min_qty else pricelist_id.price 
                    self.bks_part_number = pricelist_id.product_code or ''
                    self.bks_case_qty = pricelist_id.min_qty or 0.0
                    self.bks_actual_cost = actual_cost or 0.0
                    self.bks_standard_cost = pricelist_id.price or 0.0
                else:
                    actual_cost = self.product_id.standard_price 
                    # self.adi_part_number = adi_pricelist_id.product_code or ''
                    # self.adi_case_qty = adi_pricelist_id.min_qty or 0.0
                    self.bks_actual_cost = actual_cost or 0.0
                    self.bks_standard_cost = actual_cost or 0.0
        return

    def split_line(self):
        ctx = self._context.copy()
        ctx.update({'default_qty': self.product_uom_qty,
                    'default_sale_line_id': self.id})
        model = 'notification.message'
        view_id = self.env.ref('sale_distributor.notification_message_form_view').id
        name = False
        if ctx.get('vendor') == 'adi':
            name = self.adi_partner_id
        elif ctx.get('vendor') == 'nv':
            name = self.nv_partner_id
        elif ctx.get('vendor') == 'ss':
            name = self.ss_partner_id
        elif ctx.get('vendor') == 'sl':
            name = self.sl_partner_id
        elif ctx.get('vendor') == 'jne':
            name = self.jne_partner_id
        elif ctx.get('vendor') == 'bnr':
            name = self.bnr_partner_id
        elif ctx.get('vendor') == 'wr':
            name = self.wr_partner_id
        elif ctx.get('vendor') == 'dfm':
            name = self.dfm_partner_id
        elif ctx.get('vendor') == 'bks':
            name = self.bks_partner_id
        wiz_name = ''
        msg = ''
        if ctx.get('ship_from_here',False):
            wiz_name = 'Ship from here'
            msg = 'Ship %s from here?' % self.product_id.name
            
        elif ctx.get('add_to_buy',False):
            wiz_name = 'Add to Buy'
            msg = 'Add %s to buy' % self.product_id.name
        elif ctx.get('dropship',False):
            wiz_name = 'Dropship'
            msg =  'Dropship %s' % self.product_id.name
        if name :
            ctx.update({'default_partner_id': name.id})
            wiz_name = name.name + ' ' + wiz_name
        ctx.update({'default_message': msg})
        return {
            'name': (wiz_name),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': model,
            'view_id': view_id,
            'target': 'new',
            'context': ctx,
        }

    # def dropship(self):
    #     ctx = self._context.copy()
    #     ctx.update({'default_qty': self.product_uom_qty,
    #                 'default_sale_line_id': self.id,
    #                 'default_message': 'Enter the quantity you want to dropship',
    #                 # 'vendor':'adi',
    #                 'dropship': True})
    #     model = 'notification.message'
    #     view_id = self.env.ref('sale_distributor.notification_message_form_view').id
    #     if ctx.get('vendor') == 'adi':
    #         name = self.adi_partner_id
    #     elif ctx.get('vendor') == 'nv':
    #         name = self.nv_partner_id
    #     elif ctx.get('vendor') == 'ss':
    #         name = self.ss_partner_id
    #     elif ctx.get('vendor') == 'sl':
    #         name = self.sl_partner_id
    #     elif ctx.get('vendor') == 'jne':
    #         name = self.jne_partner_id
    #     elif ctx.get('vendor') == 'bnr':
    #         name = self.bnr_partner_id
    #     elif ctx.get('vendor') == 'wr':
    #         name = self.wr_partner_id
    #     elif ctx.get('vendor') == 'dfm':
    #         name = self.dfm_partner_id
    #     elif ctx.get('vendor') == 'bks':
    #         name = self.bks_partner_id
    #     ctx.update({'default_partner_id': name.id})
    #     return {
    #         'name': (name.name + ' ' + 'Dropship'),
    #         'type': 'ir.actions.act_window',
    #         'view_mode': 'form',
    #         'res_model': model,
    #         'view_id': view_id,
    #         'target': 'new',
    #         'context': ctx,
    #     }

    # def ship_from_here(self):
    #     ctx = self._context.copy()
    #     model = 'notification.message'
    #     view_id = self.env.ref('sale_distributor.notification_message_form_view').id
    #     return {
    #         'name': ('Ship from Here'),
    #         'type': 'ir.actions.act_window',
    #         'view_mode': 'form',
    #         'res_model': model,
    #         'view_id': view_id,
    #         'target': 'new',
    #         'context': ctx,
    #     }

    def allocate(self):
        ctx = self._context.copy()
        model = 'notification.message'
        view_id = self.env.ref('sale_distributor.allocate_notification_message_form_view').id
        return {
            'name': ('Allocate'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': model,
            'view_id': view_id,
            'target': 'new',
            'context': ctx,
        }

    def _prepare_procurement_values(self, group_id=False):
        """ Prepare specific key for moves or other components that will be created from a stock rule
        comming from a sale order line. This method could be override in order to add other custom key that could
        be used in move/po creation.
        """
        values = super(SaleOrderLine, self)._prepare_procurement_values(group_id)
        self.ensure_one()
        if self.route_id and self.vendor_id:
            values.update({
                'supplier_id': self.vendor_id,
                })
        return values