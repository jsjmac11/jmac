# -*- coding: utf-8 -*-
##########################################################################
#
#    Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#   See LICENSE URL <https://store.webkul.com/license.html/> for full copyright and licensing details.
##########################################################################
import logging
if __name__ == "__main__":
    logging.info('Starting logger for...')
_logger = logging.getLogger(__name__)
try:
    from mws import Products, Reports, Feeds,  Sellers,Orders
    from mws import MWSError
except Exception as e:
    _logger.error("install mws")

from xml.etree import ElementTree
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import SubElement
from xml.etree.ElementTree import dump
from itertools import  count

from .tools import (
    prettify,
    get_fd,
    add_text,
    extract_item,
    ProductIdType
)

class WKMWSAPI:

    def __init__(self,**kwargs):

        self.mws_access_key = kwargs.get('mws_access_key')
        self.mws_secret_key = kwargs.get('mws_secret_key')
        self.mws_merchant_id = kwargs.get('mws_merchant_id')
        self.mws_marketplace_id = kwargs.get('mws_marketplace_id')
        self.region = kwargs.get('region')
        self.domain = kwargs.get('domain')

    def _get_mws(self,obj):
        mws_access_key, mws_secret_key = self.mws_access_key, self.mws_secret_key
        mws_merchant_id, mws_marketplace_id = self.mws_merchant_id, self.mws_marketplace_id
        region, domain = self.region, self.domain
        if obj == 'Sellers':
            return Sellers(mws_access_key, mws_secret_key, mws_merchant_id, region=region, domain=domain)
        elif obj == 'Reports':
            return Reports(mws_access_key, mws_secret_key, mws_merchant_id, region=region, domain=domain)
        elif obj == 'Products':
            return Products(mws_access_key, mws_secret_key, mws_merchant_id, region=region, domain=domain)
        elif obj == 'Feeds':
            return Feeds(mws_access_key, mws_secret_key, mws_merchant_id, region=region, domain=domain)
        elif obj == 'Orders':
            return Orders(mws_access_key, mws_secret_key, mws_merchant_id, region=region, domain=domain,version='2013-09-01')

    def get_asin_from_product(self, product_id_type, barcode, wk_asin=None,**kwargs):
        Type=dict(ProductIdType).get(product_id_type)
        Value = Type == 'ASIN' and wk_asin or barcode

        try:
            data = self._get_mws('Products').get_matching_product_for_id(
                    self.mws_marketplace_id,type=Type,id=[Value]).parsed

            if extract_item(data.get('status',{}))=='Success':
                Products = data.get('Products',{})
                if len(Products):
                    Product = Products.get('Product',{})
                    if isinstance(Product,list):
                        Product = Product[0]
                    asin = Product.get('Identifiers',{}).get('MarketplaceASIN',{}).get('ASIN',{})
                    return extract_item(asin)

                # if isinstance(Products,list):
                #     Products = Products[0]
                # if isinstance(Products,dict):
                    # asin = Products.get('Product',{}).get('Identifiers',{}).get('MarketplaceASIN',{}).get('ASIN',{})
                    # return extract_item(asin)
        except MWSError as me:
            _logger.error("MWSError-get_asin_from_product---%r---",me)
        except Exception as e:
            _logger.error("MWSError-get_asin_from_product---%r---",e)

    def mws_post_feed(self, feed_type, AmazonEnvelope):
        final_result = dict(
            feed_id = None,
            message = ''
        )
        try:
            result = self._get_mws('Feeds').submit_feed(
            prettify(AmazonEnvelope).encode('utf-8'),feed_type=feed_type,
            marketplaceids=[self.mws_marketplace_id])
            final_result['feed_id'] = extract_item(result.parsed.get('FeedSubmissionInfo', {}
                ).get('FeedSubmissionId'))
        except MWSError as me:
            final_result['message'] ="<br/>%r"%(me)
        except Exception as e:
            final_result['message'] = '%r'%(e)
        return final_result

    def get_feed_result(self,feedid):
        try:
            result = self._get_mws('Feeds').get_feed_submission_result(feedid=feedid)
            if result:
                return result.original
        except MWSError as me:
            _logger.error("MWSError-get_feed_result---%r---",me)
            #raise Warning(me)
        except Exception as e:
            _logger.error("MWSError-get_feed_result---%r---",e)
            #raise Warning(e)

    @staticmethod
    def get_result_message(result):
        root = ElementTree.fromstring(result)

        process = root.findtext(
            'Message/ProcessingReport/ProcessingSummary/MessagesProcessed')
        success = root.findtext(
            'Message/ProcessingReport/ProcessingSummary/MessagesSuccessful')
        error = root.findtext(
            'Message/ProcessingReport/ProcessingSummary/MessagesWithError')
        message = '<br/> Product Proceed {0} , Successful {1} , With Error {2}  <br/> '.format(process, success, error)
        if error:
            res = root.findall(
        'Message/ProcessingReport/Result/ResultDescription')
            if len(res) >1:
                message+='<br/>'.join(map(lambda item:item.text,res[1:]))
            else :
                message+='<br/>'.join(map(lambda item:item.text,res))
        return message

    @staticmethod
    def construct_header( AmazonEnvelope, merchant_id):
        Header = SubElement(AmazonEnvelope, "Header")
        add_text(SubElement(Header, 'DocumentVersion'), text='1.01')
        add_text(SubElement(Header, 'MerchantIdentifier'), text=merchant_id)
        return AmazonEnvelope

    @classmethod
    def get_amazon_env(cls, MessageType, merchant_id):
        root_attribute = {"xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                          "xsi:noNamespaceSchemaLocation": "amzn-envelope.xsd"}
        AmazonEnvelope = Element("AmazonEnvelope", attrib=root_attribute)
        cls.construct_header(AmazonEnvelope, merchant_id)
        add_text(SubElement(AmazonEnvelope, 'MessageType'), text=MessageType)
        add_text(SubElement(AmazonEnvelope, 'PurgeAndReplace'), text='false')
        return AmazonEnvelope

    @staticmethod
    def get_message(AmazonEnvelope, message_id, operation=None):
        Message = SubElement(AmazonEnvelope, "Message")
        add_text(SubElement(Message, 'MessageID'), text=message_id)
        if operation:
            add_text(SubElement(Message, 'OperationType'), text=operation)
        return Message

    @classmethod
    def construct_order_fulfillment(cls,AmazonEnvelope, message_id, record,items_list=None):
        Message = cls.get_message(AmazonEnvelope, str(message_id))
        OrderFulfillment = SubElement(Message, "OrderFulfillment")
        add_text(SubElement(OrderFulfillment, 'AmazonOrderID'), text=record.get('AmazonOrderID'))
        add_text(SubElement(OrderFulfillment, 'FulfillmentDate'), text=record.get('FulfillmentDate'))
        FulfillmentData = SubElement(OrderFulfillment, "OrderFulfillment")
        add_text(SubElement(FulfillmentData, 'CarrierCode'), text=record.get('CarrierCode'))
        add_text(SubElement(FulfillmentData, 'CarrierName'), text=record.get('CarrierName'))
        add_text(SubElement(FulfillmentData, 'ShippingMethod'), text=record.get('ShippingMethod'))
        add_text(SubElement(FulfillmentData, 'ShipperTrackingNumber'), text=record.get('ShipperTrackingNumber'))
        if items_list:
            for item in items_list:
                Item   = SubElement(OrderFulfillment, "Item")
                add_text(SubElement(FulfillmentData, 'AmazonOrderItemCode'), text=item.get('AmazonOrderItemCode'))
                add_text(SubElement(FulfillmentData, 'Quantity'), text=item.get('Quantity'))
        return AmazonEnvelope

    @classmethod
    def construct_product(cls, AmazonEnvelope, message_id, item, node_id,parentage= 'child'):
        Message = cls.get_message(AmazonEnvelope, str(message_id), 'Update')
        Product = SubElement(Message, "Product")
        add_text(SubElement(Product, 'SKU'), text=item.get('default_code'))
        StandardProductID = SubElement(Product, "StandardProductID")
        Type=dict(ProductIdType).get(item.get('wk_product_id_type'))
        Value = Type == 'ASIN' and item.get('wk_asin') or item.get('barcode')
        add_text(SubElement(StandardProductID, 'Type'), text = Type)
        add_text(SubElement(StandardProductID, 'Value'), text = Value)
        add_text(SubElement(Product, 'ProductTaxCode'), text = 'A_GEN_NOTAX')

        DescriptionData = SubElement(Product, "DescriptionData")
        add_text(SubElement(DescriptionData, 'Title'), text = item.get('name'))
        # add_text(SubElement(DescriptionData, 'Brand'), text='Valued Naturals')
        # add_text(SubElement(DescriptionData, 'Designer'), text='Designer Rugs')
        description = item.get('description_sale')
        description = (description and description or  item.get('name'))[:2000]
        if description:
            add_text(SubElement(DescriptionData, 'Description'),text=description)
            bullet_points = description.split('\n')
            for bullet_point in bullet_points[::5]:
                add_text(SubElement(DescriptionData, 'BulletPoint'), text=bullet_point)
        if node_id:
            add_text(SubElement(DescriptionData, 'RecommendedBrowseNode'),text=node_id)
        return AmazonEnvelope

    @classmethod
    def construct_inventory(cls,AmazonEnvelope, message_id, record, default_qty=1):
        Message = cls.get_message(AmazonEnvelope, str(message_id), 'Update')
        Inventory = SubElement(Message, "Inventory")
        add_text(SubElement(Inventory, 'SKU'), text = record.get('default_code'))
        quantity = record.get('qty_available') or default_qty
        add_text(SubElement(Inventory, 'Quantity'), text=str(int(quantity)))
        # if record.get('sale_delay'):
            # add_text(SubElement(Inventory, 'QuaFulfillmentLatencyntity'), text=str(int(record.get('sale_delay'))))
        return AmazonEnvelope

    @classmethod
    def construct_price(cls,AmazonEnvelope, message_id, record,currency):
        Message = cls.get_message(AmazonEnvelope, str(message_id), 'Update')
        Price = SubElement(Message, "Price")
        add_text(SubElement(Price, 'SKU'), text=record.get('default_code'))
        price = record.get('price')
        add_text(SubElement(Price, 'StandardPrice',
                    attrib={'currency': currency}),
                    text=str(get_fd(price,2)))

        return AmazonEnvelope


    @classmethod
    def construct_image(cls,AmazonEnvelope, message_id, data,image_type='Main'):
        Message = cls.get_message(AmazonEnvelope, str(message_id), 'Update')
        ProductImage = SubElement(Message, "ProductImage")
        add_text(SubElement(ProductImage, 'SKU'), text=data.get('default_code'))
        add_text(SubElement(ProductImage, 'ImageType'), text=image_type)
        add_text(SubElement(ProductImage, 'ImageLocation'), text=data.get('url'))
        return AmazonEnvelope

    @classmethod
    def construct_product_relationship(cls,AmazonEnvelope, message_id, parent_sku,child_data):
        Message = cls.get_message(AmazonEnvelope, str(message_id), 'Update')
        Relationship =  SubElement(Message, "Relationship")
        add_text(SubElement(Relationship, 'ParentSKU'), text=parent_sku)
        for child in child_data:
            ProductRelation = SubElement(Relationship, "Relation")
            add_text(SubElement(ProductRelation, 'SKU'), text=child.get('default_code'))
            add_text(SubElement(ProductRelation, 'Type'), text='Variation')

    def post_product_data(self,items,node_id = None):
        feed_type = '_POST_PRODUCT_DATA_'
        AmazonEnvelope = self.get_amazon_env('Product', self.mws_merchant_id)
        for message_id, item in enumerate(items, 1):
            percent = 'parent' if message_id==1 else 'child'
            self.construct_product(AmazonEnvelope, message_id, item, node_id,percent)
        # print prettify(AmazonEnvelope)
        return self.mws_post_feed(feed_type, AmazonEnvelope)

    def wk_request_report(self,report_type,**kwargs):
        """
            type :_GET_FLAT_FILE_OPEN_LISTINGS_DATA_ ,_GET_MERCHANT_LISTINGS_DATA_
        """
        report = self._get_mws('Reports')
        data = dict(
            Action='RequestReport',
            ReportType=report_type,
            StartDate=None,
            EndDate=None,
        )
        report_options = kwargs.get('report_options')
        if report_options:data['ReportOptions']=report_options
        data.update(report.enumerate_param('MarketplaceIdList.Id.',
            [self.mws_marketplace_id])
        )
        request= report.make_request(data)
        return extract_item(request.parsed.get('ReportRequestInfo', {}).get('ReportRequestId', {}))

    def wk_get_reportId(self, requestids):
        report = self._get_mws('Reports')
        report_list = report.get_report_list(requestids=requestids)
        return report_list.parsed.get('ReportInfo', {})#ET.get('ReportId', {}))

    def wk_get_report_data(self, report_id):
        res = dict(
            message = '',
            data = None
        )
        try:
            report = self._get_mws('Reports')
            res['data'] = report.get_report(report_id=report_id)
        except MWSError as me:
            res['message']+="<br/>%s"%(me)
            message =('MWSError while wk_get_report_data[%s]  %s'%(report_id,me))
            _logger.error("##%s"%(message))
        except Exception as e:
            message =('Exception while product_categ_for_asin[%s]  %s'%(report_id,e))
            _logger.error("##%s"%(message))
            res['message']+="<br/>%s"%(e)
        return res

    @staticmethod
    def extract_report_data(report,report_header = None):
        report_header = report_header or dict()
        data = report.split('\n')
        header = data[0].split('\t')
        res = {}
        for item in data[1:]:
            data = dict(zip(header, item.split('\t')))
            sku = None
            if report_header.get('seller-sku') and data.get(report_header.get('seller-sku')):
                sku  = data.get(report_header.get('seller-sku')) or data.get('sku')
            elif report_header.get('sku') and data.get(report_header.get('sku')):
                sku  = data.get(report_header.get('sku'))
            if sku:res[sku] = data
        return res

    def get_mws_product_categ_for_asin(self, asin):
        """
                asin='B01ITNHZVQ'
        """
        product = self._get_mws('Products')
        res = {'data': None,'message':""}
        try:
            response = product.get_product_categories_for_asin(
                marketplaceid=self.mws_marketplace_id, asin=asin)
            res['data'] = response.parsed
        except MWSError as me:
            res['message']+="<br/>%s"%(me)
            message =('MWSError while product_categ_for_asin[%s]  %s'%(asin,me))
            _logger.error("##%s"%(message))
        except Exception as e:
            message =('Exception while product_categ_for_asin[%s]  %s'%(asin,e))
            _logger.error("##%s"%(message))
            res['message']+="<br/>%s"%(e)
        return res

    @staticmethod
    def process_mws_categ_data(data):
        res = []
        if type(data)==list:
            data =data[0]
        while data.get('Parent'):
            vals = dict(name=extract_item(data.get('ProductCategoryName')),
                         store_id=extract_item(data.get('ProductCategoryId')),
                         parent_id=extract_item(data.get('Parent').get('ProductCategoryId')))
            data = data.get('Parent',{})
            if not data.get('Parent'):
                vals['name'] = extract_item(data.get('ProductCategoryName'))
            res += [vals]

        return res

    def get_mws_product_by_asins(self, asins):
        """
                asins  : ['B01J9ZG8W0', 'B01HTQ2ZXC', 'B000MSH2F6', 'B00OHW1VL4', 'B011V0K3DQ', 'B01JA02U62', 'B01JA02UDK']
        """
        res = {'data': {}, 'message': ''}
        try:
            product = self._get_mws('Products')
            response = product.get_matching_product(
                marketplaceid=self.mws_marketplace_id, asins=asins)
            res['data'] = response.parsed
        except MWSError as me:
            res['message']+="<br/>%s"%(me)
            message =('MWSError while get_mws_product_by_asins[%s]  %s'%(asins,me))
            _logger.error("##%s"%(message))
        except Exception as e:
            res['message']+="<br/>%s"%(e)
        return res

    def _wk_list_inventory(self,skus, **kwargs):
        res = {'data': None,'message':''}
        from_date, to_date = kwargs.get('from_date'), kwargs.get('to_date')
        inventory = self._get_mws('Inventory')
        lastupdatedafter = fields.Datetime.from_string(
            from_date).isoformat()
        report_data=self.report_id.get_report_data()
        if report_data:
            sku_keys = set(report_data)
        response = inventory.list_inventory_supply(skus=skus)
        res['data'] = response.parsed
        return res

    def _wk_list_orders(self, **kwargs):
        res = {'data': None,'message':''}
        from_date, to_date = kwargs.get('from_date'), kwargs.get('to_date')
        order = self._get_mws('Orders')

        lastupdatedafter = fields.Datetime.from_string(
            from_date).isoformat()
        lastupdatedbefore = fields.Datetime.from_string(
            to_date).isoformat()

        try:
            response = order.list_orders(
                marketplaceids = [self.mws_marketplace_id],
                lastupdatedafter = lastupdatedafter,
                lastupdatedbefore = lastupdatedbefore
            )
            res['data'] = response.parsed
        except MWSError as me:
            message = ('MWSError while list orders %r'%(me))
            _logger.error("##%s %r"%(message,kwargs))
            res['message'] = message
            #raise Warning(me)

        except Exception as e:
            message = ('Exception while list orders %r'%(e))
            _logger.error("##%s %r"%(message,kwargs))
            res['message'] = message
            #raise Warning(e)

        return res

    def _wk_order_by_ids(self, order_ids):
        res = {'data': None}

        order = self._get_mws('Orders')
        try:
            response = order.get_order(amazon_order_ids = order_ids)
            res['data'] = response.parsed
        except MWSError as me:
            message =('MWSError while list orders[%s]  %s'%(order_ids,me))
            _logger.error("##%s"%(message))
            res['message']=message
            #raise Warning(me)

        except Exception as e:
            message =('Exception while list orders[%s]  %s'%(order_ids,e))
            _logger.error("##%s"%(message))
            res['message']=message
            #raise Warning(e)

        return res

    def _wk_list_order_items(self,order_id):
        res = {'data': None}

        order = self._get_mws('Orders')
        try:
            response = order.list_order_items(amazon_order_id=order_id)
            res['data'] = response.parsed
        except MWSError as me:
            message =('MWSError while list orders[%s]  %s'%(order_id,me))
            _logger.error("##%s"%(message))
            res['message']=message
        except Exception as e:
            message =('Exception while list orders[%s]  %s'%(order_id,e))
            _logger.error("##%s"%(message))
            res['message']=message
        return res

    def wk_list_order_items(self,order_id):
        response = self._wk_list_order_items(order_id)
        res_data =  response.get('data',{})
        message = response.get('message','')
        res=None
        if res_data:
            res={}
            OrderItem= res_data.get('OrderItems',{}).get('OrderItem',{})
            if type(OrderItem)!=list:
                OrderItem = [OrderItem]
            for item in OrderItem:
                ASIN = extract_item(item.get('ASIN'))
                data =dict(
                    SellerSKU=extract_item(item.get('SellerSKU')),
                    Title = extract_item(item.get('Title')),
                    ASIN = ASIN,
                    QuantityOrdered = extract_item(item.get('QuantityOrdered')),
                    ItemPrice =extract_item(item.get('ItemPrice',{}).get('Amount')),
                    ShippingPrice =extract_item(item.get('ShippingPrice',{}).get('Amount','0.0')),
                    ItemTax = extract_item(item.get('ItemTax',{}).get('Amount')),
                )
                res[ASIN]=data
        return dict(
            data = res,
            message =message
            )

    def process_order_data(self,orders):
        if orders:
            if type(orders)!=list:orders=[orders]
            response={}
            for order in filter(lambda order: extract_item(order.get('OrderStatus')) in OrderStatus ,orders):
                AmazonOrderId = extract_item(order.get('AmazonOrderId'))
                data = dict(
                    OrderStatus=extract_item(order.get('OrderStatus')),
                    PurchaseDate = extract_item(order.get('PurchaseDate',)),
                    BuyerEmail = extract_item(order.get('BuyerEmail')),
                    BuyerName  = extract_item(order.get('BuyerName')),
                    PaymentMethod = extract_item(order.get('PaymentMethod')),
                    FulfillmentChannel =  extract_item(order.get('FulfillmentChannel')),
                    ShippingAddress = order.get('ShippingAddress'),
                    AmazonOrderId =AmazonOrderId ,
                    OrderTotal = order.get('OrderTotal',{}),
                )
                response[AmazonOrderId]=data
            return response

    def wk_list_orders(self):
        response = self._wk_list_orders()
        orders=[]
        res_data = response.get('data',{})
        if res_data:
            orders = res_data.get('Orders',{}).get('Order',{})
        order_data=self.process_order_data(orders)
        return dict(
            data=order_data,
            message=response.get('message','')
        )

    def wk_order_by_ids(self,order_ids):
        orders=[]
        message=''
        for item in chunks(list(set(order_ids)),50):
            res= self._wk_order_by_ids(item)
            res_data=res.get('data',{})
            if res_data:
                response = res_data.get('Orders',{}).get('Order',{})
                if type(response)!=list:response=[response]
                if type(response)==list:orders+=response
            else:
                message+=res.get('message','')
        order_data=self.process_order_data(orders)
        return dict(
            data=order_data,
            message=message
        )


if __name__=='__main__':
    pass
