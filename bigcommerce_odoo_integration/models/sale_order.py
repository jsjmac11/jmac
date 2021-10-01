from odoo import fields, models, api
import base64
import json
from datetime import datetime
from requests import request
import time
import binascii
from odoo.exceptions import ValidationError
import sys
from threading import Thread
import logging
_logger = logging.getLogger("BigCommerce")

class SaleOrderVts(models.Model):
    _inherit = "sale.order"

    big_commerce_order_id = fields.Char(string="BigCommerce Order ID", readonly=True,copy=False)
    bigcommerce_store_id = fields.Many2one('bigcommerce.store.configuration', string="Bigcommerce Store", copy=False)
    bigcommerce_shipment_order_status = fields.Char(string='Bigcommerce Shipment Order Status',readonly=True)

    def get_shipped_qty(self):
        bigcommerce_store_hash = self.bigcommerce_store_id.bigcommerce_store_hash
        bigcommerce_client_seceret  = self.bigcommerce_store_id.bigcommerce_x_auth_client
        bigcommerce_x_auth_token = self.bigcommerce_store_id.bigcommerce_x_auth_token
        headers = {"Accept": "application/json",
                   "X-Auth-Client": "{}".format(bigcommerce_client_seceret),
                   "X-Auth-Token": "{}".format(bigcommerce_x_auth_token),
                   "Content-Type": "application/json"}


        url = "%s%s/v2/orders/%s/products"%(self.bigcommerce_store_id.bigcommerce_api_url,bigcommerce_store_hash,self.big_commerce_order_id)
        try:
            response = request(method="GET",url=url,headers=headers)
            response = response.json()
            for response in response:
                product_ids = []
                domain = []
                bigcommerce_product_id = response.get('product_id')
                product_template_id = self.env['product.template'].search(
                    [('bigcommerce_product_id', '=', bigcommerce_product_id)])
                if response.get('product_options'):
                    for product_option in response.get('product_options'):
                        attribute_obj = self.env['product.attribute'].search([('bigcommerce_attribute_id','=',product_option.get('product_option_id'))])
                        value_obj = self.env['product.attribute.value'].search([('bigcommerce_value_id','=',int(product_option.get('value')))])
                        #attrib.append(attribute_obj.id)
                        #val_obj.append(value_obj.id)
                        template_attribute_obj = self.env['product.template.attribute.value'].search(
                            [('attribute_id', 'in', attribute_obj.ids), ('product_attribute_value_id', 'in', value_obj.ids),
                             ('product_tmpl_id', '=', product_template_id.id)])
                        #val_obj.append(template_attribute_obj)
                        domain = [('product_template_attribute_value_ids', 'in', template_attribute_obj.ids),('product_tmpl_id','=',product_template_id.id)]
                        if product_ids:
                            domain += [('id','in',product_ids)]
                        product_id = self.env['product.product'].search(domain)
                        product_ids += product_id.ids
                else:
                    product_id = self.env['product.product'].sudo().search([('product_tmpl_id','=',product_template_id.id)],limit=1)
                    #product_id = product_template_id.product_variant_id
                order_line = self.order_line.filtered(lambda line:line.product_id in product_id)
                order_line.quantity_shipped = response.get('quantity_shipped')
                self._cr.commit()
        except Exception as e:
            raise ValidationError(e)

    def create_sales_order_from_bigcommerce(self, vals):
        sale_order = self.env['sale.order']
        order_vals = {
            'company_id': vals.get('company_id'),
            'partner_id': vals.get('partner_id'),
            'partner_invoice_id': vals.get('partner_invoice_id'),
            'partner_shipping_id': vals.get('partner_shipping_id'),
            'warehouse_id': vals.get('warehouse_id'),
        }
        new_record = sale_order.new(order_vals)
        new_record.onchange_partner_id()
        order_vals = sale_order._convert_to_write({name: new_record[name] for name in new_record._cache})
        new_record = sale_order.new(order_vals)
        new_record.onchange_partner_shipping_id()
        order_vals = sale_order._convert_to_write({name: new_record[name] for name in new_record._cache})
        order_vals.update({
            'company_id': vals.get('company_id'),
            'picking_policy': 'direct',
            'partner_invoice_id': vals.get('partner_invoice_id'),
            'partner_shipping_id': vals.get('partner_shipping_id'),
            'partner_id': vals.get('partner_id'),
            'date_order': vals.get('date_order', ''),
            'state': 'draft',
            'carrier_id': vals.get('carrier_id', ''),
            'currency_id':vals.get('currency_id',False),
            'discount_type': 'amount',
        })
        return order_vals

    def create_sale_order_line_from_bigcommerce(self, vals):
        sale_order_line = self.env['sale.order.line']
        order_line = {
            'order_id': vals.get('order_id'),
            'product_id': vals.get('product_id', ''),
            'company_id': vals.get('company_id', ''),
            'name': vals.get('description'),
            'product_uom': vals.get('product_uom'),
            'product_pack_id': vals.get('product_pack_id')
        }
        new_order_line = sale_order_line.new(order_line)
        new_order_line.product_id_change()
        order_line = sale_order_line._convert_to_write({name: new_order_line[name] for name in new_order_line._cache})
        order_line.update({
            'order_id': vals.get('order_id'),
            'product_uom_qty': vals.get('order_qty', 0.0),
            'pack_quantity': vals.get('order_qty', 0.0),
            'price_unit': vals.get('price_unit', 0.0),
            'discount': vals.get('discount', 0.0),
            'state': 'draft',
        })
        return order_line

    def create_bigcommerce_operation(self, operation, operation_type, bigcommerce_store_id, log_message, warehouse_id):
        vals = {
            'bigcommerce_operation': operation,
            'bigcommerce_operation_type': operation_type,
            'bigcommerce_store': bigcommerce_store_id and bigcommerce_store_id.id,
            'bigcommerce_message': log_message,
            'warehouse_id': warehouse_id and warehouse_id.id or False
        }
        operation_id = self.env['bigcommerce.operation'].create(vals)
        return operation_id

    def create_bigcommerce_operation_detail(self, operation, operation_type, req_data, response_data, operation_id,
                                            warehouse_id=False, fault_operation=False, process_message=False):
        bigcommerce_operation_details_obj = self.env['bigcommerce.operation.details']
        vals = {
            'bigcommerce_operation': operation,
            'bigcommerce_operation_type': operation_type,
            'bigcommerce_request_message': '{}'.format(req_data),
            'bigcommerce_response_message': '{}'.format(response_data),
            'operation_id': operation_id.id,
            'warehouse_id': warehouse_id and warehouse_id.id or False,
            'fault_operation': fault_operation,
            'process_message': process_message,
        }
        operation_detail_id = bigcommerce_operation_details_obj.create(vals)
        return operation_detail_id

    def bigcommerce_to_odoo_import_orders(self,warehouse_id=False, bigcommerce_store_ids=False):
        for bigcommerce_store_id in bigcommerce_store_ids:
            req_data = False
            process_message = "Process Completed Successfully!"
            operation_id = self.create_bigcommerce_operation('order', 'import',bigcommerce_store_id, 'Processing...',warehouse_id)
            self._cr.commit()
            order_response_pages = []
            try:
                today_date = datetime.now()
                todaydate = today_date.strftime("%Y-%m-%d")
                todaytime = today_date.strftime("%H:%M:%S")
                today_date = todaydate + " " + todaytime
                last_modification_date = False
                if bigcommerce_store_id.last_modification_date :
                    last_modification_date = bigcommerce_store_id.last_modification_date
                    date = last_modification_date.strftime("%Y-%m-%d")
                    time = last_modification_date.strftime("%H:%M:%S")
                    #last_modification_date = date + "T" + time
                    last_modification_date = date +" "+ time

                api_operation = "/v2/orders?max_date_created={0}&min_date_created={1}&status_id={2}".format(today_date,last_modification_date if last_modification_date else today_date,bigcommerce_store_id.bigcommerce_order_status or '11')
                response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(api_operation)
                if response_data.status_code in [200, 201]:
                    response_data = response_data.json()
                    _logger.info("Category Response Data : {0}".format(response_data))
                    late_modification_date_flag = False

                    # total_pages = response_data.get('meta') and response_data.get('meta').get('pagination').get('total_pages')
                    # if total_pages > 1:
                    #     while (total_pages != 0):
                    #         try:
                    #             page_api = "/v2/orders?max_date_created={0}&min_date_created={1}&status_id={2}&page={2}".format(
                    #             today_date, last_modification_date if last_modification_date else today_date, bigcommerce_store_id.bigcommerce_order_status or '11',total_pages)
                    #             page_response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(
                    #                 page_api)
                    #             _logger.info(
                    #                 "BigCommerce Get Order Response : {0}".format(page_response_data))
                    #             _logger.info("Response Status: {0}".format(page_response_data.status_code))
                    #             if page_response_data.status_code in [200, 201]:
                    #                 page_response_data = page_response_data.json()
                    #                 _logger.info("Order Response Data : {0}".format(page_response_data))
                    #                 order_response_pages.append(page_response_data)
                    #         except Exception as e:
                    #             _logger.info("Getting an Error In Import Order Response {}".format(e))
                    #             process_message = "Getting an Error In Import Order Response {}".format(e)
                    #             self.create_bigcommerce_operation_detail('order', 'import', '', '', operation_id,
                    #                                                      warehouse_id, True, process_message)
                    #         total_pages = total_pages - 1
                    # else:
                    #     order_response_pages.append(response_data)
                    #
                    # for order_response_page in order_response_pages:
                    for order in response_data:
                        big_commerce_order_id = order.get('id')
                        sale_order = self.env['sale.order'].search([('big_commerce_order_id', '=', big_commerce_order_id)])
                        if not sale_order:
                            date_time_str = order.get('orderDate')
                            customerEmail = order.get('billing_address').get('email')

                            city = order.get('billing_address').get('city')
                            first_name = order.get('billing_address').get('first_name')
                            last_name = order.get('billing_address').get('last_name')
                            country_iso2 = order.get('billing_address').get('country_iso2')
                            street = order.get('billing_address').get('street_1','')
                            street_2 = order.get('billing_address').get('street_2','')
                            country_obj = self.env['res.country'].search(
                                [('code', '=', country_iso2)], limit=1)

                            phone = order.get('billing_address').get('phone')
                            zip = order.get('billing_address').get('zip')

                            total_tax= order.get('total_tax')
                            customerId = order.get('customer_id')
                            carrier_id  = self.env['delivery.carrier'].search([('is_bigcommerce_shipping_method','=',True)],limit=1)
                            partner_obj = self.env['res.partner'].search([('bigcommerce_customer_id', '=', customerId)], limit=1)
                            partner_state = order.get('billing_address').get('state')
                            state_id = self.env['res.country.state'].search([('name', '=', partner_state)],
                                                                            limit=1)
                            partner_vals = {
                                    'phone': phone,
                                    'zip':zip,
                                    'city':city,
                                    'country_id':country_obj and country_obj.id,
                                    'email': customerEmail,
                                    'is_available_in_bigcommerce': True,
                                    'bigcommerce_store_id': bigcommerce_store_id.id,
                                    'street':street,
                                    'street2':street_2,
                                    'state_id': state_id and state_id.id
                                }
                            if customerId==0:
                                partner_vals.update({
                                    'name': "%s %s (Guest)" % (first_name, last_name),
                                    'bigcommerce_customer_id': "Guest User",
                                })
                                partner_obj = self.env['res.partner'].create(partner_vals)
                                user_id =  self.env['res.users'].search([('partner_id', '=', partner_obj.id)])
                                if not user_id:
                                    x_group_portal_user = self.env.ref('base.group_portal')
                                    self.env['res.users'].create([{'name': partner_obj.name,
                                                              'login': partner_obj.email,
                                                              'partner_id': partner_obj.id,
                                                              'groups_id': [(6, 0, [x_group_portal_user.id])],
                                                              }],) 
                            if not partner_obj:
                                partner_vals.update({
                                    'name': "%s %s" % (first_name, last_name),
                                    'bigcommerce_customer_id':customerId,
                                })
                                partner_obj = self.env['res.partner'].create(partner_vals)
                                user_id =  self.env['res.users'].search([('partner_id', '=', partner_obj.id)])
                                if not user_id:
                                    x_group_portal_user = self.env.ref('base.group_portal')
                                    k = self.env['res.users'].create([{'name': partner_obj.name,
                                                              'login': partner_obj.email,
                                                              'partner_id': partner_obj.id,
                                                              'groups_id': [(6, 0, [x_group_portal_user.id])],
                                                              }],) 
                                    
                            if not partner_obj:
                                process_message = "Customer is not exist in Odoo {}".format(customerId)
                                self.create_bigcommerce_operation_detail('order', 'import', req_data, response_data,
                                                                         operation_id, warehouse_id, True,
                                                                         process_message)
                                late_modification_date_flag=True
                                continue
                            shipping_partner_state = order.get('billing_address').get('state')
                            shipping_partner_country = order.get('billing_address').get('country')
                            state_id = self.env['res.country.state'].search([('name', '=', shipping_partner_state)],
                                                                            limit=1)
                            country_id = self.env['res.country'].search([('name', '=', shipping_partner_country)],
                                                                        limit=1)
                            vals = {
                                'name': order.get('billing_address').get('first_name'),
                                'street': order.get('billing_address').get('street_1'),
                                'street2': order.get('billing_address').get('street_2'),
                                'city': order.get('billing_address').get('city'),
                                'state_id': state_id and state_id.id or False,
                                'country_id': country_id and country_id.id or False,
                                'phone': order.get('billing_address').get('phone'),
                                'zip': order.get('billing_address').get('zip'),
                                'type': 'delivery',
                                'parent_id': partner_obj.id
                            }
                            base_shipping_cost = order.get('base_shipping_cost', 0.0)
                            currency_id = self.env['res.currency'].search([('name','=',order.get('currency_code'))],limit=1)
                            vals.update({'partner_id': partner_obj.id,
                                         'partner_invoice_id': partner_obj.id,
                                         'partner_shipping_id': partner_obj.id,
                                         'date_order': date_time_str or today_date,
                                         'carrier_id': carrier_id and carrier_id.id,
                                         'company_id': warehouse_id.company_id and warehouse_id.company_id.id or self.env.user.company_id.id,
                                         'warehouse_id': warehouse_id.id,
                                         'carrierCode': '',
                                         'serviceCode': '',
                                         'delivery_price': base_shipping_cost,
                                         'amount_tax':total_tax,
                                         'currency_id':currency_id.id
                                        })
                            order_vals = self.create_sales_order_from_bigcommerce(vals)
                            order_vals.update({'big_commerce_order_id': big_commerce_order_id,
                                               'bigcommerce_store_id': bigcommerce_store_id.id})
                            try:
                                order_id = self.create(order_vals)
                                if carrier_id and order_id:
                                    order_id.set_delivery_line(carrier_id, base_shipping_cost)
                                if order_id:
                                    order_id.action_quotation_sent()
                                    order_id.write({'state': 'draft'})
                                # discount_product_id = self.env.ref('bigcommerce_odoo_integration.product_product_bigcommerce_discount')
                                # if float(order.get('discount_amount')):
                                #     self.env['sale.order.line'].sudo().create({'product_id':discount_product_id.id,'price_unit':-float(order.get('discount_amount')),'product_uom_qty':1.0,'state': 'draft','order_id':order_id.id,'company_id':order_id.company_id.id})
                            except Exception as e:
                                process_message = "Getting an Error In Create Order procecss {}".format(e)
                                self.create_bigcommerce_operation_detail('order', 'import', '', '', operation_id,
                                                                         warehouse_id, True, process_message)
                                late_modification_date_flag = True
                                continue
                            process_message = "Sale Order Created {0}".format(order_id and order_id.name)
                            _logger.info("Sale Order Created {0}".format(order_id and order_id.name))
                            order_id.message_post(body="Order Successfully Import From Bigcommerce")
                            self.create_bigcommerce_operation_detail('order', 'import', req_data, response_data,
                                                                     operation_id, warehouse_id, False,
                                                                     process_message)
                            try:
                                product_details = "/v2{0}".format(order.get('products').get('resource'))
                                response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(product_details)
                                if response_data.status_code in [200, 201, 204]:
                                    response_data = response_data.json()
                                    if response_data and order_id:
                                        self.prepare_sale_order_lines(order_id,response_data,operation_id,warehouse_id)
                                    else:
                                        product_message="Product Is not available in order : {0}!".format(order_id and order_id.name)
                                        self.create_bigcommerce_operation_detail('order', 'import', req_data, response_data,
                                                                                 operation_id, warehouse_id, True,
                                                                                 product_message)
                            except Exception as e:
                                _logger.info("Getting an Error In Import Order Line Response {}".format(e))
                                process_message = "Getting an Error In Import Order Response {}".format(e,order_id and order_id.name)
                                self.create_bigcommerce_operation_detail('order', 'import', '', '', operation_id,
                                                                         warehouse_id, True, process_message)
                        else:
                            process_message = "Order Already in Odoo {}".format(sale_order and sale_order.name)
                            self.create_bigcommerce_operation_detail('order', 'import', req_data, response_data,
                                                                     operation_id, warehouse_id, True,
                                                                     process_message)
                            self._cr.commit()
                    if not late_modification_date_flag:
                        current_date = datetime.now()
                        bigcommerce_store_id.last_modification_date=current_date
                else:
                    _logger.info("Getting an Error In Import Orders Response {}".format(response_data))
                    response_data=response_data.content
                    process_message="Getting an Error In Import Orders Response".format(response_data)
                    self.create_bigcommerce_operation_detail('order','import',req_data,response_data,operation_id,warehouse_id,True,process_message)
            except Exception as e:
                _logger.info("Getting an Error In Import Order Response {}".format(e))
                process_message="Getting an Error In Import Order Response {}".format(e)
                self.create_bigcommerce_operation_detail('order','import','','',operation_id,warehouse_id,True,process_message)
            operation_id and operation_id.write({'bigcommerce_message': process_message})
            bigcommerce_store_ids.bigcommerce_operation_message = " Import Sale Order Process Complete "
            self._cr.commit()
    
    def prepare_sale_order_lines(self,order_id=False,product_details=False,operation_id=False,warehouse_id=False):
        for order_line in product_details:
            product_bigcommerce_id = order_line.get('product_id')
            product_id = self.env['product.product'].search([('bigcommerce_product_id', '=', product_bigcommerce_id)],
                                                            limit=1)

            if product_id.bigcommerce_product_variant_id:
                product_id = self.env['product.product'].search([('bigcommerce_product_variant_id', '=', order_line.get('variant_id'))],
                                                            limit=1)

            if not product_id:
                response_msg = "Sale Order : {0} Prouduct Not Found Product SKU And Name : {1}".format(order_id and order_id.name, product_bigcommerce_id)
                self.create_bigcommerce_operation_detail('order','import','','',operation_id,warehouse_id,True,response_msg)
                continue
            quantity = order_line.get('quantity')
            price = order_line.get('base_price')
            total_tax = order_line.get('total_tax')
            # pack_product_id = product_id.product_pack_line.filtered(lambda p: p.is_auto_created)
            pack_product_id = self.env['product.pack.uom'].search([('product_tmpl_id', '=', product_id.product_tmpl_id.id), ('is_auto_created', '=', True)], limit=1)
            if not pack_product_id:
                pack_auto_line = {
                     'quantity': 1.0,
                     'is_auto_created': True}
                pack_product_id = self.env['pack.product.uom'].create(pack_auto_line)
            vals = {'product_id': product_id.id, 'price_unit': price, 'order_qty': quantity,
                    'order_id': order_id and order_id.id, 'description': product_bigcommerce_id,
                    'company_id': self.env.user.company_id.id,
                    'big_commerce_tax': total_tax,
                    'product_pack_id': pack_product_id.id}
            if order_line.get('applied_discounts'):
                discount_amt = sum([float(disc.get('amount')) for disc in order_line.get('applied_discounts')])
                discount_per = (discount_amt * 100) / float(price)
                vals.update({'discount': discount_per})
            order_line = self.create_sale_order_line_from_bigcommerce(vals)
            order_line = self.env['sale.order.line'].create(order_line)
            if order_line:
                order_line.big_commerce_tax=total_tax
            _logger.info("Sale Order line Created".format(
                order_line and order_line.product_id and order_line.product_id.name))
            response_msg = "Sale Order line Created For Order  : {0}".format(order_id.name)
            self.create_bigcommerce_operation_detail('order','import','','',operation_id,warehouse_id,False,response_msg)
        self._cr.commit()

    def exportordertobigcommerce(self):
        """
        This Method Is Used Export Order To BigCommerce
        :return: If Successfully Export Return OrderId
        """
        if not self.bigcommerce_store_id:
            raise ValidationError("Please Select Bigcommerce Store")
        bigcommerce_store_hash = self.bigcommerce_store_id.bigcommerce_store_hash
        api_url = "%s%s/v2/orders"%(self.bigcommerce_store_id.bigcommerce_api_url,bigcommerce_store_hash)
        bigcommerce_auth_token = self.bigcommerce_store_id.bigcommerce_x_auth_token
        bigcommerce_auth_client = self.bigcommerce_store_id.bigcommerce_x_auth_client

        headers ={ 'Accept'       : 'application/json',
                   'Content-Type' : 'application/json',
                   'X-Auth-Token' : "{}".format(bigcommerce_auth_token),
                   'X-Auth-Client':  "{}".format(bigcommerce_auth_client) }
        ls = []
        #  attribute_id = self.order_line.product_id.attribute_line_ids.attribute_id.bigcommerce_attribute_id
        for line in self.order_line:
            # variant_combination_ids = self.env['product.variant.combination'].search(
            #     [('product_product_id', '=', line.product_id.id)]).mapped('product_template_attribute_value_id')
            product_option = []
            if line.product_id.bigcommerce_product_variant_id and line.product_id.product_template_attribute_value_ids:
                #self._cr.execute("select product_template_attribute_value_id from product_variant_combination where product_product_id={}".format(line.product_id.id))
                #res = self._cr.fetchall()
                attribute_ids = line.product_id.product_template_attribute_value_ids
                for attribute in attribute_ids:
                    attribute_value_id = attribute.product_attribute_value_id.bigcommerce_value_id
                    attribute_id = attribute.attribute_id.bigcommerce_attribute_id
                    product_option.append({'id':attribute_id,"value":str(attribute_value_id)})
            data = {
                "product_id": line.product_id.bigcommerce_product_id,
                "quantity": line.product_uom_qty,
                "price_inc_tax" : line.price_total,
                "price_ex_tax": line.price_subtotal,
                "product_options" : product_option
            }
            ls.append(data)

        request_data= {
            'status_id' : 1,
            'billing_address' :{
                "first_name" : "{}".format(self.partner_id and self.partner_id.name),
                "street_1" : "{}".format(self.partner_id and self.partner_id.street),
                "city" :"{}".format(self.partner_id and self.partner_id.city),
                "state": "{}".format(self.partner_id and self.partner_id.state_id.name),
                "zip" : "{}".format(self.partner_id and self.partner_id.zip),
                "country": "{}".format(self.partner_id and self.partner_id.country_id.name),
                "email" :"{}".format(self.partner_id and self.partner_id.email) },
            'products': ls }
        operation_id = self.create_bigcommerce_operation('order', 'export', self.bigcommerce_store_id, 'Processing...',
                                                         self.warehouse_id)
        self._cr.commit()
        try:
            response = request(method="POST",url=api_url,data=json.dumps(request_data),headers=headers)
            _logger.info("Sending Post Request To {}".format(api_url))
            response_data = response.json()
            req_data = False
            process_message = "Successfully Export Product {}".format(response_data)
            self.create_bigcommerce_operation_detail('order', 'export', req_data, response_data,
                                                     operation_id, self.warehouse_id, False,
                                                     process_message)
        except Exception as e:
            _logger.info("Export Order Response {}".format(response.content))
            raise ValidationError(e)
        if response.status_code not in [200,201]:
            raise ValidationError("Getting Some Error {}".format(response.content))
            process_message = "Getting Some Error {}".format(response.content)
            self.create_bigcommerce_operation_detail('order', 'export', req_data, response_data,
                                                     operation_id, self.warehouse_id, False,
                                                     process_message)
        response_data = response.json()
        if not response_data.get('id'):
            raise ValidationError("Order Id Not Found In Response")
            self.create_bigcommerce_operation_detail('order', 'export', req_data, response_data,
                                                     operation_id, self.warehouse_id, False,
                                                     process_message)
        self.big_commerce_order_id = response_data.get('id')
        self.message_post(body="Successfully Order Export To odoo")
        process_message = "Order Id Not Found"

        return {
            'effect': {
                'fadeout': 'slow',
                'message': "Yeah! Successfully Export Order .",
                'img_url': '/web/static/src/img/smile.svg',
                'type': 'rainbow_man',
            }
        }

class SaleOrderLineVts(models.Model):
    _inherit = "sale.order.line"

    quantity_shipped = fields.Float(string='Shipped Products',copy=False)
    #x_studio_manufacturer = fields.Many2one('bc.product.brand',string='Manufacturer')
    big_commerce_tax = fields.Float(string="BigCommerce Tax", copy=False)

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty,
                                            product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])) if not line.order_id and line.order_id.big_commerce_order_id else line.big_commerce_tax,
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })
