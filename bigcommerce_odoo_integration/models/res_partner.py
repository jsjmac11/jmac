from odoo import fields, models, api
from odoo.exceptions import ValidationError
from requests import request
import requests
import json
import logging
_logger = logging.getLogger("BigCommerce")


class ResPartner(models.Model):
    _inherit = "res.partner"

    bigcommerce_store_id = fields.Many2one('bigcommerce.store.configuration',string="Bigcommerce Store",copy=False, track_visibility='onchange')
    bigcommerce_customer_id = fields.Char("Bigcommerce Customer ID", copy=False)
    is_available_in_bigcommerce = fields.Boolean(string='Is Exported to BigCommerce',default=False)
    bigcommerce_shipping_address_id = fields.Char("Bigcommerce Shipping Address ID", copy=False)

    def create_bigcommerce_operation(self,operation,operation_type,bigcommerce_store_id,log_message,warehouse_id):
        vals = {
                    'bigcommerce_operation': operation,
                   'bigcommerce_operation_type': operation_type,
                   'bigcommerce_store': bigcommerce_store_id and bigcommerce_store_id.id,
                   'bigcommerce_message': log_message,
                   'warehouse_id': warehouse_id and warehouse_id.id or False
                   }
        operation_id = self.env['bigcommerce.operation'].create(vals)
        return  operation_id

    def create_bigcommerce_operation_detail(self,operation,operation_type,req_data,response_data,operation_id,warehouse_id=False,fault_operation=False,customer_message=False):
        bigcommerce_operation_details_obj = self.env['bigcommerce.operation.details']
        vals = {
                    'bigcommerce_operation': operation,
                   'bigcommerce_operation_type': operation_type,
                   'bigcommerce_request_message': '{}'.format(req_data),
                   'bigcommerce_response_message': '{}'.format(response_data),
                   'operation_id':operation_id.id,
                   'warehouse_id': warehouse_id and warehouse_id.id or False,
                   'fault_operation':fault_operation,
                   'process_message':customer_message
                   }
        operation_detail_id = bigcommerce_operation_details_obj.create(vals)
        return operation_detail_id

    def customer_request_data(self, partner_id):
        partner_name = partner_id.name
        name_list = partner_name.split(" ")
        if name_list:
            first_name = name_list[0]
            last_name = name_list[-1]
        else:
            first_name = partner_id.name
            last_name = ""
        return  {
            "email": partner_id.email or "",
            "first_name": first_name or "",
            "last_name": last_name or "",
            "phone": partner_id.phone or "",
        }

    def customer_address_request_data(self, partner_id):
        country_name = partner_id.country_id.name
        country_obj = self.env['res.country'].search(
                [('name', '=', country_name)], limit=1)
        country_id = country_obj and country_obj.id
        state_code = partner_id.state_id.code
        state_obj = self.env['res.country.state'].search([('code', '=', state_code)], limit=1)
        state_id = state_obj and state_obj.id
        partner_name = partner_id.parent_id.name
        name_list = partner_name.split(" ")
        if name_list:
            first_name = name_list[0]
            last_name = name_list[-1]
        else:
            first_name = partner_id.name
            last_name = ""

        return  {
            "first_name": first_name or "",
            "last_name": last_name or "",
            "company": partner_id.company_id.name or "",
            "street_1": partner_id.street or "",
            "street_2": partner_id.street2 or "",
            "zip": partner_id.zip or "",
            "city": partner_id.city or "",
            "country": "United States" or "",
            "state": partner_id.state_id and partner_id.state_id.name or "",
            "phone": partner_id.phone,
            "address_type": "commercial"
        }

    # EXPORT CUSTOMER MANUALLY
    def odoo_to_bigcommerce_export_customer_manually(self):
        if self._context.get('active_model') == 'res.partner':
            partner_ids = self.env.context.get('active_ids')
            partner_objs = self.env['res.partner'].browse(partner_ids)
            self.odoo_to_bigcommerce_export_customers(bigcommerce_store_ids= partner_objs.bigcommerce_store_id,new_partner_id=partner_objs)
        return

    def bigcommerce_to_odoo_import_customers(self,warehouse_id=False, bigcommerce_store_ids=False):
        for bigcommerce_store_id in bigcommerce_store_ids:
            req_data = False
            customer_response_pages=[]
            customer_process_message = "Process Completed Successfully!"
            category_operation_id = self.env['bigcommerce.operation']
            if not category_operation_id:
                category_operation_id = self.create_bigcommerce_operation('customer','import',bigcommerce_store_id,'Processing...',warehouse_id)
            self._cr.commit()
            try:
                api_operation = "/v3/customers"
                response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(api_operation)
                _logger.info("BigCommerce Get Customer Response : {0}".format(response_data))
                _logger.info("Response Status: {0}".format(response_data.status_code))
                if response_data.status_code in [200, 201]:
                    response_data = response_data.json()
                    _logger.info("Customer Response Data : {0}".format(response_data))
                    records = response_data.get('data')

                    total_pages = response_data.get('meta').get('pagination').get('total_pages')
                    if total_pages > 1:
                        while (total_pages != 0):
                            try:
                                page_api = "/v3/customers?page=%s"%(total_pages)
                                page_response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(
                                    page_api)
                                _logger.info("BigCommerce Get Customer Response : {0}".format(page_response_data))
                                _logger.info("Response Status: {0}".format(page_response_data.status_code))
                                if page_response_data.status_code in [200, 201]:
                                    page_response_data = page_response_data.json()
                                    _logger.info("Customer Response Data : {0}".format(page_response_data))
                                    page_records = page_response_data.get('data')
                                    customer_response_pages.append(page_records)
                            except Exception as e:
                                category_process_message = "Page is not imported! %s" % (e)
                                _logger.info("Getting an Error In Customer Response {}".format(e))
                                process_message = "Getting an Error In Import Customer Response {}".format(e)
                                self.create_bigcommerce_operation_detail('customer', 'import', page_response_data,
                                                                         category_process_message,
                                                                         category_operation_id, warehouse_id, True,
                                                                         process_message)
                            total_pages = total_pages - 1

                    else:
                        customer_response_pages.append(records)

                    for customer_response_page in customer_response_pages:
                        for record in customer_response_page:
                            customer_id = self.env['res.partner'].search(
                                ['|', ('bigcommerce_customer_id','=',record.get('id')),
                                 ('email','=', record.get('email')),],limit=1)
                            if not customer_id:
                                partner_vals = {
                                    'name': "%s %s" % (record.get('first_name'),record.get('last_name')),
                                    'phone': record.get('phone', ''),
                                    'email': record.get('email'),
                                    'bigcommerce_customer_id':record.get('id',False),
                                    'is_available_in_bigcommerce':True,
                                    'bigcommerce_store_id':bigcommerce_store_id.id
                                }
                                customer_id = self.env['res.partner'].create(partner_vals)
                                _logger.info("Customer Created : {0}".format(customer_id.name))
                                response_data = record
                                customer_message="%s Customer Created"%(customer_id.name)
                            else:
                                vals = {
                                    'name': "%s %s" % (record.get('first_name'),record.get('last_name')),
                                    'phone': record.get('phone', ''),
                                    'email': record.get('email'),
                                    # 'bigcommerce_customer_id':record.get('id'),
                                    # 'bigcommerce_store_id':bigcommerce_store_id.id
                                    }
                                if customer_id and not customer_id.bigcommerce_customer_id:
                                    vals.update({'bigcommerce_customer_id': record.get('id'),
                                         'bigcommerce_store_id': bigcommerce_store_id.id})
                                customer_id.write(vals)
                                customer_message="Customer Data Updated %s"%(customer_id.name)
                                _logger.info("Product Category Updated : {0}".format(customer_id.name))
                                req_data = record
                            self.create_bigcommerce_operation_detail('customer','import',req_data,response_data,category_operation_id,warehouse_id,False,customer_message)
                            self._cr.commit()
                            try :
                                self.add_customer_address(customer_id,bigcommerce_store_id,category_operation_id,warehouse_id)
                            except Exception as e:
                                continue
                    _logger.info("Import Customer Process Completed ")
                else:
                    _logger.info("Getting an Error In Import Customer Response".format(response_data))
                    customer_res_message=response_data.content
                    customer_message="Getting an Error In Import Customer Response".format(customer_res_message)
                    self.create_bigcommerce_operation_detail('customer','import',req_data,customer_res_message,category_operation_id,warehouse_id,True,customer_message)
            except Exception as e:
                customer_process_message = "Process Is Not Completed Yet! %s" % (e)
                _logger.info("Getting an Error In Import Customer Responase".format(e))
                customer_message="Getting an Error In Import Customer Responase : {0}".format(e)
                self.create_bigcommerce_operation_detail('customer','import',response_data,customer_process_message,category_operation_id,warehouse_id,True,customer_message)
            category_operation_id and category_operation_id.write({'bigcommerce_message': customer_process_message})
            bigcommerce_store_id.bigcommerce_operation_message = "Import Customer Process Completed."
            self._cr.commit()

    def add_customer_address(self,customer_id=False,bigcommerce_store_id=False,category_operation_id=False,warehouse_id=False):
        req_data = False
        customer_process_message = "Process Completed Successfully!"
        if customer_id and customer_id.bigcommerce_customer_id:
            try:
                api_operation = "/v2/customers/%s/addresses"%(customer_id.bigcommerce_customer_id)
                response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(api_operation)
                _logger.info("BigCommerce Get Customer Address Response : {0}".format(response_data))
                _logger.info("Response Status: {0}".format(response_data.status_code))

                if response_data.status_code in [200, 201,204]:
                    response_data = response_data.json()
                    _logger.info("Customer Response Data : {0}".format(response_data))
                    for record in response_data:
                        # CREATE MULTIPLE DELIVERY ADDRESS
                        if record['id']:
                            is_exist = self.env['res.partner'].search([('bigcommerce_shipping_address_id', '=', record['id']), ('parent_id.bigcommerce_customer_id', '=', record['customer_id'])],  limit=1)
                            customer_id = self.env['res.partner'].search([('bigcommerce_customer_id', '=', record['customer_id'])],  limit=1)
                            if not is_exist:
                                country_code = record.get("country_iso2","")
                                state_name = record.get('state',"")
                                country_obj = self.env['res.country'].search(
                                        [('code', '=', country_code)], limit=1)
                                state_obj = self.env['res.country.state'].search([('name', '=', state_name)], limit=1)
                                vals = {
                                    'type': 'delivery',
                                    'bigcommerce_shipping_address_id': record.get("id"),
                                    'street': record.get('street_1',""),
                                    'street2': record.get('street_2',""),
                                    'zip': record.get('zip',""),
                                    'city': record.get('city',""),
                                    'country_id': 233,
                                    'state_id': state_obj and state_obj.id,
                                    'parent_id': customer_id.id
                                }
                                shipping_record = self.env['res.partner'].create(vals)
                        customer_id.street=record.get('street_1',"")
                        customer_id.street1=record.get("street_2","")
                        customer_id.zip=record.get('zip',"")
                        customer_id.city = record.get('city', "")
                        country_code=record.get("country_iso2","")
                        country_obj = self.env['res.country'].search(
                            [('code', '=', country_code)], limit=1)
                        customer_id.country_id=country_obj and country_obj.id
                        state_name=record.get('state',"")
                        state_obj = self.env['res.country.state'].search([('name', '=', state_name)], limit=1)
                        customer_id.state_id=state_obj and state_obj.id
                        _logger.info("Customer Address Updated : {0}".format(customer_id.name))
                        response_data = record
                        customer_message="%s Customer Address Updated"%(customer_id.name)
                        self.create_bigcommerce_operation_detail('customer','import',req_data,response_data,category_operation_id,warehouse_id,False,customer_message)
                        self._cr.commit()
                    category_operation_id and category_operation_id.write({'bigcommerce_message': customer_process_message})
                    _logger.info("Import Customer Process Completed ")
                else:
                    _logger.info("Getting an Error In Import Customer Address Responase".format(response_data))
                    customer_res_message=response_data.content
                    customer_message="Getting an Error In Import Customer Address Responase".format(customer_res_message)
                    self.create_bigcommerce_operation_detail('customer','import',req_data,customer_res_message,category_operation_id,warehouse_id,True,customer_message)
            except Exception as e:
                customer_process_message = "Process Is Not Completed Yet! %s" % (e)
                _logger.info("Getting an Error In Import Customer Address Responase".format(e))
                customer_message="Getting an Error In Import Customer Adderss Responase".format(e)
                self.create_bigcommerce_operation_detail('customer','import',response_data,customer_process_message,category_operation_id,warehouse_id,True,customer_message)
        else:
            self.create_bigcommerce_operation_detail('customer', 'import', False,False,
                                                     category_operation_id, False, False, "For Adderss Import, Not Getting Customer In odoo.")
        category_operation_id and category_operation_id.write({'bigcommerce_message': customer_process_message})
        self._cr.commit()

    # EXPORT CUSTOMER ALL
    def odoo_to_bigcommerce_export_customers(self, warehouse_id=False, bigcommerce_store_ids=False, new_partner_id=False):
        for bigcommerce_store_id in bigcommerce_store_ids:
            customer_process_message = "Process Completed Successfully!"
            customer_operation_id = self.create_bigcommerce_operation('customer','export',bigcommerce_store_id,'Processing...',warehouse_id)
            self._cr.commit()
            try:
                if not new_partner_id:
                    partner_ids = self.search([('bigcommerce_customer_id', '=', False),('is_available_in_bigcommerce','=',False)])
                else:
                    partner_ids = new_partner_id
                _logger.info("List of Customers Need to Export: {0}".format(partner_ids))
                if not partner_ids:
                    customer_process_message="Customers is not exists in odoo for export odoo to bigCommerce!"
                for partner_id in partner_ids:
                    customer_request_data = self.customer_request_data(partner_id)
                    api_operation="/v2/customers"
                    response_data=bigcommerce_store_id.send_request_from_odoo_to_bigcommerce(customer_request_data,api_operation)
                    _logger.info("Status Code of Export Customers: {0}".format(response_data.status_code))
                    if response_data.status_code in [200, 201]:
                        response_data = response_data.json()
                        _logger.info("Customers Response Data : %s" % (response_data))
                        if response_data.get("id"):
                            bigcommerce_customer_id = response_data.get("id")
                            partner_id.bigcommerce_customer_id = bigcommerce_customer_id
                            partner_id.bigcommerce_store_id=bigcommerce_store_id.id
                            partner_id.is_available_in_bigcommerce = True
                            process_message="%s : %s Customers Exported Successfully."%(bigcommerce_customer_id,partner_id.name)
                            self.create_bigcommerce_operation_detail('customer','export',customer_request_data,response_data,customer_operation_id,warehouse_id,False,process_message)
                        else:
                            process_message="Customers Id Not Found!"
                            self.create_bigcommerce_operation_detail('customer','export',customer_request_data,response_data,customer_operation_id,warehouse_id,True,process_message)
                    else:
                        response_data = response_data.json()
                        error_msg = response_data.get('errors')
                        self.create_bigcommerce_operation_detail('customer','export',customer_request_data,error_msg,customer_operation_id,warehouse_id,True,error_msg)
                    self._cr.commit()
                    try :
                        partner_id.export_customer_address_odoo_to_bigcommerce(warehouse_id, bigcommerce_store_id, partner_id)
                    except Exception as e:
                        continue
            except Exception as e:
                customer_process_message = "Process Is Not Completed Yet!  {}".format(e)
            customer_operation_id and customer_operation_id.write({'bigcommerce_message': customer_process_message})
            self._cr.commit()

    def export_customer_address_odoo_to_bigcommerce(self,warehouse_id=False, bigcommerce_store_ids=False, new_partner_id=False):
        for bigcommerce_store_id in bigcommerce_store_ids:
            customer_process_message = "Process Completed Successfully!"
            customer_operation_id = self.create_bigcommerce_operation('customer_address','export',bigcommerce_store_id,'Processing...',warehouse_id)
            self._cr.commit()
            try:
                _logger.info("Customers Address Need to Export: {0}".format(new_partner_id.name))
                child_partner_ids = new_partner_id.child_ids.filtered(lambda x: x.type == 'delivery')
                for child_partner_id in child_partner_ids:
                    customer_request_data = self.customer_address_request_data(child_partner_id)
                    api_operation = "/v2/customers/%s/addresses"%(new_partner_id.bigcommerce_customer_id)
                    response_data=bigcommerce_store_id.send_request_from_odoo_to_bigcommerce(customer_request_data,api_operation)
                    _logger.info("Status Code of Export Customers Address: {0}".format(response_data.status_code))
                    if response_data.status_code == 200:
                        response_data = response_data.json()
                        _logger.info("Customers Address Response Data : %s" % (response_data))
                        process_message="%s : Customers Address Exported Successfully."%(child_partner_id.name)
                        self.create_bigcommerce_operation_detail('customer_address','export',customer_request_data,response_data,customer_operation_id,warehouse_id,False,customer_process_message)
            except Exception as e:
                customer_process_message = "Process Is Not Completed Yet!  {}".format(e)

    # UPDATE CUSTOMER MANUALLY
    def export_update_customer_odoo_to_bigcommerce(self):
        bigcommerce_store_id = self.bigcommerce_store_id
        bigcommerce_customer_id = self.bigcommerce_customer_id
        if self.is_available_in_bigcommerce:
            try:
                if not bigcommerce_store_id:
                    raise ValidationError("Big commerce store not found fot this order.")
                api_url ='%s%s/v2/customers/%s'%(bigcommerce_store_id.bigcommerce_api_url,bigcommerce_store_id.bigcommerce_store_hash, bigcommerce_customer_id)
                partner_id = self
                partner_name = partner_id.name.split(" ")
                if partner_name:
                    first_name = partner_name[0]
                    last_name = partner_name[-1]
                else:
                    first_name = partner_id.name
                    last_name = ""
                request_data = {
                    "first_name": first_name or "",
                    "last_name": last_name or "",
                    'phone': partner_id.phone,
                    'email': partner_id.email
                }
                headers = {"Accept": "application/json",
                           "X-Auth-Client": "{}".format(bigcommerce_store_id and bigcommerce_store_id.bigcommerce_x_auth_client),
                           "X-Auth-Token": "{}".format(bigcommerce_store_id and bigcommerce_store_id.bigcommerce_x_auth_token),
                           "Content-Type": "application/json"}
                data = json.dumps(request_data)
                url = "{0}".format(api_url)
                try:
                    _logger.info("Send PUT Request From odoo to BigCommerce: {0}".format(url))
                    response_data =  request(method='PUT', url=api_url, data=data, headers=headers)
                except Exception as e:
                    _logger.info("Getting an Error in PUT Req odoo to BigCommerce: {0}".format(e))
                    raise ValidationError(e)
                if response_data.status_code == 200:
                    response_data = response_data.json()
                    return {
                        'effect': {
                            'fadeout': 'slow',
                            'message': 'Update Customer Exported : %s' % (self.name),
                            'img_url': '/web/static/src/img/smile.svg',
                            'type': 'rainbow_man',
                        }
                    }
                else:
                    response_data = response_data.json()
                    error_msg = "{0} : {1}".format(response_data)
                    raise ValidationError(error_msg)
            except Exception as e:
                raise ValidationError("Process Is Not Completed Yet!  {}".format(e))
        else:
            raise ValidationError("Please First Export This Customer Then Try To Update.!!!!")

    def delete_customer_odoo_to_bigcommerce(self):
        bigcommerce_store_id = self.bigcommerce_store_id
        bigcommerce_customer_id = self.bigcommerce_customer_id
        if self.is_available_in_bigcommerce:
            try:
                if not bigcommerce_store_id:
                    raise ValidationError("Big commerce store not found fot this order.")
                api_url ='%s%s/v2/customers/%s'%(bigcommerce_store_id.bigcommerce_api_url,bigcommerce_store_id.bigcommerce_store_hash, bigcommerce_customer_id)
                partner_id = self
                request_data = {
                    "customer_id": partner_id.bigcommerce_customer_id
                }
                headers = {"Accept": "application/json",
                           "X-Auth-Client": "{}".format(bigcommerce_store_id and bigcommerce_store_id.bigcommerce_x_auth_client),
                           "X-Auth-Token": "{}".format(bigcommerce_store_id and bigcommerce_store_id.bigcommerce_x_auth_token),
                           "Content-Type": "application/json"}
                data = json.dumps(request_data)
                url = "{0}".format(api_url)
                partner_id.bigcommerce_customer_id = False
                partner_id.is_available_in_bigcommerce = False
                try:
                    _logger.info("Send DELETE Request From odoo to BigCommerce: {0}".format(url))
                    response_data =  request(method='DELETE', url=api_url, data=data, headers=headers)
                except Exception as e:
                    _logger.info("Getting an Error in DELETE Req odoo to BigCommerce: {0}".format(e))
                    raise ValidationError(e)
                if response_data.status_code == 204:
                    return {
                        'effect': {
                            'fadeout': 'slow',
                            'message': 'Delete Customer : %s' % (self.name),
                            'img_url': '/web/static/src/img/smile.svg',
                            'type': 'rainbow_man',
                        }
                    }
            except Exception as e:
                raise ValidationError("Process Is Not Completed Yet!  {}".format(e))
