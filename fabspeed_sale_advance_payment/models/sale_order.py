# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    payment_line = fields.One2many("account.payment",
                                 'sale_order_id', "Advance Payment")
    advance_payment_done=fields.Boolean("Advance Payment Done",copy=False,default=False)
    
    advance_total = fields.Monetary(string='Advance Total', store=True, readonly=True, compute='_advance_all')
    
    to_invoice_amount = fields.Monetary(string='invoice amount Total', store=True, readonly=True, compute='_to_invoice_amt')

    @api.depends('order_line.qty_to_invoice')
    def _to_invoice_amt(self):
        """
        Compute the total amounts of To Invoice amount.
        """
        for order in self:
            to_invoice_amount = 0.0
            for line in order.order_line:
                to_invoice_amount += line.qty_to_invoice * line.price_unit
            order.update({
                'to_invoice_amount': to_invoice_amount,
            })

    @api.depends('payment_line.amount')
    def _advance_all(self):
        """
        Compute the total amounts of the Advance Payment.
        """
        for order in self:
            amount = 0.0
            for line in order.payment_line:
                amount += line.amount
            order.update({
                'advance_total': amount,
            })
    
    
    def sale_open_advance_payment_wizard(self):
        ctx = {
            'default_model': 'sale.order',
            'default_res_id': self.ids[0],
            'default_sale_order': self.id,
            
        }
        return {
            'name': "Advance Payment",
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'sale.advance.payment.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': ctx,

        }



class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"
    
    @api.model
    def to_invoice_amount(self):
        if self._context.get('active_model') == 'sale.order' and self._context.get('active_id', False):
            sale_order = self.env['sale.order'].browse(self._context.get('active_id'))
            return sale_order.to_invoice_amount
        
    @api.model
    def advance_total(self):
        if self._context.get('active_model') == 'sale.order' and self._context.get('active_id', False):
            sale_order = self.env['sale.order'].browse(self._context.get('active_id'))
            return sale_order.advance_total
    
    to_invoice_amount = fields.Monetary(string='invoice amount Total', default=to_invoice_amount)
    advance_total = fields.Monetary(string='Advance Total', default=advance_total, readonly=True)
    display_msg = fields.Boolean("Display MSG", copy=False,
                                          default=False, compute='check_amount')

    @api.depends('to_invoice_amount', 'advance_total')
    def check_amount(self):
        for rec in self:
            if rec.to_invoice_amount > rec.advance_total:
                rec.display_msg = True
            else:
                rec.display_msg = False
