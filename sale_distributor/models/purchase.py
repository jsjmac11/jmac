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


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    line_split = fields.Boolean('Split')
    parent_line_id = fields.Many2one('purchase.order.line', string="Parent Line")
    split_line_ids = fields.One2many('purchase.order.line', 'parent_line_id', string='Allocated Lines', domain=[('line_split','=',True)], states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=False)
    sequence_ref = fields.Char('No.')

    @api.model
    def create(self, vals):
        res = super(PurchaseOrderLine, self).create(vals)
        res.order_id._genrate_line_sequence()     
        return res

    # def write(self, values):
    #     res = super(PurchaseOrderLine, self).write(values)
    #     for line in self:
    #         line.order_id._genrate_line_sequence()
    #     return res

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    order_line = fields.One2many('purchase.order.line', 'order_id', string='Order Lines', domain=[('line_split','=',False)], states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True)
    split_line = fields.One2many('purchase.order.line', 'order_id', string='Allocated Lines', domain=[('line_split','=',True)], states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=False)
    
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
                # We keep a limited scope on purpose. Ideally, we should also use move_orig_ids and
                # do some recursive search, but that could be prohibitive if not done correctly.
                moves = line.move_ids | line.move_ids.mapped('returned_move_ids')
                pickings |= moves.mapped('picking_id')
            for sline in order.split_line:
                # We keep a limited scope on purpose. Ideally, we should also use move_orig_ids and
                # do some recursive search, but that could be prohibitive if not done correctly.
                moves = sline.move_ids | sline.move_ids.mapped('returned_move_ids')
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
                count +=1
            no += 1
        return True

    def write(self, values):
        res = super(PurchaseOrder, self).write(values)
        if values.get('order_line'):
            self._genrate_line_sequence()
        return res

    def _create_picking(self):
        StockPicking = self.env['stock.picking']
        for order in self:
            if any([ptype in ['product', 'consu'] for ptype in order.order_line.mapped('product_id.type')]):
                pickings = order.picking_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
                if not pickings:
                    res = order._prepare_picking()
                    picking = StockPicking.create(res)
                else:
                    picking = pickings[0]
                # If split line found then create receipt for that line else order line.
                if order.split_line:
                    moves = order.split_line._create_stock_moves(picking)
                else:
                    moves = order.order_line._create_stock_moves(picking)
                moves = moves.filtered(lambda x: x.state not in ('done', 'cancel'))._action_confirm()
                seq = 0
                for move in sorted(moves, key=lambda move: move.date_expected):
                    seq += 5
                    move.sequence = seq
                moves._action_assign()
                picking.message_post_with_view('mail.message_origin_link',
                    values={'self': picking, 'origin': order},
                    subtype_id=self.env.ref('mail.mt_note').id)
        return True