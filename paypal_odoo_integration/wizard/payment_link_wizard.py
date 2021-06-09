# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import hashlib
import hmac

from werkzeug import urls

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import ustr, consteq, float_compare


class PaymentLinkWizard(models.TransientModel):
    _inherit = "payment.link.wizard"

    def send_payment_link(self):
        res_id = self._context.get('active_id')
        res_model = self._context.get('active_model')
        record = self.env[res_model].browse(res_id)
        record.payment_link = self.link
        ir_model_data = self.env['ir.model.data']
        template = self.env.ref('sale.email_template_edi_sale', False)
        msg_ids = template.send_mail(res_id, force_send=True)
        ctx = dict(self._context)
        ctx.update({'default_template_id': template, })
        mail = self.env['mail.compose.message'].with_context(
                ctx).create({})