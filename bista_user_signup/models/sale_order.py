# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import fields, models, api, _
from odoo.exceptions import AccessError, UserError, ValidationError

class SaleOrder(models.Model):
    """Inherit Sale order for Customization."""

    _inherit = 'sale.order'

    @api.model
    def create(self, vals):
        res = super(SaleOrder, self).create(vals)
        template = self.env.ref('bista_user_signup.email_template_signup_created')
        partner_ids = res.partner_id.ids
        partner_ids = ','.join(map(str, partner_ids))
        current_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        if res.partner_id.user_ids:
            link = current_url + '/my/home'
        else:
            link = current_url + '/web/signup'
        template.with_context({'partner_ids': partner_ids, 'link': link}).send_mail(res.id, force_send=True)
        return res
