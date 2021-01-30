# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
# from datetime import datetime
import string


class PurchaseOrderLine(models.Model):
    """Update split line for SO process Qty."""

    _inherit = 'purchase.order.line'
    _order = 'order_id, sequence_ref, id'

    line_split = fields.Boolean('Split', default=False)
    parent_line_id = fields.Many2one('purchase.order.line',
                                     string="Parent Line")
    split_line_ids = fields.One2many('purchase.order.line', 'parent_line_id',
                                     string='Allocated Lines',
                                     domain=[('line_split', '=', True)],
                                     states={'cancel': [('readonly', True)],
                                             'done': [('readonly', True)]},
                                     copy=False)
    sequence_ref = fields.Char('No.')
    item_note = fields.Text(string="Item Note")
    allocated_qty = fields.Float(string='Allocated Quantity',
                                 compute='_compute_allocated_qty')
    invetory_qty = fields.Float(string='Invetory Quantity',
                                compute='_compute_allocated_qty')
    active = fields.Boolean("Active", default=True)

    @api.depends('qty_received_method', 'qty_received_manual')
    def _compute_qty_received(self):
        super(PurchaseOrderLine, self)._compute_qty_received()
        for line in self:
            if line.parent_line_id:
                qty_received = sum(line.parent_line_id.split_line_ids.mapped('qty_received'))
                line.parent_line_id.qty_received = qty_received
            

    @api.depends('order_id.split_line', 'product_qty', 'order_id.order_line')
    def _compute_allocated_qty(self):
        for record in self:
            allocate_qty = 0.0
            product_qty = record.product_qty
            for line in record.order_id.split_line:
                if line.sale_line_id and line.product_id.id == record.product_id.id:
                    allocate_qty += line.product_qty
            record.allocated_qty = allocate_qty or 0.0
            record.invetory_qty = product_qty - allocate_qty or 0.0

    @api.model
    def create(self, vals):
        """Generate purchase order line sequence."""
        res = super(PurchaseOrderLine, self).create(vals)
        res.order_id._genrate_line_sequence()

        return res

    # def write(self, values):
    #     res = super(PurchaseOrderLine, self).write(values)
    #     for line in self:
    #         line.order_id._genrate_line_sequence()
    #     return res

    def action_cancel_pol(self):
        """Remove purchase order line and corresponding sale line."""
        if self.sale_line_id:
            st_move_ids = self.env['stock.move'].search(
                [('sale_line_id', '=', self.sale_line_id.id)])
            st_move_ids._action_cancel()
            self.sale_line_id.write({'active': False})

        po_st_move_ids = self.env['stock.move'].search(
            [('purchase_line_id', '=', self.id)])
        po_st_move_ids._action_cancel()
        pl = self.order_id.split_line.filtered(lambda l: l.id != self.id)
        order_id = False
        if not pl:
            order_id = self.order_id
        if self.parent_line_id.product_qty == self.product_qty:
            if self.order_id.state not in ('purchase', 'done'):
                if not order_id:
                    self.parent_line_id.unlink()
                self.unlink()
            else:
                if not order_id:
                    self.parent_line_id.active = False
                self.active = False
        else:
            self.parent_line_id.product_qty = self.parent_line_id.product_qty - self.product_qty
            if self.order_id.state not in ('purchase', 'done'):
                self.unlink()
            else:
                self.active = False
        if order_id:
            order_id.button_cancel()
        return True

    def change_sol_qty(self):
        """Re-allocate purchase quantity to sale line."""
        ctx = self._context.copy()
        # po_so_line = {'qty': self.product_qty}
        # if self.sale_line_id:
        #     po_so_line.update({'sale_line_id': self.sale_line_id.id,
        #                        'sale_id': self.sale_line_id.order_id.id,
        #                        'name': self.id})
        ctx.update({'default_purchase_line_id': self.id,
                    'default_purchase_id': self.order_id.id,
                    'default_remaining_qty': self.product_qty,
                    'default_qty': self.product_qty,
                    'default_sale_line_id': self.sale_line_id.id,
                    # 'default_po_so_line': [(0, 0, po_so_line)]
                    })
        model = 'notification.message'
        view_id = self.env.ref(
            'sale_distributor.notification_message_form_view_pol_cancel').id
        wiz_name = ''
        # if ctx.get('purchase', False):
        msg = 'Please Re-allocate sale order!'
        wiz_name = "Allocate"
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


