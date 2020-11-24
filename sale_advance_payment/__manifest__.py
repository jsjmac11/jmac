##############################################################################
#
#    Bista Solutions
#    Copyright (C) 2020 (http://www.bistasolutions.com)
#
##############################################################################

{
    'name': 'Bista Advance Payment Sale',
    'version': '13.0.0.0.1',
    'category': 'Stock',
    'depends': ['account', 'sale', 'stock'],
    'author': 'Shawaz Jahangiri',
    'maintainer': 'Bista Solutions.',
    'summary': 'Advance Payment for Sale',
    'website': 'https://www.bistasolutions.com'
    'description': '''you can take advance payment regarding Sale and generate customer invoice
            ''',
    'website': 'www.bistasolutions.com',
    'data': [
         'wizard/advance_payment.xml',
         'views/sale_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}
