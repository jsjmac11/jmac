# -*- coding: utf-8 -*-
# @author Chintan Ambaliya <chintan.ambaliya@bistasolutions.com>

import logging
import pprint
import werkzeug
from unicodedata import normalize

from odoo import http
from odoo.http import request
from odoo.osv import expression
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.addons.payment.controllers.portal import PaymentProcessing, WebsitePayment

_logger = logging.getLogger(__name__)


@http.route(['/website_payment/pay'], type='http', auth='public', website=True, sitemap=False)
def pay(self, reference='', order_id=None, amount=False, currency_id=None, acquirer_id=None, partner_id=False, access_token=None, **kw):
    """
    Generic payment page allowing public and logged in users to pay an arbitrary amount.

    In the case of a public user access, we need to ensure that the payment is made anonymously - e.g. it should not be
    possible to pay for a specific partner simply by setting the partner_id GET param to a random id. In the case where
    a partner_id is set, we do an access_token check based on the payment.link.wizard model (since links for specific
    partners should be created from there and there only). Also noteworthy is the filtering of s2s payment methods -
    we don't want to create payment tokens for public users.

    In the case of a logged in user, then we let access rights and security rules do their job.
    """
    env = request.env
    user = env.user.sudo()
    reference = normalize('NFKD', reference).encode('ascii', 'ignore').decode('utf-8')
    if partner_id and not access_token:
        raise werkzeug.exceptions.NotFound
    if partner_id and access_token:
        token_ok = request.env['payment.link.wizard'].check_token(access_token, int(partner_id), float(amount), int(currency_id))
        if not token_ok:
            raise werkzeug.exceptions.NotFound

    invoice_id = kw.get('invoice_id')

    # Default values
    values = {
        'amount': 0.0,
        'currency': user.company_id.currency_id,
    }

    # Check sale order
    if order_id:
        try:
            order_id = int(order_id)
            if partner_id:
                # `sudo` needed if the user is not connected.
                # A public user woudn't be able to read the sale order.
                # With `partner_id`, an access_token should be validated, preventing a data breach.
                order = env['sale.order'].sudo().browse(order_id)
            else:
                order = env['sale.order'].browse(order_id)
            values.update({
                'currency': order.currency_id,
                'amount': order.amount_total,
                'order_id': order_id
            })
        except:
            order_id = None

    if invoice_id:
        try:
            values['invoice_id'] = int(invoice_id)
        except ValueError:
            invoice_id = None

    # Check currency
    if currency_id:
        try:
            currency_id = int(currency_id)
            values['currency'] = env['res.currency'].browse(currency_id)
        except:
            pass

    # Check amount
    if amount:
        try:
            amount = float(amount)
            values['amount'] = amount
        except:
            pass

    # Check reference
    reference_values = order_id and {'sale_order_ids': [(4, order_id)]} or {}
    values['reference'] = env['payment.transaction']._compute_reference(values=reference_values, prefix=reference)

    # Check acquirer
    acquirers = None
    if order_id and order:
        cid = order.company_id.id
    elif kw.get('company_id'):
        try:
            cid = int(kw.get('company_id'))
        except:
            cid = user.company_id.id
    else:
        cid = user.company_id.id

    # Check partner
    if not user._is_public():
        # NOTE: this means that if the partner was set in the GET param, it gets overwritten here
        # This is something we want, since security rules are based on the partner - assuming the
        # access_token checked out at the start, this should have no impact on the payment itself
        # existing besides making reconciliation possibly more difficult (if the payment partner is
        # not the same as the invoice partner, for example)
        partner_id = user.partner_id.id
    elif partner_id:
        partner_id = int(partner_id)

    values.update({
        'partner_id': partner_id,
        'bootstrap_formatting': True,
        'error_msg': kw.get('error_msg')
    })

    acquirer_domain = ['&', ('state', 'in', ['enabled', 'test']), ('company_id', '=', cid)]
    if partner_id:
        partner = request.env['res.partner'].browse([partner_id])
        acquirer_domain = expression.AND([
            acquirer_domain,
            ['|', ('country_ids', '=', False), ('country_ids', 'in', [partner.sudo().country_id.id])]
        ])
    if acquirer_id:
        acquirers = env['payment.acquirer'].browse(int(acquirer_id))
    if order_id:
        acquirers = env['payment.acquirer'].search(acquirer_domain)
    if not acquirers:
        acquirers = env['payment.acquirer'].search(acquirer_domain)

    # s2s mode will always generate a token, which we don't want for public users
    valid_flows = ['form', 's2s'] if not user._is_public() else ['form']
    values['acquirers'] = [acq for acq in acquirers if acq.payment_flow in valid_flows or acq.provider == 'paypal_payflow']
    if partner_id:
        values['pms'] = request.env['payment.token'].search([
            ('acquirer_id', 'in', acquirers.ids),
            ('partner_id', '=', partner_id)
        ])
    else:
        values['pms'] = []

    return request.render('payment.pay', values)


