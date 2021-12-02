##############################################################################
#
#    Bista Solutions
#    Copyright (C) 2019 (http://www.bistasolutions.com)
#
##############################################################################

{
    'name': 'Distributor Data Import Enhancement',
    'version': '13.0.0.0.1',
    'category': 'Base',
    'depends': ['base', 'product', 'sale'],
    'license': 'AGPL-3',
    'author': 'Bista Solutions Inc.',
    'maintainer': 'Bista Solutions.',
    'summary': 'This module allow to import distributor data',
    'description': '''
        - Import Distributor Pricelist
        - Import Distributor Stock
    ''',
    'website': 'www.bistasolutions.com',
    'data': [
        'wizard/distributor_data_import.xml',
    ],
    'installable': True,
    'auto_install': False,
}
