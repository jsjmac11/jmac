# -*- coding: utf-8 -*-
# @author Chintan Ambaliya <chintan.ambaliya@bistasolutions.com>

{
    'name': 'Paypal Payflow Payment Acquirer',
    'category': 'Sale/Payment',
    'summary': 'Payment Acquirer: Paypal Payflow Implementation',
    'version': '13.0.1.0.0',
    'author': 'Bista Solutions Pvt. Ltd., Chintan Ambaliya',
    'website': 'http://www.bistasolutions.com',
    'description': """Paypal Payflow Payment Acquirer""",
    'depends': ['payment', 'sale'],
    'data': [
        'security/payment_security.xml',
        'views/payment_views.xml',
        'views/payment_payflow_templates.xml',
        'data/payment_acquirer_data.xml',
    ],
    'installable': True,
    'post_init_hook': 'create_missing_journal_for_acquirers',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
}
