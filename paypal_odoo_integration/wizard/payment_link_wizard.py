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

    def _generate_link(self):
        for payment_link in self:
            record = self.env[payment_link.res_model].browse(payment_link.res_id)
            link = ('%s/website_payment/pay?reference=%s&amount=%s&currency_id=%s'
                    '&partner_id=%s&access_token=%s') % (
                        record.get_base_url(),
                        urls.url_quote_plus(payment_link.description),
                        payment_link.amount,
                        payment_link.currency_id.id,
                        payment_link.partner_id.id,
                        payment_link.access_token
                    )
            if payment_link.company_id:
                link += '&company_id=%s' % payment_link.company_id.id
            if payment_link.res_model == 'account.move':
                link += '&invoice_id=%s' % payment_link.res_id

            res_id = self._context.get('active_id')
            res_model = self._context.get('active_model')
            record = self.env[res_model].browse(res_id)
            if self._context.get('active_model') == 'sale.order':
                link = record.get_base_url() + record.get_portal_url()
            payment_link.link = link
            
    def send_payment_link(self):
        res_id = self._context.get('active_id')
        res_model = self._context.get('active_model')
        record = self.env[res_model].browse(res_id)
        url = record.get_base_url() + record.get_portal_url()
        record.write({'require_signature': False,
                      'state': 'sent'})
        record.payment_link = url
        ir_model_data = self.env['ir.model.data']
        template = self.env.ref('sale.email_template_edi_sale', False)
        msg_ids = template.send_mail(res_id, force_send=True)
        ctx = dict(self._context)
        ctx.update({'default_template_id': template, })
        mail = self.env['mail.compose.message'].with_context(
                ctx).create({})