class PurchaseOrder(models.Model):
    """Update customization fileds for process line."""

    _inherit = 'purchase.order'

    order_line = fields.One2many('purchase.order.line', 'order_id',
                                 string='Order Lines',
                                 domain=[('line_split', '=', False)],
                                 states={'cancel': [('readonly', True)],
                                         'done': [('readonly', True)]},
                                 copy=True)
    split_line = fields.One2many('purchase.order.line', 'order_id',
                                 string='Allocated Lines',
                                 domain=[('line_split', '=', True)],
                                 states={'cancel': [('readonly', True)],
                                         'done': [('readonly', True)]},
                                 copy=False)
    add_to_buy = fields.Boolean(string="Add To Buy", default=False, copy=False,
                                states={'cancel': [('readonly', True)],
                                        'purchase': [('readonly', True)],
                                        'done': [('readonly', True)]})

    @api.constrains('add_to_buy')
    def _create_paurchase_order(self):
        if len(self.search([('partner_id', '=', self.partner_id.id),
                            ('add_to_buy', '=', True),
                            ('state', 'in', ('draft', 'sent'))])) > 1:
            raise ValidationError(_("Add to buy Purchase Order Already exist \
                                For %s Vendor ...!" % self.partner_id.name))

    @api.depends('order_line.move_ids.returned_move_ids',
                 'order_line.move_ids.state',
                 'order_line.move_ids.picking_id',
                 'split_line.move_ids.returned_move_ids',
                 'split_line.move_ids.state',
                 'split_line.move_ids.picking_id')
    def _compute_picking(self):
        for order in self:
            pickings = self.env['stock.picking']
            for line in order.order_line:
                # We keep a limited scope on purpose. Ideally, we should also
                # use move_orig_ids and do some recursive search,
                # but that could be prohibitive if not done correctly.
                moves = line.move_ids | line.move_ids.mapped(
                    'returned_move_ids')
                pickings |= moves.mapped('picking_id')
            for sline in order.split_line:
                # We keep a limited scope on purpose. Ideally, we should also
                # use move_orig_ids and do some recursive search,
                # but that could be prohibitive if not done correctly.
                moves = sline.move_ids | sline.move_ids.mapped(
                    'returned_move_ids')
                pickings |= moves.mapped('picking_id')
            order.picking_ids = pickings
            order.picking_count = len(pickings)

    def _genrate_line_sequence(self):
        no = 1
        for l in self.order_line:
            l.sequence_ref = no
            count = 0
            for sl in l.split_line_ids:
                res = string.ascii_uppercase[count]
                sl.sequence_ref = str(no) + res
                count += 1
            no += 1
        return True

    def create_split_line(self):
        for pline in self.order_line:
            p_qty = pline.product_qty
            c_qty = sum(pline.split_line_ids.mapped('product_qty'))
            if p_qty != c_qty:
                cline = pline.split_line_ids.filtered(lambda l: not l.sale_line_id)
                if cline:
                    cline.product_qty += p_qty - c_qty
                else:
                    pline.copy({'product_qty': p_qty - c_qty,
                                'line_split': True,
                                'parent_line_id': pline.id})
        return True

    @api.model
    def create(self, vals):
        """Generate purchase order line sequence."""
        res = super(PurchaseOrder, self).create(vals)
        if vals.get('order_line'):
            res.create_split_line()
        return res

    def write(self, values):
        """Generate sequence."""
        res = super(PurchaseOrder, self).write(values)
        if values.get('order_line'):
            self._genrate_line_sequence()
            self.create_split_line()
        return res

    # def write(self, vals):
    #     res = super(PurchaseOrder, self).write(vals)
    #     if vals.get('order_line') and self.state == 'purchase':
    #         for order in self:
    #             to_log = {}
    #             for order_line in order.split_line:
    #                 if pre_order_line_qty.get(order_line, False) and float_compare(pre_order_line_qty[order_line], order_line.product_qty, precision_rounding=order_line.product_uom.rounding) > 0:
    #                     to_log[order_line] = (order_line.product_qty, pre_order_line_qty[order_line])
    #             if to_log:
    #                 order._log_decrease_ordered_quantity(to_log)
    #     return res

    def _create_picking(self):
        stockpicking = self.env['stock.picking']
        for order in self:
            if any([ptype in ['product', 'consu'] for ptype in
                    order.order_line.mapped('product_id.type')]):
                pickings = order.picking_ids.filtered(lambda x: x.state not in
                                                      ('done', 'cancel'))
                if not pickings:
                    res = order._prepare_picking()
                    picking = stockpicking.create(res)
                else:
                    picking = pickings[0]
                # If split line found then create receipt for that line
                # else order line.
                # if order.split_line:
                moves = order.split_line._create_stock_moves(picking)
                # else:
                #     moves = order.order_line._create_stock_moves(picking)
                moves = moves.filtered(lambda x: x.state not in
                                       ('done', 'cancel'))._action_confirm()
                seq = 0
                for move in sorted(moves, key=lambda move: move.date_expected):
                    seq += 5
                    move.sequence = seq
                moves._action_assign()
                picking.message_post_with_view(
                    'mail.message_origin_link',
                    values={'self': picking,
                            'origin': order},
                    subtype_id=self.env.ref('mail.mt_note').id)
        return True

    def _activity_cancel_on_sale(self):
        """Update SO with activity perform in PO.

        If some PO are cancelled, we need to put an activity on their
        origin SO (only the open ones). Since a PO can have
        been modified by several SO, when cancelling one PO,
        many next activities can be schedulded on different SO.
        """
        # super(PurchaseOrder, self)._activity_cancel_on_sale()
        sol_ids = self.env["sale.order.line"]
        # map SO -> recordset of PO as {sale.order: set(purchase.order.line)}
        sale_to_notify_map = {}
        for order in self:
            for purchase_line in order.split_line:
                if purchase_line.sale_line_id:
                    sale_order = purchase_line.sale_line_id.order_id
                    sol_ids |= purchase_line.sale_line_id
                    sale_to_notify_map.setdefault(
                        sale_order, self.env['purchase.order.line'])
                    sale_to_notify_map[sale_order] |= purchase_line
        for sale_order, purchase_order_lines in sale_to_notify_map.items():
            sale_order.activity_schedule_with_view(
                'mail.mail_activity_data_warning',
                user_id=sale_order.user_id.id or self.env.uid,
                views_or_xmlid='sale_purchase.\
                exception_sale_on_purchase_cancellation',
                render_context={
                    'purchase_orders': purchase_order_lines.mapped('order_id'),
                    'purchase_lines': purchase_order_lines})
        for order in self:
            for purchase_line in order.split_line:
                purchase_line.action_cancel_pol()
        # move_ids = self.env['stock.move'].search(
        #     [('sale_line_id', 'in', sol_ids.ids)])
        # move_ids._action_cancel()
        # sol_ids.write({'po_cancel_note': '', 'active': False})
