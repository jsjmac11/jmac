# -*- coding: utf-8 -*-
##########################################################################
#
#    Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE URL <https://store.webkul.com/license.html/> for full copyright and licensing details.
##########################################################################
__all__=['extract_list','extract_item','add_text','chunks','get_fd','prettify']
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
MapId = lambda items:[item.id for item in items]
Mapname = lambda items:[item.name for item in items]

JoinList = lambda item,sep='':'%s'%(sep).join(map(str,item))


def extract_list(obj):
    if isinstance(obj,list) and len(obj):
        obj = obj[0]
    return obj

def extract_item(data,item='value'):
    if isinstance(data,dict):
        return data.get(item) and data.get(item) or data
    return data

def add_text(elem, text):
    elem.text = text

    return elem
def chunks(items, size=10):
    return list(items[i:i+size] for i in range(0, len(items), size))

def get_fd(item,f):
    return "{1:.{0}f}".format(f,item)

def prettify(elem):
    from xml.etree import ElementTree
    from xml.dom import minidom
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="\t")


def parsed_response(data,method):
    response = None
    DictWrapper,DataWrapper=None,None
    try:
        from mws import DictWrapper,DataWrapper
    except Exception as e:
        _logger.error("install mws")
    if DictWrapper and DataWrapper:
        try:
            response = DictWrapper(data, method+"Result")
        except XMLError:
            response = DataWrapper(data, [])
    if response: return response.parsed
