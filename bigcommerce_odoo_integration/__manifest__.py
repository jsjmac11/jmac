{
    # App information
    'name': 'BigCommerce Odoo Integration',
    'category': 'Website',
    'author': "Vraja Technologies",
    'version': '13.0.7.12.2020',
    'summary': """BigCommerce Odoo Integration will help you connect with Market Place.""",
    'description': """""",

    'depends': ['delivery','sale_management'],

    'data': [
             'data/delivery_demo.xml',
             'data/ir_cron.xml',
             'security/ir.model.access.csv',
             'views/warehouse.xml',
             'views/menuitem.xml',
             'views/bigcommerce_store_configuration_view.xml',
             'views/bigcommerce_operation_details.xml',
             # 'views/product_category.xml',
             'views/bigcommerce_category_view.xml',
             "views/product_template.xml",
             "views/product_attribute.xml",
             "views/res_partner.xml",
             "views/sale_order.xml",
             "views/bigcommerce_product_image_view.xml",
             "views/export_order_to_bigcommerce_button_view.xml",
             "views/bigcommerce_stock_picking_view.xml",
             # "views/shipped_product_view.xml",
             "views/bc_product_brand.xml",
             ],

    
    'images': ['static/description/bigcommerce_cover_image.png'],
    'maintainer': 'Vraja Technologies',
    'website':'www.vrajatechnologies.com',

    'demo': [],
    'live_test_url': 'http://www.vrajatechnologies.com/contactus',
    'installable': True,
    'application': True,
    'auto_install': False,
    'price': '299',
    'currency': 'EUR',
    'license': 'OPL-1',

}
