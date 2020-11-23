# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

from collections import defaultdict

class account_payment(models.Model):
    _inherit = "account.payment"
    _description = "Payments"
    
    sale_order_id=fields.Many2one("sale.order","Sale Order")
