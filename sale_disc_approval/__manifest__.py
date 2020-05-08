# -*- coding: utf-8 -*-
#############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
#############################################################################

{
    'name': 'Sale Discount Approval',
    'version': '13.0.1.0.1',
    'category': 'Sales Management',
    'summary': "Discount on Total in Sale and Invoice With Discount Limit and Approval",
    'author': 'Bista Solutions',
    'company': 'Bista Solutions',
    'website': 'http://www.bistasolutions.com',
    'description': """

Sale Discount for Total Amount
=======================
Module to manage discount on total amount in Sale.
        as an specific amount or percentage
""",
    'depends': ['sale',
                'account', 'delivery'
                ],
    'data': [
        'views/sale_view.xml',
        'views/res_config_view.xml',

    ],
    'demo': [
    ],
    'images': [],
    'application': True,
    'installable': True,
    'auto_install': False,
}
