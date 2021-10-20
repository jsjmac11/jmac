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
            invetory_qty = 0.0
            product_qty = record.product_qty
            for line in record.order_id.split_line:
                if line.sale_line_id and line.product_id.id == record.product_id.id:
                    allocate_qty += line.product_qty
                if not line.sale_line_id and line.product_id.id == record.product_id.id:
                    invetory_qty += line.product_qty
            record.allocated_qty = allocate_qty or 0.0
            if record.order_id.state != 'cancel':
                record.invetory_qty = invetory_qty or 0.0
            else:
                record.invetory_qty = 0.0

    def _create_or_update_picking(self):
        for line in self:
            if not line.parent_line_id:
                return False
        super(PurchaseOrderLine, self)._create_or_update_picking()

    @api.model
    def create(self, vals):
        """Generate purchase order line sequence."""
        res = super(PurchaseOrderLine, self).create(vals)
        res.order_id._genrate_line_sequence()
        return res

    def write(self, values):
        res = super(PurchaseOrderLine, self).write(values)
        sol_list = []
        line = self.mapped('order_id').mapped('split_line')
        so_name = line.mapped('sale_line_id').mapped('order_id').mapped('name')
        po_name = ", ".join(so_name)
        self.order_id.origin = po_name
        return res

    def unlink(self):
        if not self.env.context.get("purchase_split_line"):
            for line in self:
                if not line.line_split:
                    split_line = line.order_id.split_line.filtered(
                                lambda l: l.product_id == line.product_id)
                    self += split_line
        return super(PurchaseOrderLine, self).unlink()

    def action_cancel_pol(self):
        """Remove purchase order line and corresponding sale line."""
        for line in self:
            if line.sale_line_id:
                if line.order_id.state in ('purchase'):
                    inv_line = line.order_id.split_line.filtered(
                        lambda l: l.product_id == line.product_id and not l.sale_line_id)
                    if inv_line: # and self.purchase_line_id.state in ('draft', 'sent')
                        update_inv_qty = inv_line.product_qty + line.product_qty
                        inv_line.product_qty = update_inv_qty
                        if line.state == 'purchase':
                            inv_st_move_id = inv_line.move_ids.filtered(lambda l: l.picking_id.state not in ('done','cancel') and l.picking_type_id.code == 'incoming')
                            inv_st_move_id.product_uom_qty = update_inv_qty
                    else:
                        line.copy({'product_qty': line.product_qty,
                                                'sale_line_id': False,
                                                'line_split': True})
                    # self.parent_line_id.product_qty += self.product_qty
                st_move_ids = self.env['stock.move'].search(
                    [('sale_line_id', '=', line.sale_line_id.id)])
                st_move_ids._action_cancel()
                line.sale_line_id.write({'active': False})

            po_st_move_ids = self.env['stock.move'].search(
                [('purchase_line_id', '=', line.id)])
            po_st_move_ids._action_cancel()
            po_st_move_ids.unlink()
            pl = line.order_id.split_line.filtered(lambda l: l.id != line.id)
            order_id = False
            if not pl:
                order_id = line.order_id
            if line.parent_line_id.product_qty == line.product_qty:
                if line.order_id.state not in ('purchase', 'done'):
                    if not self.env.context.get('po_cancel'):
                        line.parent_line_id.unlink()
                    line.unlink()
                else:
                    if not self.env.context.get('po_cancel'):
                        line.parent_line_id.active = False
                    line.active = False
            else:
                if not (line.state in ('purchase', 'done') and line.sale_line_id):
                    line.parent_line_id.product_qty = line.parent_line_id.product_qty - line.product_qty
                if line.order_id.state not in ('purchase', 'done'):
                    line.unlink()
                else:
                    line.active = False
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
                    'default_product_id':self.product_id.id,
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

    def _find_candidate(self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values):
        # if this is defined, this is a dropshipping line, so no
        # this is to correctly map delivered quantities to the so lines
        if self.env.context.get('add_to_buy') or self.env.context.get('add_to_buy_merge_po'):
            lines = self
            return lines and lines[0] or self.env['purchase.order.line']
        else:
            lines = self.filtered(lambda l: l.propagate_date == values['propagate_date'] and l.propagate_date_minimum_delta == values['propagate_date_minimum_delta'] and l.propagate_cancel == values['propagate_cancel'])
            return lines and lines[0] or self.env['purchase.order.line']
        return super(PurchaseOrderLine, lines)._find_candidate(product_id, product_qty, product_uom, location_id, name, origin, company_id, values)

    def show_so(self):
        form_view_id = self.env.ref('sale.view_order_form').id
        
        return {
            'name': ('Sale Order'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.order',
            'view_id': form_view_id,
            'type': 'ir.actions.act_window',
            'res_id': self.sale_line_id and self.sale_line_id.order_id.id
        }
        
class PurchaseOrder(models.Model):
    """Update customization fileds for process line."""

    _inherit = 'purchase.order'

    @api.depends('order_line')
    def _compute_item_note_line(self):
        for line in self.order_line.filtered(lambda l: l.display_type == 'line_note'):
            if line:
                self.is_note_line = True

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
    shipping_method = fields.Text(string="Shipping Method", copy=False)
    is_note_line = fields.Boolean(string="Is Item Note", compute='_compute_item_note_line', store=True)

    @api.constrains('add_to_buy')
    def _create_paurchase_order(self):
        if len(self.search([('partner_id', '=', self.partner_id.id),
                            ('add_to_buy', '=', True),
                            ('state', 'in', ('draft', 'sent'))])) > 1:
            raise ValidationError(_("Add to buy Purchase Order Already exist For %s Vendor ...!" % self.partner_id.name))

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
                                'parent_line_id': pline.id,
                                'sale_line_id': False})
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

    def button_draft(self):
        res = super(PurchaseOrder, self).button_draft()
        if self.order_line:
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
            order.split_line.with_context(po_cancel=True).action_cancel_pol()
        # move_ids = self.env['stock.move'].search(
        #     [('sale_line_id', 'in', sol_ids.ids)])
        # move_ids._action_cancel()
        # sol_ids.write({'po_cancel_note': '', 'active': False})
