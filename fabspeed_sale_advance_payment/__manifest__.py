##############################################################################
#
#    Bista Solutions
#    Copyright (C) 2020 (http://www.bistasolutions.com)
#
##############################################################################

{
    'name': 'Bista Fab Speed Advance Payment Sale',
    'version': '13.0.0.0.1',
    'category': 'Stock',
    'depends': ['account', 'sale', 'stock'],
    'license': 'AGPL-3',
    'author': 'Bista Solutions.',
    'maintainer': 'Bista Solutions.',
    'summary': 'Advance Payment for Sale',
    'description': '''you can take advance payment regarding Sale and generate vender bill later
            ''',
    'website': 'www.bistasolutions.com',
    'data': [
         'wizard/advance_payment.xml',
         'views/sale_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}
