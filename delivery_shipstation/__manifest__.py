# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################
{
    'name': "ShipStation Delivery",

    'summary': """
        ShipStation Delivery servicess""",

    'description': """
        This module is integrate shipstation shipping services with odoo.
        Fetching services, shipping price and genrate labels from shipstation
        in odoo and deliver the shipments.
    """,

    'author': "Bista Solutions",
    'website': "http://www.bistasolutions.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Inventory',
    'version': "13.0.2.0.0",
    'application': True,
    # any module necessary for this one to work correctly
    'depends': ['base', 'delivery', 'stock', 'sale', 'stock_picking_batch'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/shipstation_data.xml',
        'views/configuration_views.xml',
        'views/picking_view.xml',
        'views/automation_rule_view.xml',
        'wizard/shipping_rates.xml',
        'wizard/delivery_package_view.xml',
        'views/sale_order_view.xml',
        'views/picking_batch_view.xml',
        'views/product_template_view.xml',
        # 'views/delivery_portal_template.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
