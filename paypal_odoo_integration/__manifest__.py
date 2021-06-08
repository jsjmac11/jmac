# -*- coding: utf-8 -*-
{
    'name': 'Paypal Payflow Pro Odoo Integration',
    'category': 'Sale',
    'author': "Bista Solutions",
    'version': "13.0.1.0.2",
    'summary': """Paypal Payflow Pro Odoo Integration""",
    'description': """""",
    'depends': ['sale_management', 'sale_advance_payment', 'payment', 'account'],
    'data': [
            "data/payment_acquirer_data.xml",
            'data/mail_data.xml',
            'wizard/paypal_payflow_payment_view.xml',
            'wizard/payment_link_wizard_views.xml',
            "views/sale_order.xml",
            "views/account_move_view.xml",
            "views/payment_view.xml",
            ],

    'images': [],
    'website':'http://www.bistasolutions.com',

    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',
}
