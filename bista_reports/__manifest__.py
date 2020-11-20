# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

{
    'name': 'JMAC Reports',
    'version': "13.0.1.0.2",
    'author': 'Bista Solutions Pvt. Ltd.',
    'website': "https://www.bistasolutions.com",
    'category': 'Base',
    'summary': """JMAC custom header and footer layout with custom reports""",
    'description': """
    JMAC custom header and footer layout with custom reports of sales 
    and purchase.
    """,
    'depends': ['base', 'sale', 'purchase', 'stock', 'web', 
                'sale_stock', 'delivery','sale_distributor'],
    'data': [
        'report/base_report_header.xml',
        'report/quotation_template.xml',
        'report/purchase_report_template.xml',
        'data/report_data.xml',
        'report/report_packing_slip.xml',

    ],
    'auto_install': False
}
