# -*- coding: utf-8 -*-
# @author Chintan Ambaliya <chintan.ambaliya@bistasolutions.com>

import logging
from odoo.http import request
from odoo import api, exceptions, fields, models, _

from odoo.addons.payment_paypal_payflow.payflowpro.classes import CreditCard, Amount, Profile, Address, ShippingAddress, Tracking, Response, CustomerInfo
from odoo.addons.payment_paypal_payflow.payflowpro.client import PayflowProClient, find_classes_in_list, find_class_in_list

_logger = logging.getLogger(__name__)

URL_BASE_TEST = 'https://pilot-payflowpro.paypal.com'
URL_BASE_LIVE = 'https://payflowpro.paypal.com'


class PaymentAcquirerTest(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('paypal_payflow', 'Paypal Payflow')])
    payflow_partner_id = fields.Char('Payflow Partner ID', required_if_provider='payflow')
    payflow_vendor_id = fields.Char('Payflow Vendor ID', required_if_provider='payflow')
    payflow_user_name = fields.Char('Username', required_if_provider='payflow')
    payflow_password = fields.Char('Password', required_if_provider='payflow')
    status = fields.Char(string='Connection Message', readonly=True, required_if_provider='payflow')
    connection_status = fields.Boolean(string="Connection Status", default=False, required_if_provider='payflow')

    def test_connection(self):
        status = ' Connection Un-successful'
        if self.payflow_partner_id and self.payflow_vendor_id and self.payflow_unm and self.payflow_pwd:
            status = "Congratulation, It's Successfully Connected with Paypal Payflow."
            self.connection_status = True
            self.status = status
        else:
            self.status = status
            self.connection_status = False
        return self.connection_status

    @api.model
    def _get_paypal_payflow_urls(self, environment):
        """ Paypal Payflow URLs """
        return {'authorize_form_url': URL_BASE_LIVE if environment == 'prod' else URL_BASE_TEST}

    def paypal_payflow_s2s_form_validate(self, data):
        error = dict()

        mandatory_fields = ["cc_number", "cc_cvc", "cc_holder_name", "cc_expiry", "cc_brand"]
        # Validation
        for field_name in mandatory_fields:
            if not data.get(field_name):
                error[field_name] = 'missing'

        return False if error else True

    @api.model
    def paypal_payflow_s2s_form_process(self, data):
        """ Return a minimal token to allow proceeding to transaction creation. """
        values = {
            'cc_number': data.get('cc_number'),
            'cc_cvc': int(data.get('cc_cvc')),
            'cc_holder_name': data.get('cc_holder_name'),
            'cc_expiry': data.get('cc_expiry'),
            'cc_brand': data.get('cc_brand'),
            'acquirer_id': int(data.get('acquirer_id')),
            'partner_id': int(data.get('partner_id')),
            'order_id': data.get('order_id') and int(data.get('order_id')) or False,
        }
        payment_token = self.env['payment.token'].sudo().create(values)
        return payment_token

    def paypal_payflow_get_form_action_url(self):
        self.ensure_one()
        environment = 'prod' if self.state == 'enabled' else 'test'
        return self._get_paypal_payflow_urls(environment)['paypal_payflow_form_url']


class PaymentTransactionTest(models.Model):
    _inherit = 'payment.transaction'

    def _paypal_payflow_form_validate(self, data):
        self._paypal_payflow_s2s_validate(data)

    def paypal_payflow_s2s_do_transaction(self, **data):
        self.ensure_one()
        URL = URL_BASE_LIVE if self.acquirer_id.state == 'enabled' else URL_BASE_TEST
        client = PayflowProClient(
            partner=self.acquirer_id.payflow_partner_id,
            vendor=self.acquirer_id.payflow_vendor_id,
            username=self.acquirer_id.payflow_user_name,
            password=self.acquirer_id.payflow_password,
            url_base=URL
        )
        responses, unconsumed_data = client.capture(
            self.payment_token_id.acquirer_ref
        )
        return self._paypal_payflow_s2s_validate_tree(responses[0].data)

    def _paypal_payflow_s2s_validate_tree(self, tree):
        return self._paypal_payflow_s2s_validate(tree)

    def _paypal_payflow_s2s_validate(self, tree):
        if self.state == 'done':
            _logger.warning('Paypal Payflow: trying to validate an already validated tx (ref %s)' % self.reference)
            return True
        status_code = tree.get('result')
        if status_code == '0':
            self.write({
                'acquirer_reference': tree.get('pnref'),
                'date': fields.Datetime.now(),
            })
            self._set_transaction_done()
            self.execute_callback()
            self.payment_token_id.active = False
            return True
        else:
            error = tree.get('respmsg')
            _logger.info(error)
            self.write({'acquirer_reference': tree.get('pnref')})
            self._set_transaction_error(msg=error)
            self.payment_token_id.active = False
            return False


class PaymentToken(models.Model):
    _inherit = 'payment.token'

    def paypal_payflow_create(self, values):
        order_id = values.get('order_id')
        if not order_id:
            order_id = request.session.get('sale_order_id')

        if values.get('cc_number') and order_id:
            acquirer = self.env['payment.acquirer'].browse(values['acquirer_id'])
            order = self.env['sale.order'].browse(order_id)
            amount = sum(order.mapped('amount_total'))
            values['cc_number'] = values['cc_number'].replace(' ', '')
            expiry = str(values['cc_expiry'][:2]) + str(values['cc_expiry'][-2:])
            partner = request.env.user.partner_id
            street = str(partner.street)
            city = str(partner.city)
            state = str(partner.state_id.name)
            zip_code = str(partner.zip)
            country = str(partner.country_id.name)
            URL = URL_BASE_LIVE if acquirer.state == 'enabled' else URL_BASE_TEST
            credit_card = CreditCard(
                acct=values['cc_number'],
                expdate=expiry,
                cvv2=values['cc_cvc']
            )
            client = PayflowProClient(
                partner=acquirer.payflow_partner_id,
                vendor=acquirer.payflow_vendor_id,
                username=acquirer.payflow_user_name,
                password=acquirer.payflow_password,
                url_base=URL
            )
            responses, unconsumed_data = client.authorization(
                credit_card,
                Amount(amt=amount, currency=order.currency_id.name),
                extras=[
                    Address(street=street, city=city,
                            state=state, zip=zip_code,
                            country=country),
                ]
            )
            tree = responses[0].data
            if tree.get('result') == '0':
                return {
                    'acquirer_ref': tree.get('pnref'),
                    'name': 'XXXXXXXXXXXX%s - %s' % (values['cc_number'][-4:], values['cc_holder_name'])
                }
            error = tree.get('respmsg')
            _logger.error(error)
            raise Exception(error)
        raise Exception(_('Order not found'))
