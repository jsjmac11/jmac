# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################


{
    'name': 'Bista Mail - JMAC',
    'version': "13.0.1.0.2",
    'author': 'Bista Solutions Pvt. Ltd.',
    'website': "https://www.bistasolutions.com",
    'category': 'Mail',
    'summary': """Change the chatter message Label.""",
    'description': """Bista Mail - JMAC module change the chatter label.
    Example : Send Message --> External Message and Log Note --> Internal Message
    """,
    'depends': ['mail', 'base'],
    'data': [
        'views/res_partner_view.xml',
    ],
    "qweb": [
        'static/src/xml/chatter.xml'
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
