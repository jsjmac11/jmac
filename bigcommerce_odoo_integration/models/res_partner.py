from odoo import fields, models, api
import logging
_logger = logging.getLogger("BigCommerce")

class ResPartner(models.Model):
    _inherit = "res.partner"

    bigcommerce_store_id = fields.Many2one('bigcommerce.store.configuration',string="Bigcommerce Store",copy=False)
    bigcommerce_customer_id = fields.Char("Bigcommerce Customer ID", copy=False)
    is_available_in_bigcommerce = fields.Boolean(string='Is Exported to BigCommerce',default=False)

    
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
                            customer_id = self.env['res.partner'].search([('bigcommerce_customer_id','=',record.get('id'))],limit=1)
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
                        break
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
