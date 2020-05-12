# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

{
    'name': 'JMAC Helpdesk',
    'version': "13.0.1.0.1",
    'author': 'Bista Solutions Pvt. Ltd.',
    'website': "https://www.bistasolutions.com",
    'category': 'Base',
    'summary': """""",
    'description': """
    """,
    'depends': ['base','sale','helpdesk'],
    'data': [
        'views/helpdesk_team_view_inherit.xml',
        'views/helpdesk_ticket_view_inherit.xml',
        'views/sale_order_inherite_view.xml',
    ],
    'auto_install': False
}
