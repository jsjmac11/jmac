# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

{
    'name': 'JMAC User Signup',
    'version': "13.0.1.0.0",
    'author': 'Bista Solutions Pvt. Ltd.',
    'website': "https://www.bistasolutions.com",
    'category': 'Base',
    'summary': """ User Signup""",
    'description': """ User Signup
    """,
    'depends': ['base', 'sale', 'product', 'mail', 'account'],
    'data': [
        'data/mail_template_data.xml'
    ],
    'auto_install': False
}
