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

class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_paypal_payflow = fields.Boolean(string="Is Paypal Payflow", copy=False)
