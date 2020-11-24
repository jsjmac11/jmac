# -*- encoding: utf-8 -*-
#
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (http://www.bistasolutions.com)
#
#

from odoo import models, fields, api, _
from odoo.exceptions import Warning


class SaleAdvancePaymentWizard(models.TransientModel):
    _name = 'sale.advance.payment.wizard'
    _description = "Advance Payment"
    
    payment_date = fields.Date('Payment Date',
                               default=fields.Date.context_today)
    total_amount = fields.Float('Total Amount')
    advance_amount = fields.Float('Advance Amount')
    advance_percent = fields.Float('Advance Percent (%)')
    journal_id = fields.Many2one('account.journal', 'Journal')
    ref = fields.Char('Ref')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id",
                                  string="Currency", readonly=True)
    payment_term_id = fields.Many2one('account.payment.term', 'Payment Term')
    
    @api.model
    def default_get(self, fields):
        res = super(SaleAdvancePaymentWizard, self).default_get(fields)
        so_id = self._context.get('active_ids', [])[0]
        so = self.env[self._context.get(
            'active_model')].browse(so_id)
        res['ref'] = so.name
        journal_obj = self.env['account.journal']
        journal = journal_obj.search([('type', 'in', ['bank','cash']),
                                      ('code', 'in', ['CSH1','BNK1'])], limit=1)
        
        account_payment_term_line_obj = self.env["account.payment.term.line"].search([('payment_id','=',so.payment_term_id.id),('value','=','percent')],limit=1)
        advance_amount = (so.amount_total * account_payment_term_line_obj.value_amount) / 100
        adv_percent = account_payment_term_line_obj.value_amount
        if not advance_amount:
            advance_amount = so.amount_total
            adv_percent = 100
        res['journal_id'] = journal.id if journal else False
        res['payment_term_id'] = so.payment_term_id.id if so.payment_term_id else False
        res['total_amount'] = so.amount_total
        res['advance_percent'] = adv_percent
        res['advance_amount'] = advance_amount
        return res
    
    @api.onchange('advance_percent')
    def onchange_advance_percent(self):
        if self.total_amount > 0:
            self.advance_amount = (float(self.advance_percent) * float(self.total_amount)) / 100.0
     
    @api.onchange('advance_amount')
    def onchange_advance_amount(self):
        if self.total_amount > 0:
            self.advance_percent = (float(self.advance_amount) / float(self.total_amount)) * 100.0

    
    def action_create_payment(self):
        payment_obj = self.env['account.payment'].sudo()
        type = 'inbound'
        payment_method_id = self.env[
                        'account.payment.method'].search(
                        [('name', '=', 'Manual'),
                         ('payment_type', '=', 'inbound')])
        so_id = self._context.get('active_ids', [])[0]
        so = self.env[self._context.get(
            'active_model')].browse(so_id)
        vals = {
            'partner_type' : 'customer',
            'partner_id': so.partner_id.id,
            'amount' : self.advance_amount,
            'payment_date': self.payment_date,
            'payment_type': 'inbound',
            'journal_id': self.journal_id.id,
            'payment_method_id': payment_method_id.id,
            'sale_order_id' : so.id,
            }
        payment=payment_obj.create(vals)
        payment.post()
        so.advance_payment_done=True
        moves_id = so._create_invoices(final=True)
        moves_id.action_post()
        # moves_id.update({'transaction_ids':[(6,0,[payment.id])]})
        for invoice in moves_id.filtered(lambda move: move.is_invoice()):
            move_lines = payment.mapped('move_line_ids').filtered(lambda line: not line.reconciled and line.credit > 0.0)
            for line in move_lines:
                invoice.js_assign_outstanding_line(line.id)
        