WebsitePayment.pay = pay


class PaypalPayflowController(http.Controller):
    _accept_url = '/payment/paypal_payflow/test/accept'
    _decline_url = '/payment/paypal_payflow/test/decline'
    _exception_url = '/payment/paypal_payflow/test/exception'
    _cancel_url = '/payment/paypal_payflow/test/cancel'

    @http.route([
        '/payment/paypal_payflow/accept', '/payment/paypal_payflow/test/accept',
        '/payment/paypal_payflow/decline', '/payment/paypal_payflow/test/decline',
        '/payment/paypal_payflow/exception', '/payment/paypal_payflow/test/exception',
        '/payment/paypal_payflow/cancel', '/payment/paypal_payflow/test/cancel',
    ], type='http', auth='public', csrf=False)
    def paypal_payflow_form_feedback(self, **post):
        """ Handle both redirection from Ingenico (GET) and s2s notification (POST/GET) """
        _logger.info('Ogone: entering form_feedback with post data %s', pprint.pformat(post))  # debug
        request.env['payment.transaction'].sudo().form_feedback(post, 'paypal_payflow')
        return werkzeug.utils.redirect("/payment/process")

    @http.route(['/payment/paypal_payflow/s2s/create_json'], type='json', auth='public', csrf=False)
    def paypal_payflow_s2s_create_json(self, **kwargs):
        if not kwargs.get('partner_id'):
            kwargs = dict(kwargs, partner_id=request.env.user.partner_id.id)
        new_id = request.env['payment.acquirer'].browse(int(kwargs.get('acquirer_id'))).s2s_process(kwargs)
        return new_id.id

    @http.route(['/payment/paypal_payflow/s2s/create_json_3ds'], type='json', auth='public', csrf=False)
    def paypal_payflow_s2s_create_json_3ds(self, verify_validity=False, **kwargs):
        if not kwargs.get('partner_id'):
            kwargs = dict(kwargs, partner_id=request.env.user.partner_id.id)
        token = False
        error = None

        try:
            token = request.env['payment.acquirer'].browse(int(kwargs.get('acquirer_id'))).s2s_process(kwargs)
        except Exception as e:
            error = str(e)

        if not token:
            res = {
                'result': False,
                'error': error,
            }
            return res

        res = {
            'result': True,
            'id': token.id,
            'short_name': token.short_name,
            '3d_secure': False,
            'verified': True,
        }
        return res

    @http.route(['/payment/paypal_payflow/s2s/create'], type='http', auth='public', methods=["POST"], csrf=False)
    def paypal_payflow_s2s_create(self, **post):
        error = ''
        acq = request.env['payment.acquirer'].browse(int(post.get('acquirer_id')))
        try:
            token = acq.s2s_process(post)
        except Exception as e:
            # synthax error: 'CHECK ERROR: |Not a valid date\n\n50001111: None'
            token = False
            error = str(e).splitlines()[0].split('|')[-1] or ''

        if token and post.get('verify_validity'):
            baseurl = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            params = {
                'accept_url': baseurl + '/payment/paypal_payflow/validate/accept',
                'decline_url': baseurl + '/payment/paypal_payflow/validate/decline',
                'exception_url': baseurl + '/payment/paypal_payflow/validate/exception',
                'return_url': post.get('return_url', baseurl)
            }
            tx = token.validate(**params)
            if tx and tx.html_3ds:
                return tx.html_3ds
            # add the payment transaction into the session to let the page /payment/process to handle it
            PaymentProcessing.add_payment_transaction(tx)
        return werkzeug.utils.redirect("/payment/process")

    @http.route([
        '/payment/paypal_payflow/validate/accept',
        '/payment/paypal_payflow/validate/decline',
        '/payment/paypal_payflow/validate/exception',
    ], type='http', auth='public')
    def paypal_payflow_validation_form_feedback(self, **post):
        """ Feedback from 3d secure for a bank card validation """
        request.env['payment.transaction'].sudo().form_feedback(post, 'paypal_payflow')
        return werkzeug.utils.redirect("/payment/process")

    @http.route(['/payment/paypal_payflow/s2s/feedback'], auth='public', csrf=False)
    def feedback(self, **kwargs):
        try:
            tx = request.env['payment.transaction'].sudo()._paypal_payflow_form_get_tx_from_data(kwargs)
            tx._paypal_payflow_s2s_validate_tree(kwargs)
        except ValidationError:
            return 'ko'
        return 'ok'
