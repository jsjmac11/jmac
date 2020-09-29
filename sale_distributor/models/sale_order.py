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

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    order_line = fields.One2many('sale.order.line', 'order_id', string='Order Lines',
        states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=False, auto_join=True,
        domain=[('line_split','=',False)])
    # all_order_line = fields.One2many('sale.order.line', 'main_order_id', string='Process Order Lines', 
    #     states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True, auto_join=True,
    #     domain=[('line_split','=',True)])

    split_line_ids = fields.One2many('sale.order.line', compute='_compute_split_lines')
    is_process_line = fields.Boolean(string="Is Process Qty",
        compute='_compute_is_process_qty',
        help='Technical field used to see if we have process qty.')
    qty_all = fields.Boolean(string="All Qty",
        compute='_compute_is_process_qty',
        help='Technical field used to see if we have process qty.')

    @api.depends('order_line','order_line.sale_split_lines')
    def _compute_is_process_qty(self):
        for order in self:
            lines = order.order_line.filtered(lambda l: not l.is_delivery)
            ordered_qty = sum(lines.mapped('product_uom_qty'))
            processed_qty = sum(lines.mapped('sale_split_lines').mapped('product_uom_qty'))
            if processed_qty == ordered_qty:
                qty_all = True
            else:
                qty_all = False
            order.is_process_line = any(order.order_line.mapped('sale_split_lines'))
            order.qty_all = qty_all
            

    @api.depends('order_line','order_line.sale_split_lines')
    def _compute_split_lines(self):
        for record in self:
            record.split_line_ids = record.order_line.sale_split_lines


    # @api.onchange('partner_id')
    # def onchange_partner_id(self):
    #     res = super(SaleOrder, self).onchange_partner_id()
    #     return res

    def _action_confirm(self):
        self.split_line_ids._action_launch_stock_rule()
        return super(SaleOrder, self)._action_confirm()

    def action_confirm(self):
        """
        Creates the stock.picking normally with call to Super. If the pick has more than one split line
        item. If so, looks to see if any of the split lines are "Ship To Here", indicated by the line
        type of "stock". For each of the Ship To Here split lines, creates a new pick and moves that line
        to the new pick.
        """
        res = super(SaleOrder, self).action_confirm()
        for picking in self.picking_ids.filtered(lambda r: len(r.move_lines) > 1):
            lines_by_type = {type: picking.move_lines.filtered(lambda r: r.sale_line_id.line_type == type) 
                for type in ['stock', 'buy', 'dropship']}
            # Only create the extra ticket if there is more than one stock split line and there is one 
            # split line that is not a stock split line
            if len(lines_by_type['stock']) > 0 and len(lines_by_type['stock']) < len(picking.move_lines): 
                new_picking = picking.copy({'move_lines': [], 
                                            'move_line_ids_without_package': [],
                                            'move_line_ids': [],
                                            })
                for move_line in lines_by_type['stock']:
                    move_line.picking_id = new_picking
                    move_line.move_line_ids.picking_id = new_picking
        return res

    def action_cancel(self):
        res = super(SaleOrder, self).action_cancel()
        self.split_line_ids.unlink()
        return res

    def _genrate_line_sequence(self):
        no = 1
        for l in self.order_line:
            l.sequence_ref = no
            count = 0
            for sl in l.sale_split_lines:
                res = string.ascii_uppercase[count]
                sl.sequence_ref = str(no) + res
                count +=1
            no += 1
        return True

    @api.model
    def create(self, vals):
        res = super(SaleOrder, self).create(vals)
        if vals.get('order_line'):
            child_lines = res.mapped('order_line').mapped('sale_split_lines').filtered(lambda cl: not cl.order_id)
            if child_lines:
                child_lines.update({'order_id':res.id})
            res._genrate_line_sequence()     
        return res

    def write(self, values):
        res = super(SaleOrder, self).write(values)
        if values.get('order_line'):
            child_lines = self.mapped('order_line').mapped('sale_split_lines').filtered(lambda cl: not cl.order_id)
            if child_lines:
                child_lines.update({'order_id':self.id})
            self._genrate_line_sequence()
        return res

    def confirm_purchase(self):
        self.action_confirm()
        purchase_line_data = self.env['purchase.order.line'].search([('sale_order_id', 'in', self.ids)])
        dropship_purchase_ids = purchase_line_data.mapped('order_id').filtered(lambda po: po.dest_address_id)
        if dropship_purchase_ids:
            dropship_purchase_ids.button_confirm()
        return True

    def order_process(self):
        ctx = self._context.copy()
        ctx.update({'default_order_id': self.id})
        model = 'notification.message'
        view_id = self.env.ref('sale_distributor.notification_message_form_view').id
        wiz_name = ''
        msg = 'Please Select Vendor for '
        if ctx.get('ship_from_here',False):
            wiz_name = 'Ship from here'
            msg += 'Ship from here?'
        elif ctx.get('add_to_buy',False):
            wiz_name = 'Add to Buy'
            msg += 'Add to buy'
        elif ctx.get('dropship',False):
            wiz_name = 'Dropship'
            msg +=  'Dropship'
        elif ctx.get('allocate',False):
            wiz_name = 'Allocate'
            msg += 'Allocate'
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

    @api.model
    def fields_view_get(self, view_id=None, view_type='tree', toolbar=False, submenu=False):
        res = super(SaleOrder, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'tree':
            quotation_view_id = self.env.ref('sale.view_quotation_tree_with_onboarding').id
            order_view_id = self.env.ref('sale.view_order_tree').id
            if view_id == quotation_view_id:
                action = res['toolbar']['action']
                for rec in action:
                    if rec['name'] == 'Create invoices':
                        res['toolbar']['action'].remove(rec)
            if view_id == order_view_id:
                action = res['toolbar']['action']
                for rec in action:
                    if rec['name'] == 'Mark Quotation as Sent':
                        res['toolbar']['action'].remove(rec)
        return res

    def _activity_cancel_on_purchase(self):
        """ If some SO are cancelled, we need to put an activity on their generated purchase. If sale lines of
            different sale orders impact different purchase, we only want one activity to be attached.
        """
        res = super(SaleOrder, self)._activity_cancel_on_purchase()
        if self.mapped('split_line_ids').ids:
            purchase_to_notify_map = {}  # map PO -> recordset of SOL as {purchase.order: set(sale.orde.liner)}

            purchase_order_lines = self.env['purchase.order.line'].search([('sale_line_id', 'in', self.mapped('split_line_ids').ids), ('state', '!=', 'cancel')])
            for purchase_line in purchase_order_lines:
                purchase_to_notify_map.setdefault(purchase_line.order_id, self.env['sale.order.line'])
                purchase_to_notify_map[purchase_line.order_id] |= purchase_line.sale_line_id

            for purchase_order, sale_order_lines in purchase_to_notify_map.items():
                purchase_order.activity_schedule_with_view('mail.mail_activity_data_warning',
                    user_id=purchase_order.user_id.id or self.env.uid,
                    views_or_xmlid='sale_purchase.exception_purchase_on_sale_cancellation',
                    render_context={
                        'sale_orders': sale_order_lines.mapped('order_id'),
                        'sale_order_lines': sale_order_lines,
                })

    def _add_supplier_to_product(self):
        # Add the partner in the supplier list of the product if the supplier is not registered for
        # this product. We limit to 10 the number of suppliers for a product to avoid the mess that
        # could be caused for some generic products ("Miscellaneous").
        for line in self.order_line:
            # Do not add a contact as a supplier
            partner = self.partner_id if not self.partner_id.parent_id else self.partner_id.parent_id
            if line.product_id and partner not in line.product_id.seller_ids.mapped('name') and len(line.product_id.seller_ids) <= 10:
                # Convert the price in the right currency.
                currency = partner.property_purchase_currency_id or self.env.company.currency_id
                price = self.currency_id._convert(line.price_unit, currency, line.company_id, line.date_order or fields.Date.today(), round=False)
                # Compute the price for the template's UoM, because the supplier's UoM is related to that UoM.
                if line.product_id.product_tmpl_id.uom_po_id != line.product_uom:
                    default_uom = line.product_id.product_tmpl_id.uom_po_id
                    price = line.product_uom._compute_price(price, default_uom)

                supplierinfo = {
                    'name': partner.id,
                    'sequence': max(line.product_id.seller_ids.mapped('sequence')) + 1 if line.product_id.seller_ids else 1,
                    'min_qty': 0.0,
                    'price': price,
                    'currency_id': currency.id,
                    'delay': 0,
                }
                # In case the order partner is a contact address, a new supplierinfo is created on
                # the parent company. In this case, we keep the product name and code.
                seller = line.product_id._select_seller(
                    partner_id=line.partner_id,
                    quantity=line.product_qty,
                    date=line.order_id.date_order and line.order_id.date_order.date(),
                    uom_id=line.product_uom)
                if seller:
                    supplierinfo['product_name'] = seller.product_name
                    supplierinfo['product_code'] = seller.product_code
                vals = {
                    'seller_ids': [(0, 0, supplierinfo)],
                }
                try:
                    line.product_id.write(vals)
                except AccessError:  # no write access rights -> just ignore
                    break



class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    _order = 'order_id, id, sequence_ref'

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

    order_id = fields.Many2one('sale.order', string='Order Reference', required=False, ondelete='cascade', index=True,
                               copy=False)
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
    total_stock = fields.Float(string="Total Stock", digits='Product Unit of Measure')

    # ADI TAB
    adi_part_number = fields.Char(string="ADI Part Number")
    adi_case_qty = fields.Float(string="ADI Case Qty", digits='Product Unit of Measure')
    adi_mo_qty = fields.Float(string="ADI MOQ", digits='Product Unit of Measure')
    adi_sale_exp_date = fields.Date(string="ADI Sale Exp Date")
    adi_note = fields.Text(string="ADI Description")
    adi_actual_cost = fields.Float(string="ADI Actual Cost")
    adi_standard_cost = fields.Float(string="ADI Standard Cost")
    adi_price_match = fields.Float(string="ADI Price Match")
    adi_coded_price_flag = fields.Float(string="ADI Coded Price Flag")
    adi_sale_cost = fields.Float(string="ADI Sale Cost")
    adi_total_stock = fields.Float(string="ADI Total Stock", digits='Product Unit of Measure')
    adi_cost_last_updated = fields.Datetime(string="ADI Cost Last Updated")
    adi_stock_last_updated = fields.Datetime(string="ADI Stock Last Updated")
    adi_partner_id = fields.Many2one('res.partner', string='ADI Vendor')
    adi_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="ADI Stock")
    adi_tab_color = fields.Char(string="ADI Tab Color", compute='_compute_adi_tab_color')
    
    @api.depends('product_id', 'adi_vendor_stock_ids')
    def _compute_adi_tab_color(self):
        """
        Gives a color scheme for the vendor tab depending on whether the vendor carries the product
        and has it in inventory.
        """
        if bool(self.adi_vendor_stock_ids):
            if self.adi_vendor_stock_ids.case_qty > 0:
                self.adi_tab_color = 'green_blue'
            else:
                self.adi_tab_color = 'green'
        else:
            self.adi_tab_color = 'grey'

    # NV TAB
    nv_part_number = fields.Char(string="NV Part Number")
    nv_case_qty = fields.Float(string="NV Case Qty", digits='Product Unit of Measure')
    nv_mo_qty = fields.Float(string="NV MOQ", digits='Product Unit of Measure')
    nv_sale_exp_date = fields.Date(string="NV Sale Exp Date")
    nv_note = fields.Text(string="NV Description")
    nv_actual_cost = fields.Float(string="NV Actual Cost")
    nv_standard_cost = fields.Float(string="NV Standard Cost")
    nv_price_match = fields.Float(string="NV Price Match")
    nv_coded_price_flag = fields.Float(string="NV Coded Price Flag")
    nv_sale_cost = fields.Float(string="NV Sale Cost")
    nv_total_stock = fields.Float(string="NV Total Stock", digits='Product Unit of Measure')
    nv_cost_last_updated = fields.Datetime(string="NV Cost Last Updated")
    nv_stock_last_updated = fields.Datetime(string="NV Stock Last Updated")
    nv_partner_id = fields.Many2one('res.partner', string='NV Vendor')
    nv_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'nv_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="NV Stock")
    nv_tab_color = fields.Char(string="NV Tab Color", compute='_compute_nv_tab_color')

    @api.depends('product_id', 'nv_vendor_stock_ids')
    def _compute_nv_tab_color(self):
        """
        Gives a color scheme for the vendor tab depending on whether the vendor carries the product
        and has it in inventory.
        """
        if bool(self.nv_vendor_stock_ids):
            if self.nv_vendor_stock_ids.case_qty > 0:
                self.nv_tab_color = 'green_blue'
            else:
                self.nv_tab_color = 'green'
        else:
            self.nv_tab_color = 'grey'

    # SL TAB
    sl_part_number = fields.Char(string="SL Part Number")
    sl_case_qty = fields.Float(string="SL Case Qty", digits='Product Unit of Measure')
    sl_mo_qty = fields.Float(string="SL MOQ", digits='Product Unit of Measure')
    sl_sale_exp_date = fields.Date(string="SL Sale Exp Date")
    sl_note = fields.Text(string="SL Description")
    sl_actual_cost = fields.Float(string="SL Actual Cost")
    sl_standard_cost = fields.Float(string="SL Standard Cost")
    sl_price_match = fields.Float(string="SL Price Match")
    sl_coded_price_flag = fields.Float(string="SL Coded Price Flag")
    sl_sale_cost = fields.Float(string="SL Sale Cost")
    sl_total_stock = fields.Float(string="SL Total Stock", digits='Product Unit of Measure')
    sl_cost_last_updated = fields.Datetime(string="SL Cost Last Updated")
    sl_stock_last_updated = fields.Datetime(string="SL Stock Last Updated")
    sl_partner_id = fields.Many2one('res.partner', string='SL Vendor')
    sl_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'sl_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="SL Stock")
    sl_tab_color = fields.Char(string="SL Tab Color", compute='_compute_sl_tab_color')

    @api.depends('product_id', 'sl_vendor_stock_ids')
    def _compute_sl_tab_color(self):
        """
        Gives a color scheme for the vendor tab depending on whether the vendor carries the product
        and has it in inventory.
        """
        if bool(self.sl_vendor_stock_ids):
            if self.sl_vendor_stock_ids.case_qty > 0:
                self.sl_tab_color = 'green_blue'
            else:
                self.sl_tab_color = 'green'
        else:
            self.sl_tab_color = 'grey'
                                                        
    # SS TAB
    ss_part_number = fields.Char(string="SS Part Number")
    ss_case_qty = fields.Float(string="SS Case Qty", digits='Product Unit of Measure')
    ss_mo_qty = fields.Float(string="SS MOQ", digits='Product Unit of Measure')
    ss_sale_exp_date = fields.Date(string="SS Sale Exp Date")
    ss_note = fields.Text(string="SS Description")
    ss_actual_cost = fields.Float(string="SS Actual Cost")
    ss_standard_cost = fields.Float(string="SS Standard Cost")
    ss_price_match = fields.Float(string="SS Price Match")
    ss_coded_price_flag = fields.Float(string="SS Coded Price Flag")
    ss_sale_cost = fields.Float(string="SS Sale Cost")
    ss_total_stock = fields.Float(string="SS Total Stock", digits='Product Unit of Measure')
    ss_cost_last_updated = fields.Datetime(string="SS Cost Last Updated")
    ss_stock_last_updated = fields.Datetime(string="SS Stock Last Updated")
    ss_partner_id = fields.Many2one('res.partner', string='SS Vendor')
    ss_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'ss_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="SS Stock")
    ss_tab_color = fields.Char(string="SS Tab Color", compute='_compute_ss_tab_color')

    @api.depends('product_id', 'ss_vendor_stock_ids')
    def _compute_ss_tab_color(self):
        """
        Gives a color scheme for the vendor tab depending on whether the vendor carries the product
        and has it in inventory.
        """
        if bool(self.ss_vendor_stock_ids):
            if self.ss_vendor_stock_ids.case_qty > 0:
                self.ss_tab_color = 'green_blue'
            else:
                self.ss_tab_color = 'green'
        else:
            self.ss_tab_color = 'grey'

    # JNE TAB
    jne_part_number = fields.Char(string="JNE Part Number")
    jne_case_qty = fields.Float(string="JNE Case Qty", digits='Product Unit of Measure')
    jne_mo_qty = fields.Float(string="JNE MOQ", digits='Product Unit of Measure')
    jne_sale_exp_date = fields.Date(string="JNE Sale Exp Date")
    jne_note = fields.Text(string="JNE Description")
    jne_actual_cost = fields.Float(string="JNE Actual Cost")
    jne_standard_cost = fields.Float(string="JNE Standard Cost")
    jne_price_match = fields.Float(string="JNE Price Match")
    jne_coded_price_flag = fields.Float(string="JNE Coded Price Flag")
    jne_sale_cost = fields.Float(string="JNE Sale Cost")
    jne_total_stock = fields.Float(string="JNE Total Stock", digits='Product Unit of Measure')
    jne_cost_last_updated = fields.Datetime(string="JNE Cost Last Updated")
    jne_stock_last_updated = fields.Datetime(string="JNE Stock Last Updated")
    jne_partner_id = fields.Many2one('res.partner', string='JNE Vendor')
    jne_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'jne_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="JNE Stock")
    jne_tab_color = fields.Char(string="JNE Tab Color", compute='_compute_jne_tab_color')

    @api.depends('product_id', 'jne_vendor_stock_ids')
    def _compute_jne_tab_color(self):
        """
        Gives a color scheme for the vendor tab depending on whether the vendor carries the product
        and has it in inventory.
        """
        if bool(self.jne_vendor_stock_ids):
            if self.jne_vendor_stock_ids.case_qty > 0:
                self.jne_tab_color = 'green_blue'
            else:
                self.jne_tab_color = 'green'
        else:
            self.jne_tab_color = 'grey'

    # BNR TAB
    bnr_part_number = fields.Char(string="BNR Part Number")
    bnr_case_qty = fields.Float(string="BNR Case Qty", digits='Product Unit of Measure')
    bnr_mo_qty = fields.Float(string="BNR MOQ", digits='Product Unit of Measure')
    bnr_sale_exp_date = fields.Date(string="BNR Sale Exp Date")
    bnr_note = fields.Text(string="BNR Description")
    bnr_actual_cost = fields.Float(string="BNR Actual Cost")
    bnr_standard_cost = fields.Float(string="BNR Standard Cost")
    bnr_price_match = fields.Float(string="BNR Price Match")
    bnr_coded_price_flag = fields.Float(string="BNR Coded Price Flag")
    bnr_sale_cost = fields.Float(string="BNR Sale Cost")
    bnr_total_stock = fields.Float(string="BNR Total Stock", digits='Product Unit of Measure')
    bnr_cost_last_updated = fields.Datetime(string="BNR Cost Last Updated")
    bnr_stock_last_updated = fields.Datetime(string="BNR Stock Last Updated")
    bnr_partner_id = fields.Many2one('res.partner', string='BNR Vendor')
    bnr_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'bnr_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="BNR Stock")
    bnr_tab_color = fields.Char(string="BNR Tab Color", compute='_compute_bnr_tab_color')

    @api.depends('product_id', 'bnr_vendor_stock_ids')
    def _compute_bnr_tab_color(self):
        """
        Gives a color scheme for the vendor tab depending on whether the vendor carries the product
        and has it in inventory.
        """
        if bool(self.bnr_vendor_stock_ids):
            if self.bnr_vendor_stock_ids.case_qty > 0:
                self.bnr_tab_color = 'green_blue'
            else:
                self.bnr_tab_color = 'green'
        else:
            self.bnr_tab_color = 'grey'

    # WR TAB
    wr_part_number = fields.Char(string="WR Part Number")
    wr_case_qty = fields.Float(string="WR Case Qty", digits='Product Unit of Measure')
    wr_mo_qty = fields.Float(string="WR MOQ", digits='Product Unit of Measure')
    wr_sale_exp_date = fields.Date(string="WR Sale Exp Date")
    wr_note = fields.Text(string="WR Description")
    wr_actual_cost = fields.Float(string="WR Actual Cost")
    wr_standard_cost = fields.Float(string="WR Standard Cost")
    wr_price_match = fields.Float(string="WR Price Match")
    wr_coded_price_flag = fields.Float(string="WR Coded Price Flag")
    wr_sale_cost = fields.Float(string="WR Sale Cost")
    wr_total_stock = fields.Float(string="WR Total Stock", digits='Product Unit of Measure')
    wr_cost_last_updated = fields.Datetime(string="WR Cost Last Updated")
    wr_stock_last_updated = fields.Datetime(string="WR Stock Last Updated")
    wr_partner_id = fields.Many2one('res.partner', string='WR Vendor')
    wr_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'wr_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="WR Stock")
    wr_tab_color = fields.Char(string="WR Tab Color", compute='_compute_wr_tab_color')

    @api.depends('product_id', 'wr_vendor_stock_ids')
    def _compute_wr_tab_color(self):
        """
        Gives a color scheme for the vendor tab depending on whether the vendor carries the product
        and has it in inventory.
        """
        if bool(self.wr_vendor_stock_ids):
            if self.wr_vendor_stock_ids.case_qty > 0:
                self.wr_tab_color = 'green_blue'
            else:
                self.wr_tab_color = 'green'
        else:
            self.wr_tab_color = 'grey'

    # DFM TAB
    dfm_part_number = fields.Char(string="DFM Part Number")
    dfm_case_qty = fields.Float(string="DFM Case Qty", digits='Product Unit of Measure')
    dfm_mo_qty = fields.Float(string="DFM MOQ", digits='Product Unit of Measure')
    dfm_sale_exp_date = fields.Date(string="DFM Sale Exp Date")
    dfm_note = fields.Text(string="DFM Description")
    dfm_actual_cost = fields.Float(string="DFM Actual Cost")
    dfm_standard_cost = fields.Float(string="DFM Standard Cost")
    dfm_price_match = fields.Float(string="DFM Price Match")
    dfm_coded_price_flag = fields.Float(string="DFM Coded Price Flag")
    dfm_sale_cost = fields.Float(string="DFM Sale Cost")
    dfm_total_stock = fields.Float(string="DFM Total Stock", digits='Product Unit of Measure')
    dfm_cost_last_updated = fields.Datetime(string="DFM Cost Last Updated")
    dfm_stock_last_updated = fields.Datetime(string="DFM Stock Last Updated")
    dfm_partner_id = fields.Many2one('res.partner', string='DFM Vendor')
    dfm_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'dfm_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="DFM Stock")
    dfm_tab_color = fields.Char(string="DFM Tab Color", compute='_compute_dfm_tab_color')

    @api.depends('product_id', 'dfm_vendor_stock_ids')
    def _compute_dfm_tab_color(self):
        """
        Gives a color scheme for the vendor tab depending on whether the vendor carries the product
        and has it in inventory.
        """
        if bool(self.dfm_vendor_stock_ids):
            if self.dfm_vendor_stock_ids.case_qty > 0:
                self.dfm_tab_color = 'green_blue'
            else:
                self.dfm_tab_color = 'green'
        else:
            self.dfm_tab_color = 'grey'

    # JMAC TAB
    jmac_allocated = fields.Float(string="Allocated", digits='Product Unit of Measure')
    jmac_available = fields.Float(string="Available", digits='Product Unit of Measure')
    jmac_onhand = fields.Float(string="On Hand", digits='Product Unit of Measure')
    jmac_stock_ids = fields.Many2many('stock.quant', 'jmac_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="Jmac Stock")
    inbound_stock_lines = fields.One2many("inbound.stock", 'sale_line_id', string="Inbound Stock", readonly="1")

    # BKS TAB
    bks_part_number = fields.Char(string="BKS Part Number")
    bks_case_qty = fields.Float(string="BKS Case Qty", digits='Product Unit of Measure')
    bks_mo_qty = fields.Float(string="BKS MOQ", digits='Product Unit of Measure')
    bks_sale_exp_date = fields.Date(string="BKS Sale Exp Date")
    bks_note = fields.Text(string="BKS Description")
    bks_actual_cost = fields.Float(string="BKS Actual Cost")
    bks_standard_cost = fields.Float(string="BKS Standard Cost")
    bks_price_match = fields.Float(string="BKS Price Match")
    bks_coded_price_flag = fields.Float(string="BKS Coded Price Flag")
    bks_sale_cost = fields.Float(string="BKS Sale Cost")
    bks_total_stock = fields.Float(string="BKS Total Stock", digits='Product Unit of Measure')
    bks_cost_last_updated = fields.Datetime(string="BKS Cost Last Updated")
    bks_stock_last_updated = fields.Datetime(string="BKS Stock Last Updated")
    bks_partner_id = fields.Many2one('res.partner', string='BKS Vendor')
    bks_vendor_stock_ids = fields.Many2many('vendor.stock.master.line', 'bks_sol_vendor_stock_rel',
                                            'line_id', 'vendor_stock_id', string="BKS Stock")
    bks_tab_color = fields.Char(string="BKS Tab Color", compute='_compute_bks_tab_color')

    @api.depends('product_id', 'bks_vendor_stock_ids')
    def _compute_bks_tab_color(self):
        """
        Gives a color scheme for the vendor tab depending on whether the vendor carries the product
        and has it in inventory.
        """
        if bool(self.bks_vendor_stock_ids):
            if self.bks_vendor_stock_ids.case_qty > 0:
                self.bks_tab_color = 'green_blue'
            else:
                self.bks_tab_color = 'green'
        else:
            self.bks_tab_color = 'grey'

    # OTV TAB
    partner_id = fields.Many2one('res.partner', string='Vendor')
    otv_cost = fields.Float(string="Cost")

    # Splited Line check
    line_split = fields.Boolean('Split')
    parent_line_id = fields.Many2one('sale.order.line', string="Parent Line")
    sale_split_lines = fields.One2many("sale.order.line", 'parent_line_id', string="Process Qty",  ondelete='cascade')
    vendor_id = fields.Many2one('res.partner', string='Line Vendor')
    vendor_unit_price= fields
    line_type = fields.Selection([('buy','Buy'),('dropship','Dropship'),('stock','Ship'),('allocate','Allocated')])
    main_order_id = fields.Many2one('sale.order', string='Sale Order', related='parent_line_id.order_id', ondelete='cascade', index=True,
                               copy=False)
    vendor_price_unit = fields.Float(string='Vendor Unit Price', digits='Product Price')
    sequence_ref = fields.Char('No.')
    substitute_product_id = fields.Many2one(
        'product.product', string='Substitute Product', domain="[('sale_ok', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        change_default=True, ondelete='restrict', check_company=True)  # Unrequired company
    substitute_product_template_id = fields.Many2one(
        'product.template', string='Substitute Product Template',
        related="substitute_product_id.product_tmpl_id", domain=[('sale_ok', '=', True)])

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """
        Launch procurement group run method with required/custom fields genrated by a
        sale order line. procurement group will launch '_run_pull', '_run_buy' or '_run_manufacture'
        depending on the sale order line product rule.
        """
        for line in self:
            if not line.parent_line_id: # Shortcuts if not a "split line"
                return True
        return super(SaleOrderLine, self)._action_launch_stock_rule()

    @api.model
    def create(self, vals):
        res = super(SaleOrderLine, self).create(vals)
        if vals.get('is_delivery'):
            res.order_id._genrate_line_sequence()     
        return res

    def write(self, values):
        res = super(SaleOrderLine, self).write(values)
        if values.get('is_delivery'):
            self.order_id._genrate_line_sequence()
        return res

    def vendor_price_stock(self, partner_id, product_uom_qty,params,vendor):
        product_id = self.product_id
        if self.substitute_product_id:
            product_id = self.substitute_product_id
        pricelist_id = product_id._select_seller(
                                                partner_id=partner_id,
                                                quantity=product_uom_qty,
                                                date=self.order_id.date_order and self.order_id.date_order.date(),
                                                uom_id=self.product_uom,
                                                params=params)
        actual_cost = pricelist_id.price / pricelist_id.min_qty if pricelist_id.min_qty else pricelist_id.price 
        values = {vendor+'_part_number' : pricelist_id.product_code or '',
                  vendor+'_case_qty' : pricelist_id.min_qty or 0.0,
                  vendor+'_actual_cost' : actual_cost or 0.0,
                  vendor+'_standard_cost' : pricelist_id.price or 0.0,
                  vendor+'_sale_exp_date' : pricelist_id.date_end}
        vendor_cost = {}
        stock_sum = 0.0
        stock_master_line_id = self.env["vendor.stock.master.line"].search(
                    [('res_partner_id', '=', partner_id.id),
                     ('product_id', '=', product_id.id),
                     ('case_qty','!=',0.0)])
        if stock_master_line_id:
            if actual_cost:
                vendor_cost = {partner_id: actual_cost}
            stock_sum = sum(stock_master_line_id.mapped('case_qty'))
            values.update({vendor+'_total_stock' : stock_sum,
             vendor+'_vendor_stock_ids' : [(6,0,stock_master_line_id.ids)]})
        return [values, vendor_cost, stock_sum]

    @api.onchange('product_id','substitute_product_id')
    def product_id_change(self):
        self.lowest_cost_source = ''
        self.adi_part_number = self.nv_part_number = self.jne_part_number = ''
        self.sl_part_number = self.ss_part_number = self.bnr_part_number = ''
        self.wr_part_number = self.dfm_part_number = self.bks_part_number = ''
        self.lowest_cost = self.jmac_onhand  = self.jmac_available = 0.0
        self.adi_case_qty = self.adi_actual_cost = self.adi_standard_cost = 0.0
        self.nv_case_qty = self.nv_actual_cost = self.nv_standard_cost = 0.0
        self.jne_case_qty = self.jne_actual_cost = self.jne_standard_cost = 0.0
        self.sl_case_qty = self.sl_actual_cost = self.sl_standard_cost = 0.0
        self.ss_case_qty = self.ss_actual_cost = self.ss_standard_cost = 0.0
        self.bnr_case_qty = self.bnr_actual_cost = self.bnr_standard_cost = 0.0
        self.wr_case_qty = self.wr_actual_cost = self.wr_standard_cost = 0.0
        self.dfm_case_qty = self.dfm_actual_cost = self.dfm_standard_cost = 0.0
        self.bks_case_qty = self.bks_actual_cost = self.bks_standard_cost = 0.0
        self.adi_sale_exp_date = self.nv_sale_exp_date = self.jne_sale_exp_date = False
        self.sl_sale_exp_date = self.ss_sale_exp_date = self.bnr_sale_exp_date = False
        self.wr_sale_exp_date = self.dfm_sale_exp_date = self.bks_sale_exp_date = False
        self.jmac_stock_ids = self.inbound_stock_lines = self.adi_vendor_stock_ids = [(6,0,[])]
        self.nv_vendor_stock_ids = self.jne_vendor_stock_ids = self.sl_vendor_stock_ids = [(6,0,[])]
        self.ss_vendor_stock_ids = self.bnr_vendor_stock_ids = self.wr_vendor_stock_ids = [(6,0,[])]
        self.dfm_vendor_stock_ids = self.bks_vendor_stock_ids = [(6,0,[])]
        self.adi_total_stock = self.nv_total_stock = self.jne_total_stock = self.sl_total_stock = 0.0
        self.ss_total_stock = self.bnr_total_stock = self.wr_total_stock = self.dfm_total_stock = self.bks_total_stock = 0.0
        self.sale_split_lines = [(6,0,[])]
        result = super(SaleOrderLine, self).product_id_change()
        product_id = self.product_id
        if self.substitute_product_id:
            product_id = self.substitute_product_id
        if product_id:
            vendor_cost = {}
            all_total_stock = 0.0
            result.update({'value': {}})
            incoming_move_ids = self.env["stock.move"].search([('product_id', '=', product_id.id),
                                             ('location_id.usage', 'not in', ('internal', 'transit')),
                                             ('location_dest_id.usage', 'in', ('internal', 'transit')),
                                             ('state', 'not in', ('cancel', 'done'))]).filtered(lambda mo: mo.purchase_line_id)
            if incoming_move_ids:
                inbound_lines = []
                for move in incoming_move_ids:
                    po_line = move.purchase_line_id
                    inbound_lines.append((0, 0,{'purchase_id': po_line.order_id.id or '',
                                               'state': po_line.order_id.state or '',
                                               'qty_ordered': po_line.product_qty or 0.0,
                                               'qty_committed': 0.0,
                                               'qty_received': po_line.qty_received or 0.0,
                                               'date_submitted': po_line.order_id.date_approve or '',
                                               # 'sale_line_id': self.parent_line_id.id,
                                               'po_line_id': po_line.id}))
                self.inbound_stock_lines = inbound_lines
            jmac_stock_ids = self.env["stock.quant"].search([('product_id', '=', product_id.id),
                ('location_id.usage', '=', 'internal'),('quantity','!=',0.0)])
            if jmac_stock_ids:
                self.jmac_onhand = product_id.qty_available
                self.jmac_available = product_id.qty_available
                self.jmac_stock_ids = [(6,0,jmac_stock_ids.ids)]
                all_total_stock += product_id.qty_available
            params = {} # 'order_id': self.order_id
            if self.adi_partner_id:
                price_stock_list = self.vendor_price_stock(self.adi_partner_id,self.product_uom_qty,params,'adi')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])
                all_total_stock += price_stock_list[2]

            if self.nv_partner_id:
                price_stock_list = self.vendor_price_stock(self.nv_partner_id,self.product_uom_qty,params,'nv')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])
                all_total_stock += price_stock_list[2]

            if self.sl_partner_id:
                price_stock_list = self.vendor_price_stock(self.sl_partner_id,self.product_uom_qty,params,'sl')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])
                all_total_stock += price_stock_list[2]

            if self.ss_partner_id:
                price_stock_list = self.vendor_price_stock(self.ss_partner_id,self.product_uom_qty,params,'ss')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])
                all_total_stock += price_stock_list[2]

            if self.jne_partner_id:
                price_stock_list = self.vendor_price_stock(self.jne_partner_id,self.product_uom_qty,params,'jne')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])
                all_total_stock += price_stock_list[2]

            if self.bnr_partner_id:
                price_stock_list = self.vendor_price_stock(self.bnr_partner_id,self.product_uom_qty,params,'bnr')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])
                all_total_stock += price_stock_list[2]

            if self.wr_partner_id:
                price_stock_list = self.vendor_price_stock(self.wr_partner_id,self.product_uom_qty,params,'wr')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])
                all_total_stock += price_stock_list[2]

            if self.dfm_partner_id:
                price_stock_list = self.vendor_price_stock(self.dfm_partner_id,self.product_uom_qty,params,'dfm')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])
                all_total_stock += price_stock_list[2]

            if self.bks_partner_id:
                price_stock_list = self.vendor_price_stock(self.bks_partner_id,self.product_uom_qty,params,'bks')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])
                all_total_stock += price_stock_list[2]

            result['value'].update({'total_stock': all_total_stock})
            if vendor_cost:
                min_cost = min(vendor_cost.keys(), key=(lambda k: vendor_cost[k]))
                result['value'].update({'lowest_cost_source': min_cost.name,
                                        'lowest_cost': vendor_cost.get(min_cost)})
            else:
                result['value'].update({'lowest_cost_source': '',
                                        'lowest_cost': 0.0})
        return result

    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        result = super(SaleOrderLine, self).product_uom_change()
        product_id = self.product_id
        if self.substitute_product_id:
            product_id = self.substitute_product_id
        if product_id:
            vendor_cost = {}
            result = {'value': {}}
            params = {} # 'order_id': self.order_id
            if self.adi_partner_id:
                price_stock_list = self.vendor_price_stock(self.adi_partner_id,self.product_uom_qty,params,'adi')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])

            if self.nv_partner_id:
                price_stock_list = self.vendor_price_stock(self.nv_partner_id,self.product_uom_qty,params,'nv')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])

            if self.sl_partner_id:
                price_stock_list = self.vendor_price_stock(self.sl_partner_id,self.product_uom_qty,params,'sl')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])

            if self.ss_partner_id:
                price_stock_list = self.vendor_price_stock(self.ss_partner_id,self.product_uom_qty,params,'ss')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])

            if self.jne_partner_id:
                price_stock_list = self.vendor_price_stock(self.jne_partner_id,self.product_uom_qty,params,'jne')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])

            if self.bnr_partner_id:
                price_stock_list = self.vendor_price_stock(self.bnr_partner_id,self.product_uom_qty,params,'bnr')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])

            if self.wr_partner_id:
                price_stock_list = self.vendor_price_stock(self.wr_partner_id,self.product_uom_qty,params,'wr')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])

            if self.dfm_partner_id:
                price_stock_list = self.vendor_price_stock(self.dfm_partner_id,self.product_uom_qty,params,'dfm')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])

            if self.bks_partner_id:
                price_stock_list = self.vendor_price_stock(self.bks_partner_id,self.product_uom_qty,params,'bks')
                result['value'].update(price_stock_list[0])
                vendor_cost.update(price_stock_list[1])
            if vendor_cost:
                min_cost = min(vendor_cost.keys(), key=(lambda k: vendor_cost[k]))
                result['value'].update({'lowest_cost_source': min_cost.name,
                                        'lowest_cost': vendor_cost.get(min_cost)})
            else:
                result['value'].update({'lowest_cost_source': '',
                                        'lowest_cost': 0.0})
        return result

    def split_line(self):
        ctx = self._context.copy()
        process_qty = sum(self.sale_split_lines.mapped('product_uom_qty'))
        unprocess_qty = self.product_uom_qty - process_qty
        if not unprocess_qty:
            raise ValidationError(_("There is no quantity for process!"))
        ctx.update({'default_qty': unprocess_qty,
                    'default_remaining_qty': unprocess_qty,
                    'default_sale_line_id': self.id})
        model = 'notification.message'
        view_id = self.env.ref('sale_distributor.notification_message_form_view').id
        name = False
        vendor_price_unit = 0.0
        if ctx.get('vendor') == 'adi':
            name = self.adi_partner_id
            vendor_price_unit = self.adi_actual_cost
        elif ctx.get('vendor') == 'nv':
            name = self.nv_partner_id
            vendor_price_unit = self.nv_actual_cost
        elif ctx.get('vendor') == 'ss':
            name = self.ss_partner_id
            vendor_price_unit = self.ss_actual_cost
        elif ctx.get('vendor') == 'sl':
            name = self.sl_partner_id
            vendor_price_unit = self.sl_actual_cost
        elif ctx.get('vendor') == 'jne':
            name = self.jne_partner_id
            vendor_price_unit = self.jne_actual_cost
        elif ctx.get('vendor') == 'bnr':
            name = self.bnr_partner_id
            vendor_price_unit = self.bnr_actual_cost
        elif ctx.get('vendor') == 'wr':
            name = self.wr_partner_id
            vendor_price_unit = self.wr_actual_cost
        elif ctx.get('vendor') == 'dfm':
            name = self.dfm_partner_id
            vendor_price_unit = self.dfm_actual_cost
        elif ctx.get('vendor') == 'bks':
            name = self.bks_partner_id
            vendor_price_unit = self.bks_actual_cost
        elif ctx.get('vendor') == 'otv':
            name = self.partner_id
            vendor_price_unit = self.otv_cost
        wiz_name = ''
        msg = ''
        product_id = self.product_id
        if self.substitute_product_id:
            product_id = self.substitute_product_id
        if ctx.get('ship_from_here',False):
            wiz_name = 'Ship from here'
            msg = 'Ship %s from here?' % product_id.name
            
        elif ctx.get('add_to_buy',False):
            wiz_name = 'Add to Buy'
            msg = 'Add %s to buy' % product_id.name
        elif ctx.get('dropship',False):
            wiz_name = 'Dropship'
            msg =  'Dropship %s' % product_id.name
        elif ctx.get('allocate',False):
            wiz_name = 'Allocate'
            msg = 'Allocate %s?' % product_id.name
        if name :
            ctx.update({'default_partner_id': name.id})
            wiz_name = name.name + ' ' + wiz_name
        ctx.update({'default_message': msg,'default_unit_price':vendor_price_unit})
        return {
            'name': (wiz_name),
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
        if self.split_line and self.route_id and self.vendor_id:
            values.update({
                'supplier_id': self.vendor_id,
                'vendor_price_unit': self.vendor_price_unit,
                })
        return values


class InboundStock(models.Model):
    _name = "inbound.stock"
    _description = "Inbound Stock"

    sale_line_id = fields.Many2one("sale.order.line", string="Inbound Stock Ref", ondelete='cascade', index=True, copy=True)
    purchase_id = fields.Many2one("purchase.order", string="PO Number")
    po_line_id = fields.Many2one("purchase.order.line", string="PO Line")
    state = fields.Selection([
        ('draft', 'RFQ'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
    ], string='PO Status')
    qty_ordered = fields.Float(string="Qty Ordered", digits='Product Unit of Measure')
    qty_committed = fields.Float(string="Qty Committed", digits='Product Unit of Measure')
    qty_received = fields.Float(string="Qty Received", digits='Product Unit of Measure')
    date_submitted = fields.Datetime(string="Date Submitted")
