# -*- coding: utf-8 -*-
# @author Chintan Ambaliya <chintan.ambaliya@bistasolutions.com>

import logging
import pprint
import werkzeug
from unicodedata import normalize

from odoo import http
from odoo.http import request
from odoo.osv import expression
from odoo.exceptions import AccessError, MissingError
from odoo.addons.sale.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


class CustomerPortalExtended(CustomerPortal):
    
    @http.route()
    def portal_order_page(self, order_id, report_type=None, access_token=None, message=False, download=False, **kw):
        try:
            order_sudo = self._document_check_access('sale.order', order_id, access_token=access_token)
            payment_tx_id = order_sudo.get_portal_last_transaction()
            # TODO: Implement you logic  here
            if payment_tx_id and payment_tx_id.payment_id:
                payment_tx_id.payment_id.write(
                    {'sale_order_id': order_sudo and order_sudo.id})
                order_sudo.write(
                    {'paypal_transaction_id': payment_tx_id.acquirer_reference})
        except (AccessError, MissingError):
            pass
        return super(CustomerPortalExtended, self).portal_order_page(
            order_id, report_type=report_type, access_token=access_token,
            message=message, download=download, **kw
        )
