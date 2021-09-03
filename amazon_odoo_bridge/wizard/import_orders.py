# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE URL <https://store.webkul.com/license.html/> for full copyright and licensing details.
#################################################################################
from dateutil.parser import parse as date_parse
import logging
_logger = logging.getLogger(__name__)

try:
    from mws import MWSError
except Exception as e:
    _logger.error("install mws")
    
from odoo import api, fields, models, _
from odoo.exceptions import UserError,RedirectWarning, ValidationError
from odoo.addons.amazon_odoo_bridge.tools.tools import extract_item as EI
from odoo.addons.amazon_odoo_bridge.tools.tools import chunks
from odoo.addons.amazon_odoo_bridge.tools.tools import CHANNELDOMAIN


Source = [
	('all', 'All'),
	('order_ids', 'Order ID(s)'),
]
OrderStatus = [
    'Canceled',
    'Unshipped',
    'PartiallyShipped',
    'Shipped',
    'Pending'
]
SyncStatus = [
    (True,'success'),
    (False,'error')
]


class ImportMwsOrders(models.TransientModel):
    _name = "import.mws.orders"
    _inherit = ['import.orders']

    report_id = fields.Many2one(
        string='Report',
        comodel_name='mws.report',
        domain=[
        ('state','=','receive'),
        ('report_type','in', ['OPEN_LISTINGS_MERCHANT_LISTINGS']),
        ('ml_data','!=',False),
        ('data','!=',False),
        ]
    )
    max_results = fields.Integer(
        string='Max Result',
        default=100
    )

    @api.model
    def default_get(self,fields):
        res=super(ImportMwsOrders,self).default_get(fields)
        context = dict(self._context)
        params =context.get('params',{})
        active_id = context.get('active_id') or params.get('id')
        model = 'multi.channel.sale'
        if (active_id and
            (context.get('active_model')==model or params.get('model')==model)):
            context['channel_id'] = active_id
            report_status = self.channel_id.with_context(context).mws_ensure_report()
            report_id = report_status.get('report_id')
            if report_status.get('message'):
                action_id = self.env.ref('amazon_odoo_bridge.action_reports').id
                raise RedirectWarning(report_status.get('message'), action_id, _('Go to the report panel.'))
        return res

    @api.model
    def _wk_list_orders(self, **kwargs):
        res = {'data': None,'message':''}
        # order_vals = self.read(['from_date','to_date'])[0]
        channel_id = kwargs.get('channel_id')
        order = channel_id._get_mws('Orders')
        create_before = fields.Datetime.from_string(
            self.to_date).isoformat()
        context = self._context
        if context.get("order_import_cron"):
            create_after = fields.Datetime.from_string(
                channel_id.import_order_date or self.from_date).isoformat()
        elif context.get("order_status_cron"):
            create_after = fields.Datetime.from_string(
                channel_id.update_order_date or self.from_date).isoformat()
        else:
            create_after = fields.Datetime.from_string(
                self.from_date).isoformat()
        try:
            response = order.list_orders(
                marketplaceids = [channel_id.mws_marketplace_id],
                created_after = create_after,
                created_before = create_before,
                next_token = kwargs.get('nextToken')
            )
            res['data'] = response
        except MWSError as me:
            message = _('MWSError while list orders %s'%(me))
            _logger.error("##%s"%(message))
            res['message'] = message
        except Exception as e:
            message = _('Exception while list orders %s'%(e))
            _logger.error("##%s"%(message))
            res['message'] = message
        return res

    def _wk_order_by_ids(self, order_ids):
        res = {'data': None}
        order = self.channel_id._get_mws('Orders')
        try:
            response = order.get_order(amazon_order_ids = order_ids)
            res['data'] = response
        except MWSError as me:
            message =_('MWSError while list orders ids [%s]  %s'%(order_ids,me))
            _logger.error("##%s"%(message))
            res['message']=message
        except Exception as e:
            message =_('Exception while list orders ids[%s]  %s'%(order_ids,e))
            _logger.error("##%s"%(message))
            res['message']=message
        return res

    def _wk_list_order_items(self,order_id):
        res = {'data': None}

        order = self.channel_id._get_mws('Orders')
        try:
            response = order.list_order_items(amazon_order_id=order_id)
            res['data'] = response
        except MWSError as me:
            message =_('MWSError while list orders items [%s]  %s'%(order_id,me))
            _logger.error("##%s"%(message))
            res['message']=message
        except Exception as e:
            message =_('Exception while list orders items[%s]  %s'%(order_id,e))
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
            OrderItem= res_data.parsed.get('OrderItems',{}).get('OrderItem',{})
            encoding = res_data.response.encoding
            if type(OrderItem)!=list:
                OrderItem = [OrderItem]
            for item in OrderItem:
                SellerSKU = EI(item.get('SellerSKU'))
                data =dict(
                    SellerSKU=SellerSKU,
                    Title = EI(item.get('Title')).encode(encoding).decode('utf-8'),
                    ASIN = EI(item.get('ASIN')),
                    QuantityOrdered = EI(item.get('QuantityOrdered')),
                    ItemPrice =EI(item.get('ItemPrice',{}).get('Amount')),
                    ShippingPrice =EI(item.get('ShippingPrice',{}).get('Amount','0.0')),
                    ItemTax = EI(item.get('ItemTax',{}).get('Amount')),
                    ShippingDiscount=EI(item.get('ShippingDiscount',{}).get('Amount'))
                )
                res[SellerSKU]=data
        return dict(
            data = res,
            message =message,
            )

    def process_order_data(self,orders, encoding):
        if orders:
            if type(orders)!=list:orders=[orders]
            response={}
            for order in filter(lambda order: EI(order.get('OrderStatus')) in OrderStatus ,orders):
                AmazonOrderId = EI(order.get('AmazonOrderId'))
                name = ''
                if order.get('BuyerName'):
                    name = EI(order.get('BuyerName')).encode(encoding).decode('utf-8')

                addr =  order.get('ShippingAddress',{})
                if addr:
                    if addr.get('Name'):
                        addr['Name']         = EI(addr.get('Name')).encode(encoding).decode('utf-8')
                    if addr.get('AddressLine1'):
                        addr['AddressLine1'] =  EI(addr.get('AddressLine1')).encode(encoding).decode('utf-8')
                    if addr.get('AddressLine2'):
                        addr['AddressLine2'] =  EI(addr.get('AddressLine2')).encode(encoding).decode('utf-8')
                    if addr.get('AddressLine3'):
                        addr['AddressLine3'] =  EI(addr.get('AddressLine3')).encode(encoding).decode('utf-8')
                    if addr.get('City'):
                        addr['City']         =  EI(addr.get('City')).encode(encoding).decode('utf-8')


                data = dict(
                    OrderStatus=EI(order.get('OrderStatus')),
                    PurchaseDate = EI(order.get('PurchaseDate',)),
                    BuyerEmail = EI(order.get('BuyerEmail')),
                    BuyerName  = name,
                    PaymentMethod = EI(order.get('PaymentMethod')),
                    FulfillmentChannel =  EI(order.get('FulfillmentChannel')),
                    ShippingAddress = addr,
                    AmazonOrderId =AmazonOrderId ,
                    OrderTotal = order.get('OrderTotal',{}),
                )
                response[AmazonOrderId]=data
            return response

    def wk_list_orders(self,**kwrgs):
        nextToken = None
        response = self._wk_list_orders(**kwrgs)
        orders=[]
        encoding=False

        res_data = response.get('data',{})
        if res_data:
            encoding = res_data.response.encoding
            res_data = res_data.parsed
            orders = res_data.get('Orders',{}).get('Order',{})
            nextToken = res_data.get('NextToken',{}).get('value')
        order_data=self.process_order_data(orders, encoding)
        return dict(
            nextToken=nextToken,
            data=order_data,
            message=response.get('message','')
        )

    def wk_order_by_ids(self,order_ids):
        orders=[]
        encoding=False
        message=''
        for item in chunks(list(set(order_ids)),50):
            res= self._wk_order_by_ids(item)
            res_data=res.get('data',{})
            if res_data:
                encoding = res_data.response.encoding
                res_data = res_data.parsed
                response = res_data.get('Orders',{}).get('Order',{})
                if type(response)!=list:orders+=[response]
                if type(response)==list:orders+=response
            else:
                message+=res.get('message','')
        order_data=self.process_order_data(orders, encoding)
        return dict(
            data=order_data,
            message=message
        )

    @api.model
    def _wk_fetch_orders(self, channel_id,order_ids=None, nextToken=None):
        order_data=[]
        message=''
        if  order_ids:
            order_ids = list(set(order_ids.split(',')))
            res = self.wk_order_by_ids(order_ids)
            order_data =res.get('data')
            message += res.get('message','')

        else:
            kwrgs = {}
            kwrgs.update({
                'channel_id':channel_id,
                'nextToken':nextToken,
            })
            res = self.wk_list_orders(**kwrgs)
            order_data =res.get('data')
            message += res.get('message','')
        return dict(
            nextToken=res.get('nextToken'),
            data=order_data,
            message=message
            )

    def import_products(self,sku_keys):

        message='For order product imported %s'%(sku_keys)
        mapping_obj = self.env['channel.product.mappings']
        domain = [('default_code', 'in',sku_keys)]
        channel_id = self.channel_id
        mapped = channel_id._match_mapping(mapping_obj,domain).mapped('default_code')
        sku_keys=list(set(sku_keys)-set(mapped))
        message=''
        if len(sku_keys):
            report_id = self.report_id
            if not report_id:
                report_status = channel_id.mws_ensure_report()
                report_id = report_status.get('report_id')
            try:
                import_product_obj=self.env['import.mws.products']
                vals =dict(
                    report_id=report_id.id,
                    source='product_ids',
                    product_ids=','.join(sku_keys),
                    operation='import',
                    channel_id = channel_id.id
                )
                import_product_id=import_product_obj.create(vals)
                import_product_id.import_now()
            except Exception as e:
                message = "Error while  order product import %s"%(e)
        return message

    def update_shipping_info(self,order_items,order_data,price):
        ASIN =order_data.get('FulfillmentChannel','')
        name = 'Amazon%s'%(ASIN)
        order_items[ASIN] = dict(
            QuantityOrdered = 1,
            ASIN =ASIN,
            Title = name,
            ISDelivery =True,
            ItemPrice='%s'%(price),
        )
        return order_items

    def update_discount_info(self,order_items,price):
        order_items["discount"] = dict(
            QuantityOrdered = 1,
            Title = 'AmazonDiscount',
            ISDiscount =True,
            ItemPrice='%s'%(price),
        )
        return order_items

    def mws_get_tax_line(self,itemtax,channel_id,qty_ordered=1):
        tax_amt = float(itemtax)
        tax_type = 'fixed'
        # channel_data = channel_id.read(['channel'])[0]#Added
        # name = channel_data.get("channel")+"_"+str(channel_data.get('id'))+"_"+str(tax_percent)#Added
        new_rate = tax_amt/qty_ordered
        name = 'Tax-{}'.format(new_rate)
        return {
            'rate':new_rate,
            'name':name,
            'tax_type':tax_type,
            'include_in_price': False #Added
        }

    def get_order_line_feeds(self,order_id,order_data,channel_id):
        data=dict()
        res_data = self.wk_list_order_items(order_id)

        order_items=res_data.get('data')
        message=res_data.get('message','')
        lines=[]
        if order_items:
            message+=self.import_products(sku_keys=list(order_items))
            sipping_price=sum(map(lambda item:float(
                item.get('ShippingPrice','0.0') or '0.0'),
                order_items.values()))
            discount_price=sum(map(lambda item:float(
                item.get('ShippingDiscount','0.0') or '0.0'),
                order_items.values()))
            if sipping_price:
                order_items= self.update_shipping_info(
                    order_items,order_data,sipping_price
                )
            if discount_price:
                order_items= self.update_discount_info(
                    order_items,discount_price
                )
            size = len(order_items)
            if size==1:
                sku,order_item = list(order_items.items())[0]
                item_price = order_item.get('ItemPrice')
                qty_ordered = float(order_item.get('QuantityOrdered', '1')) or 1 # Added This to handle cancel order
                line=dict(
                    line_product_uom_qty = order_item.get('QuantityOrdered'),
                    line_product_id = order_item.get('ASIN'),
                    line_variant_ids = 'No Variants',
                    line_product_default_code = sku,
                    line_name = order_item.get('Title'),
                    # line_price_unit=order_item.get('ItemPrice')
                    line_price_unit = float(item_price if item_price else 0 )/qty_ordered,
                )
                item_tax = '0.0' if order_item.get('ItemTax','0.0') in [None] else order_item.get('ItemTax','0.0').strip()
                # if float(item_tax): #Removed check
                line['line_taxes'] = [self.mws_get_tax_line(item_tax,channel_id,qty_ordered)]
                data.update(line)

            else:
                for sku,order_item in order_items.items():
                    item_price = order_item.get('ItemPrice')
                    qty_ordered = float(order_item.get('QuantityOrdered', '1')) or 1 # Added This to handle cancel order

                    line=dict(
                        line_product_uom_qty = order_item.get('QuantityOrdered'),
                        line_product_id =order_item.get('ASIN'),
                        line_variant_ids = sku,
                        line_name = order_item.get('Title'),
                        line_product_default_code = sku,
                        # line_price_unit=order_item.get('ItemPrice')
                        line_price_unit = float(item_price if item_price else 0 )/qty_ordered,
                    )
                    item_tax = '0.0' if order_item.get('ItemTax','0.0') in [None] else order_item.get('ItemTax','0.0').strip()
                    # if float(item_tax): #Removed Check
                    line['line_taxes'] = [self.mws_get_tax_line(item_tax,channel_id,qty_ordered)]
                    if order_item.get('ISDelivery'):
                        line['line_source']= 'delivery'
                    if order_item.get("ISDiscount"):
                        line['line_source']= 'discount'
                    if order_item.get("PromotionDiscountTax"):pass
                    lines += [(0, 0, line)]

            data['line_ids'] = lines
            data['line_type'] = len(lines) >1 and 'multi' or 'single'
        return dict(
            data=data,
            message=message,
            )

    def get_order_vals(self,partner_id,items, order_data):
        pricelist_id = self.channel_id.pricelist_name
        vals=dict(
            partner_id = partner_id,
            payment_method = '%s'%(order_data.get('PaymentMethod','')),
            carrier_id = '%s'%(order_data.get('FulfillmentChannel','')),
            order_state =order_data.get('OrderStatus',''),
            customer_name = order_data.get('BuyerName'),
            customer_email =partner_id,
            invoice_partner_id =partner_id,
            invoice_email =partner_id,
            currency = pricelist_id.currency_id.name,
            confirmation_date = str(date_parse(order_data.get('PurchaseDate'))).split('.')[0]

        )

        addr =  order_data.get('ShippingAddress',{})
        if addr:
            vals['invoice_name'] =EI(addr.get('Name'))
            if not vals.get('customer_name'):
                vals['customer_name'] = vals['invoice_name']
            street = EI(addr.get('AddressLine1'))
            if street:
                vals['invoice_street'] =street
                vals['invoice_street2'] =EI(addr.get('AddressLine2'))
            else:
                vals['invoice_street'] =EI(addr.get('AddressLine2'))
                vals['invoice_street2'] =EI(addr.get('AddressLine3'))

            vals['invoice_phone'] =EI(addr.get('Phone'))
            vals['invoice_city'] =EI(addr.get('City'))
            vals['invoice_zip'] =EI(addr.get('PostalCode'))
            vals['invoice_state_id'] =EI(addr.get('StateOrProvinceCode') or addr.get('StateOrRegion'))
            vals['invoice_country_id'] =EI(addr.get('CountryCode'))
        return vals

    def _update_order_feed(self,mapping,partner_id,line_items, order_data):
        vals = dict()
        order_vals = self.get_order_vals(partner_id,line_items, order_data)
        mapping.write(dict(line_ids=[(5,0,0)]))
        vals.update(line_items)
        vals.update(order_vals)
        vals['state'] =  'update'
        return mapping.write(vals)

    def _mws_create_order_feed(self,partner_id,line_items, order_data,order_id):
        feed_obj = self.env['order.feed']
        vals = self.get_order_vals(partner_id,line_items, order_data)
        vals['store_id']=order_id
        vals.update(line_items)
        return self.channel_id._create_feed(feed_obj, vals)

    def _import_order(self,partner_id,line_items, order_data):
        update =False
        feed_obj =self.env['order.feed']
        mws_order_id =  order_data.get('AmazonOrderId')
        match = self.channel_id._match_feed(
            feed_obj, [('store_id', '=',mws_order_id)],limit=1)
        if match:
            update = self._update_order_feed(match,partner_id,
                line_items, order_data)
        else:
            match= self._mws_create_order_feed(
            partner_id,line_items, order_data,mws_order_id)
        return dict(
            feed_id=match,
            update=update
        )

    def import_amazon_orders_status(self,channel_id,nextToken,store_order_ids=[]):
        message = ''
        update_ids = []
        order_state_ids = channel_id.order_state_ids
        default_order_state = order_state_ids.filtered('default_order_state')
        store_order_ids = channel_id.match_order_mappings(
            limit=None).filtered(lambda item:item.order_name.state=='draft'
            ).mapped('store_order_id')
        if not store_order_ids:
            message += 'No order mapping exits'
        else:
            res = self._wk_fetch_orders(
                channel_id=channel_id,
                order_ids =','.join(store_order_ids),
                nextToken=nextToken
            )
            orders = res.get('data')
            nextToken = res.get('nextToken')
            if not orders:
                message = res.get('message','')
                if message:
                    message+=message
                else:
                    message+='No order data received.'

            else:
                for mws_order_id , order_data in orders.items():
                    status = order_data.get('OrderStatus')
                    res = channel_id.set_order_by_status(
                        channel_id= channel_id,
                        store_id = mws_order_id,
                        status = status,
                        order_state_ids = order_state_ids,
                        default_order_state = default_order_state,
                        payment_method =order_data.get('PaymentMethod','')
                    )
                    order_match = res.get('order_match')
                    if order_match:update_ids +=[order_match]
                self._cr.commit()

        time_now = fields.Datetime.now()
        all_imported , all_updated = 1,1
        if all_updated and len(update_ids):
            channel_id.update_order_date = time_now
        if not channel_id.import_order_date:
            channel_id.import_order_date = time_now
        if not channel_id.update_order_date:
            channel_id.update_order_date = time_now
        if channel_id.debug=='enable':
            _logger.info("===%r=%r="%(update_ids,message))
        if nextToken:
            self.import_amazon_orders_status(channel_id,nextToken,store_order_ids)
        return dict(
            update_ids=update_ids,
            message = message,
        )

    def import_amazon_orders(self,channel_id,create_ids=[],update_ids=[],message='',nextToken=None):

        order_state_ids = channel_id.order_state_ids
        default_order_state = order_state_ids.filtered('default_order_state')
        feed_obj = self.env['order.feed']
        create_ids = self.env['order.feed']
        update_ids = self.env['order.feed']
        res = self._wk_fetch_orders(channel_id, nextToken=nextToken)
        orders = res.get('data')
        if not orders:
            message = res.get('message','')
            if message:
                message+=message
            else:
                message+='No order data received.'
        else:
            nextToken = res.get('nextToken')
            last_order_date = None
            for mws_order_id , order_data in orders.items():
                partner_store_id=order_data.get('BuyerEmail')
                if partner_store_id:
                    match = channel_id._match_feed(
                        feed_obj, [('store_id', '=', mws_order_id),('state','!=','error')])
                    if match:
                        res = channel_id.set_order_by_status(
                            channel_id= channel_id,
                            store_id = mws_order_id,
                            status = order_data.get('OrderStatus'),
                            order_state_ids = order_state_ids,
                            default_order_state = default_order_state,
                            payment_method =order_data.get('PaymentMethod','')
                        )
                        order_match = res.get('order_match')
                        if order_match:update_ids +=match
                    else:
                        res=self.get_order_line_feeds(mws_order_id,order_data,channel_id)
                        message+=res.get('message','')
                        line_items = res.get('data')
                        shipping_method =order_data.get('FulfillmentChannel','')
                        if shipping_method:
                            shipping_mapping_id = self.env['shipping.feed'].get_shiping_carrier_mapping(
                            channel_id, shipping_method
                            )
                            line_items['carrier_id']= shipping_mapping_id.shipping_service_id
                        if line_items:
                            if line_items.get("line_ids") or line_items.get("line_name"):
                                import_res=self._import_order(
                                    partner_store_id, line_items, order_data)
                                feed_id = import_res.get('feed_id')
                                if import_res.get('update'):
                                    update_ids+=feed_id
                                else:
                                    create_ids+=feed_id
                                if channel_id.debug=='enable':
                                    _logger.info("======Order Feed Create/Update======(%r)",(message,feed_id))
                                last_order_date = order_data.get('PurchaseDate')
                        else:
                            if channel_id.debug=='enable':
                                _logger.info("=====Order Feed Create Skipped====(%r)",message)
                            self._cr.commit()
            if self._context.get("order_import_cron") and last_order_date:
                channel_id.import_order_date = str(date_parse(last_order_date)).split('.')[0]

            if nextToken and not message:
                self.import_amazon_orders(channel_id,create_ids=create_ids,update_ids=update_ids,message=message,nextToken=nextToken)

        return dict(
            create_ids=create_ids,
            update_ids=update_ids,
        )

    def import_now(self):
        create_ids,update_ids,map_create_ids,map_update_ids=[],[],[],[]
        message=''
        channel_id = ''
        for record in self:
            channel_id = record.channel_id
            feed_res = record.import_amazon_orders(channel_id)
            # create_ids+=feed_res.get('create_ids')
            # update_ids+=feed_res.get('update_ids')
            post_res = self.post_feed_import_process(channel_id,feed_res)
            create_ids+=post_res.get('create_ids')
            update_ids+=post_res.get('update_ids')
            map_create_ids+=post_res.get('map_create_ids')
            map_update_ids+=post_res.get('map_update_ids')
            # if len(create_ids):channel_id.set_channel_date('import','order')
            # if len(update_ids):channel_id.set_channel_date('update','order')
        message+=self.env['multi.channel.sale'].get_feed_import_message(
            'order',create_ids,update_ids,map_create_ids,map_update_ids
        )
        _logger.info("Import Order===%r=%r= %r=%r"%(create_ids,update_ids,message,channel_id))
        if self._context.get("order_import_cron"):
            return {"success":True}
        return self.env['multi.channel.sale'].display_message(message)

    @api.model
    def _cron_mws_import_order(self):
        last_channel_ids = self.env.ref("amazon_odoo_bridge.last_channel_ids")
        domain = CHANNELDOMAIN + [("mws_import_ord_cron_run","=",True)]
        _logger.info("Channel Active by Toggle====(%r)====",self.env['multi.channel.sale'].search(domain))
        for channel_id in self.env['multi.channel.sale'].search(domain):
            message = ''
            _logger.info("Import Order(AMZ)=====(%r)====",channel_id)
            try:
                report_status = channel_id.mws_ensure_report()
                message+= report_status.get('message')
                report_id = report_status.get('report_id')
                if report_id:
                    obj=self.create(dict(report_id=report_id.id,channel_id=channel_id.id))
                    res = obj.with_context({"order_import_cron":1}).import_now()
                    if channel_id.debug=='enable':
                        _logger.info("message %r=import_res==="%(message))
                    if res.get("success"):
                        mws_merchant_id =  channel_id.mws_merchant_id
                        other_channel = self.env['multi.channel.sale'].search(CHANNELDOMAIN+[("mws_merchant_id",'=',mws_merchant_id),
                            ("mws_import_ord_cron_run","=",False)])
                        params_val = eval(last_channel_ids.value)

                        this_seller_channels = []
                        if not len(params_val):
                            params_val.append({
                                    mws_merchant_id:[channel_id.id]
                                })
                        else:
                            present = False
                            for el in params_val:
                                if mws_merchant_id in el:
                                    present = True
                                    el[mws_merchant_id]+=[channel_id.id]
                                    el[mws_merchant_id] = list(set(el[mws_merchant_id]))
                                    this_seller_channels = el[mws_merchant_id]
                                    break
                            if not present:
                                params_val.append({
                                        mws_merchant_id:[channel_id.id]
                                    })
                        old_other_channel = channel_id.browse(this_seller_channels)

                        if other_channel!=old_other_channel:
                            last_channel_ids.value = params_val
                            new_other_channel = other_channel - old_other_channel
                            if not new_other_channel:
                                # Reset
                                for el in params_val:
                                    if mws_merchant_id in el:
                                        el[mws_merchant_id] = [channel_id.id]
                                        break
                                last_channel_ids.value = params_val
                                new_other_channel = other_channel

                            channel_id.mws_import_ord_cron_run = False
                            new_other_channel[0].mws_import_ord_cron_run = True

            except Exception as e:
                _logger.info("Import Order Failed(AMZ)=====(%r)====(%r)",channel_id,e)
                continue


    @api.model
    def _cron_mws_import_order_status(self):
        for channel_id in self.env['multi.channel.sale'].search(CHANNELDOMAIN):
            message = ''
            import_res = None
            channel_id = channel_id
            try:
                report_status = channel_id.mws_ensure_report()
                message+= report_status.get('message')
                report_id = report_status.get('report_id')
                if report_id:
                    obj=self.create(dict(
                        report_id=report_id.id,
                        channel_id=channel_id.id)
                    )
                    import_res = obj.with_context({"order_status_cron":1}).import_amazon_orders_status(channel_id,nextToken=False)
                if channel_id.debug=='enable':
                    _logger.info("message %r=import_res==%r=="%(message,import_res))
            except Exception as e:
                _logger.info("Import Order Status Failed(AMZ)=====(%r)====(%r)",channel_id,e)
                continue
