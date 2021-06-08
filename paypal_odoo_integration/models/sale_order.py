# coding: utf-8

from odoo import fields, models, api
from .classes import CreditCard, Amount, Profile, Address, ShippingAddress, Tracking, Response, CustomerInfo
from .client import PayflowProClient, find_classes_in_list, find_class_in_list

class SaleOrder(models.Model):
    _inherit = "sale.order"

    paypal_transaction_id = fields.Char(string="Paypal Transaction ID", readonly=True, copy=False)
    pending_capture = fields.Boolean(string="Pending Capture", copy=False)
    is_payment = fields.Boolean(string="Is Payment", copy=False)
    payment_link = fields.Char(string="Payment Link")

    def capture_payment_action(self):
        payment_acquirers_id = self.env['payment.acquirer'].search([('provider', '=', 'paypal_payflow')])
        sale_order_id = self.env['sale.order'].browse(self.id)
        client = PayflowProClient(partner=payment_acquirers_id.payflow_partner_id, vendor=payment_acquirers_id.payflow_vendor_id, 
                             username=payment_acquirers_id.payflow_unm, password=payment_acquirers_id.payflow_pwd)
        extras = {'AUTHORIZATIONID': sale_order_id.paypal_transaction_id,'AMT':sale_order_id.amount_total, 'METHOD':'DoCapture'}
        responses, unconsumed_data = client.capture(sale_order_id.paypal_transaction_id, extras=extras)
        sale_order_id.pending_capture = False;

    # def do_request_call(self):
    #     PARTNER_ID = "PayPal"
    #     VENDOR_ID = "shawaz"
    #     USERNAME = "sjbista"
    #     PASSWORD = "B1st@123"
    #     client = PayflowProClient(partner=PARTNER_ID, vendor=VENDOR_ID, 
    #                          username=USERNAME, password=PASSWORD)
    #     credit_card = CreditCard(acct=123456789, expdate="12/2025")
    #     responses, unconsumed_data = client.sale(credit_card, Amount(amt=5, currency="USD"), extras=[Address(street="2842 Magnolia St.", zip="94608")])
    #     responses, unconsumed_data = client.authorization(credit_card, Amount(amt=5, currency="USD"))
    #     transaction_id = responses[0].pnref

