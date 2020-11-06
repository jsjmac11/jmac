# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################


{
    'name': 'ODOO Email CC and BCC',
    'summary': 'Add CC and BCC feature in mail',
    'category': 'Marketing',
    'version': '13.0.1.0.3',
    'sequence': 1,
    'author': "Bista Solutions Pvt. Ltd.",
    'website': 'https://www.bistasolutions.com',
    'description': """Add CC and BCC feature in mail,
    Email CC, Email Bcc, mail features, Email cc feature, Email Bcc features, Email CC IDs, Email BCC IDs""",
    'depends': ['mail'],
    'data': [
        'views/compose_view.xml',
    ],
    "images":  ['static/description/icon.png'],
    "application":  True,
    "installable":  True,
    "auto_install":  False,
    "pre_init_hook":  "pre_init_check",
}
