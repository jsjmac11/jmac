# -*- coding: utf-8 -*-
#############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
#############################################################################
from odoo import api, fields, models


class sale_discount(models.Model):
    _inherit = 'sale.order'

    state = fields.Selection(selection_add=[('waiting', 'Waiting Approval'),('approved', 'Quotation Approved')],
        string='Status', readonly=True, copy=False, index=True, 
        track_visibility='onchange', default='draft')
    is_approved = fields.Boolean('Approved', copy=False, help="Indicate manager approved the order.")


    def action_confirm(self):
        discnt = 0.0
        no_line = 0.0
        if not self.is_approved and self.company_id.so_double_validation == 'two_step':
            discnt = self.discount_rate
            if self.company_id.so_double_validation_limit and discnt > self.company_id.so_double_validation_limit:
                self.state = 'waiting'
                return True
        super(sale_discount, self).action_confirm()


    def action_approve(self):
        self.update({'is_approved': True, 'state': 'draft'})
        return True



class Company(models.Model):
    _inherit = 'res.company'

    so_double_validation = fields.Selection([
        ('one_step', 'Confirm sale orders in one step'),
        ('two_step', 'Get 2 levels of approvals to confirm a sale order')
    ], string="Sale Levels of Approvals", default='one_step',
        help="Provide a double validation mechanism for sales discount")

    so_double_validation_limit = fields.Float(string="Percentage of Discount that requires double validation'",
                                  help="Minimum discount percentage for which a double validation is required")


class ResDiscountSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    so_order_approval = fields.Boolean("Sale Discount Approval", default=lambda self: self.env.user.company_id.so_double_validation == 'two_step')

    so_double_validation = fields.Selection(related='company_id.so_double_validation',string="Sale Levels of Approvals *", readonly=False)
    so_double_validation_limit = fields.Float(string="Discount limit requires approval in %",
                                              related='company_id.so_double_validation_limit', readonly=False)

    def set_values(self):
        super(ResDiscountSettings, self).set_values()
        self.so_double_validation = 'two_step' if self.so_order_approval else 'one_step'
