# coding: utf-8

from odoo import fields, models, api
from .classes import CreditCard, Amount, Profile, Address, ShippingAddress, Tracking, Response, CustomerInfo
from .client import PayflowProClient, find_classes_in_list, find_class_in_list

class AccountMove(models.Model):
    _inherit = "account.move"

    pending_capture = fields.Boolean(string="Pending Capture", copy=False)

    def capture_payment_action(self):
        sale_order_id = self.env['sale.order'].search([('name', '=', self.invoice_origin)])
        self.pending_capture = False
        if sale_order_id:
            sale_order_id.write({'pending_capture': False})
            sale_order_id.capture_payment_action()
            
        for invoice in self.filtered(lambda move: move.is_invoice()):
            payment = self.env['account.payment'].search([('sale_order_id', '=', sale_order_id.id)])
            move_lines = payment.mapped('move_line_ids').filtered(lambda line: not line.reconciled and line.credit > 0.0)
            for line in move_lines:
                invoice.js_assign_outstanding_line(line.id)

class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_paypal_payflow = fields.Boolean(string="Is Paypal Payflow", copy=False)
