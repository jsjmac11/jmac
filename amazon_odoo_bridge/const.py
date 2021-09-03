# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE URL <https://store.webkul.com/license.html/> for full copyright and licensing details.
#################################################################################
FIELDS = ['name', 'weight', 'price','list_price',
         'qty_available', 'default_code', 'barcode','wk_asin',
         'wk_product_id_type','description_sale'
 ]
MAPPINGDOMAIN = lambda need_sync: [('ecom_store', '=', 'amazon'),
                                    ('need_sync', 'in', need_sync)]
ProductIdType=[
    ('wk_upc','UPC'),
    ('wk_ean','EAN'),
    ('wk_isbn','ISBN'),
    ('wk_asin','ASIN'),
]
CHANNELDOMAIN = [('channel', '=', 'amazon'),('state', '=', 'validate')]
