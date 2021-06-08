# coding: utf-8

from odoo import api, fields, models, _

class AcquirerPaypal(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('paypal_payflow', 'Paypal Payflow')])
    payflow_partner_id = fields.Char('Payflow Partner ID')
    payflow_vendor_id = fields.Char('Payflow Vendor ID')
    payflow_unm = fields.Char('Username')
    payflow_pwd = fields.Char('Password')
