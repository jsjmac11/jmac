# -*- coding: utf-8 -*-

{
    # About module
    'name': 'Draggable Dialog',
    'category': 'Extra Tools',
    'license': 'OPL-1',
    'version': '13.0.1.0.0',
    'sequence': 717,
    'description': 'You can move all wizards of Odoo backend to see text behind it.',
    'summary': 'Make All Odoo Dialog Movable.',

    # About author
    'author': 'Bista Solutions',
    'company': 'Bista Solutions',
    'maintainer': 'Bista Solutions',
    'website': 'https://bistasolutions.com',  # Can be theme demo URL.

    # Module code/view(s)/technical/hooks/depends etc.
    'depends': ['web'],
    'data': [
        'views/assets.xml',
    ],

    # Other attributes
    'images': [
        'static/description/banner.jpeg',
        'static/description/move.gif',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
