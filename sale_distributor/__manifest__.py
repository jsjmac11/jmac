# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

{
    'name': 'JMAC Sale Distributor',
    'version': "13.0.1.0.3",
    'author': 'Bista Solutions Pvt. Ltd.',
    'website': "https://www.bistasolutions.com",
    'category': 'Sale',
    'summary': """JMAC Sale Distributor module help to make the vendor details.""",
    'description': """
    JMAC Sale Distributor module help to make the vendor details.
    """,
    'depends': ['sale','sale_stock','product','mail','purchase_stock','account', 'sale_amazon'],
    'data': [
        'security/ir.model.access.csv',
        'data/res_partner_demo.xml',
        'data/stock_picking_demo.xml',
        'data/mail_template_data.xml',
        'view/sale_menuitem.xml',
        'view/sale_order.xml',
        'view/res_partner_view.xml',
        'view/vendor_stock_view.xml',
        'view/vendor_tabs_css.xml',
        'security/ir.model.access.csv',
        'wizard/notification_view.xml',
        'view/purchase_view.xml',
        'view/product_view.xml',
        'view/account_move_view.xml',
    ],
    'demo': [
        ],
    'auto_install': False
}
