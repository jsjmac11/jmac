# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from ..models.classes import CreditCard, Amount, Profile, Address, ShippingAddress, Tracking, Response,  CustomerInfo
from ..models.client import PayflowProClient, find_classes_in_list, find_class_in_list
from odoo.exceptions import Warning

ENCRYPTED_FIELDS = ['account_number', 'month', 'year']

class SaleAdvancePaymentWizard(models.TransientModel):
    _inherit = 'sale.advance.payment.wizard'

    def get_years():
        year_list = []
        for i in range(2020, 2036):
            year_list.append((str(i), str(i)))
        return year_list

    payment_date = fields.Date('Payment Date',
                               default=fields.Date.context_today)
    account_number = fields.Char(string="Card Number", size=16)
    cvv = fields.Char(string="CVV", size=4)
    month = fields.Selection([('01', '01'), ('02', '02'),('03', '03'), ('04', '04'),
                          ('05', '05'), ('06', '06'), ('07', '07'), ('08', '08'), 
                          ('09', '09'), ('10', '10'), ('11', '11'), ('12', '12')], string='Month')
    year = fields.Selection(get_years(), string='Year')
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    zip = fields.Char(string='Zip')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    country_id = fields.Many2one('res.country', string='Country')
    is_payal_payment = fields.Boolean(string="Is Paypal Payment", copy=False, default=False)

    @api.onchange('journal_id')
    def onchange_journal_id(self):
        if self.journal_id.is_paypal_payflow:
            self.is_payal_payment = True
        else:
            self.is_payal_payment = False
    @api.model
    def default_get(self, fields):
        res = super(SaleAdvancePaymentWizard, self).default_get(fields)
        sale_order_id = self._context.get('active_ids', [])[0]
        order = self.env[self._context.get('active_model')].browse(sale_order_id)
        res['total_amount'] = order.amount_total
        res['street'] = order.partner_id.street
        res['street2'] = order.partner_id.street2
        res['city'] = order.partner_id.city
        res['state_id'] = order.partner_id.state_id.id
        res['zip'] = order.partner_id.zip
        res['country_id'] = order.partner_id.country_id.id
        return res

    def authorized_with_capture(self):
        active_model = 'sale.advance.payment.wizard'
        payment_acquirers_id = self.env['payment.acquirer'].search([('provider', '=', 'paypal_payflow')])
        act_model = self.env.context.get('active_model', False)
        active_id = self.env.context.get('active_id', False)
        sale_obj = self.env[act_model]
        sale_order_id = sale_obj.browse(active_id)
        year = self.year
        exp_date = self.month + year[-2:]
        if self.street2:
            street = self.street + ', ' + self.street2
        else:
            street = self.street
        client = PayflowProClient(partner=payment_acquirers_id.payflow_partner_id, vendor=payment_acquirers_id.payflow_vendor_id, 
                             username=payment_acquirers_id.payflow_unm, password=payment_acquirers_id.payflow_pwd)
        credit_card = CreditCard(acct=self.account_number, expdate=exp_date, cvv2=self.cvv)
        responses, unconsumed_data = client.sale(credit_card, Amount(amt=self.total_amount, currency=self.currency_id.id), 
            extras=[Address(street=street, city=self.city, state=self.state_id.name, zip=self.zip, country=self.country_id.name)])
        responses, unconsumed_data = client.authorization(credit_card, Amount(amt=self.total_amount, currency=self.currency_id.id))
        transaction_id = responses[0].pnref
        sale_order_id.paypal_transaction_id = transaction_id
        responses, unconsumed_data = client.capture(transaction_id)
        payment_obj = self.env['account.payment'].sudo()
        payment_method_id = self.env[
                        'account.payment.method'].search(
                        [('name', '=', 'Manual'),
                        ('payment_type', '=', 'inbound')])
        vals = {
            'partner_type' : 'customer',
            'partner_id': sale_order_id.partner_id.id,
            'amount' : self.total_amount,
            'payment_date': self.payment_date,
            'payment_type': 'inbound',
            'journal_id': payment_acquirers_id.journal_id.id,
            'payment_method_id': payment_method_id.id,
            'sale_order_id' : sale_order_id.id,
            }
        payment = payment_obj.create(vals)
        payment.post()
        sale_order_id.write({'state': 'draft'})
        moves_id = sale_order_id._create_invoices(final=True)
        moves_id.action_post()
        for invoice in moves_id.filtered(lambda move: move.is_invoice()):
            move_lines = payment.mapped('move_line_ids').filtered(lambda line: not line.reconciled and line.credit > 0.0)
            for line in move_lines:
                invoice.js_assign_outstanding_line(line.id)


    def authorized_only(self):
        active_model = 'sale.advance.payment.wizard'
        payment_acquirers_id = self.env['payment.acquirer'].search([('provider', '=', 'paypal_payflow')])
        act_model = self.env.context.get('active_model', False)
        active_id = self.env.context.get('active_id', False)
        sale_obj = self.env[act_model]
        sale_order_id = sale_obj.browse(active_id)
        year = self.year
        exp_date = self.month + year[-2:]
        client = PayflowProClient(partner=payment_acquirers_id.payflow_partner_id, vendor=payment_acquirers_id.payflow_vendor_id, 
                             username=payment_acquirers_id.payflow_unm, password=payment_acquirers_id.payflow_pwd)
        credit_card = CreditCard(acct=self.account_number, expdate=exp_date, cvv2=self.cvv)
        responses, unconsumed_data = client.authorization(credit_card, Amount(amt=self.total_amount, currency=self.currency_id.id))
        transaction_id = responses[0].pnref
        sale_order_id.paypal_transaction_id = transaction_id
        sale_order_id.pending_capture = True
        # responses, unconsumed_data = client.capture(sale_order_id.paypal_transaction_id)
        payment_obj = self.env['account.payment'].sudo()
        payment_method_id = self.env[
                        'account.payment.method'].search(
                        [('name', '=', 'Manual'),
                        ('payment_type', '=', 'inbound')])
        vals = {
            'partner_type' : 'customer',
            'partner_id': sale_order_id.partner_id.id,
            'amount' : self.total_amount,
            'payment_date': self.payment_date,
            'payment_type': 'inbound',
            'journal_id': payment_acquirers_id.journal_id.id,
            'payment_method_id': payment_method_id.id,
            'sale_order_id' : sale_order_id.id,
            }
        payment = payment_obj.create(vals)
        payment.post()
        sale_order_id.write({'state': 'draft'})
        moves_id = sale_order_id._create_invoices(final=True)
        moves_id.action_post()
        moves_id.pending_capture = True

    @api.model
    def create(self, values):
        if values.get('account_number', False) and len(values['account_number']) > 16:
            raise Warning(_("Please enter valid credit card number!."))
        if values.get('cvv', False) and len(values['cvv']) > 4:
            raise Warning(_("Please enter valid cvv number!."))
        result = super(SaleAdvancePaymentWizard, self).create(values)
        return result
