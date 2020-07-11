# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

{
    'name': 'JMAC Delivery Cost',
    'version': "13.0.1.0.2",
    'author': 'Bista Solutions Pvt. Ltd.',
    'website': "https://www.bistasolutions.com",
    'category': 'Base',
    'summary': """JMAC Delivery cost module help to make the calculation
    of Delivery cost based on JMAC Rules.""",
    'description': """
    JMAC Delivery cost module help to make the calculation
    of Delivery cost based on JMAC Rules.
    """,
    'depends': ['delivery','product'],
    'data': [
        'view/res_partner.xml',
        'view/product_views.xml',
    ],
    'auto_install': False
}
