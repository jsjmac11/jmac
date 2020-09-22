# -*- coding: utf-8 -*-
#############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
#############################################################################
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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

    so_order_approval = fields.Boolean("Sale Discount Approval",
                                       default=lambda self: self.env.user.company_id.so_double_validation == 'two_step')

    so_double_validation = fields.Selection(related='company_id.so_double_validation',
                                            string="Sale Levels of Approvals *", readonly=False)
    so_double_validation_limit = fields.Float(string="Discount limit requires approval in %",
                                              related='company_id.so_double_validation_limit', readonly=False)

    def set_values(self):
        super(ResDiscountSettings, self).set_values()
        self.so_double_validation = 'two_step' if self.so_order_approval else 'one_step'

    @api.onchange('so_double_validation_limit')
    def onchange_so_double_validation_limit(self):
        """
        Discount % validation.
        :return: raise
        """
        if not (0 <= self.so_double_validation_limit <= 100):
            raise ValidationError(_("Discount Limit is invalid!"))
