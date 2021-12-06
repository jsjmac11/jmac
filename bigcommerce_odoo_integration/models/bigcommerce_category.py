from odoo import fields, models, api
from odoo.exceptions import ValidationError
from requests import request
import requests
import json
import logging
_logger = logging.getLogger("Bigcommerce")

_logger = logging.getLogger("BigCommerce")


class BigCommerceCategory(models.Model):
    _name = "bigcommerce.category"
    _description = 'BigCommerce Product Category'
    _parent_name = "parent_id"
    _rec_name = 'complete_name'
    _order = 'complete_name'

    name = fields.Char(string="Product Category", track_visibility='onchange')
    complete_name = fields.Char(
        'Complete Name', compute='_compute_complete_name',
        store=True)
    description = fields.Char(string="Description", track_visibility='onchange')
    bigcommerce_store_id = fields.Many2one('bigcommerce.store.configuration',string="Bigcommerce Store",copy=False, track_visibility='onchange')
    bigcommerce_product_category_id = fields.Char("Bigcommerce Category ID", copy=False, track_visibility='onchange')
    custom_url = fields.Char(string="Custom Url", copy=False)
    is_visible = fields.Boolean(string="Is Visible", copy=False)
    bigcommerce_parent_category_id = fields.Char("Bigcommerce Parent Category ID", copy=False, track_visibility='onchange')
    is_exported_to_bigcommerce = fields.Boolean(string='Is Exported to BigCommerce',default=False)
    parent_id = fields.Many2one('bigcommerce.category', string="Parent Category", track_visibility='onchange')

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = '%s / %s' % (category.parent_id.complete_name, category.name)
            else:
                category.complete_name = category.name

    @api.onchange('parent_id')
    def onchange_parent_id(self):
        if self.parent_id:
            self.bigcommerce_parent_category_id = self.parent_id.bigcommerce_product_category_id
        else:
            self.bigcommerce_parent_category_id = False

    def export_product_category_to_bigcommerce(self):
        if self._context.get('active_model') == 'bigcommerce.category':
            category_ids = self.env.context.get('active_ids')
            category_objs = self.env['bigcommerce.category'].browse(category_ids)
            self.odoo_to_bigcommerce_export_product_categories(bigcommerce_store_ids= category_objs.bigcommerce_store_id,new_category_id=category_objs)
            # category_objs.write({'is_exported_to_bigcommerce':True})
        return

    def create_bigcommerce_operation(self,operation,operation_type,bigcommerce_store_id,log_message,warehouse_id):
        vals = {
                    'bigcommerce_operation': operation,
                    'bigcommerce_operation_type': operation_type,
                    'bigcommerce_store': bigcommerce_store_id and bigcommerce_store_id.id ,
                    'bigcommerce_message': log_message,
                    'warehouse_id': warehouse_id and warehouse_id.id or False
                   }
        operation_id = self.env['bigcommerce.operation'].create(vals)
        return  operation_id

    def create_bigcommerce_operation_detail(self,operation,operation_type,req_data,response_data,operation_id,warehouse_id=False,fault_operation=False,process_message=False):
        bigcommerce_operation_details_obj = self.env['bigcommerce.operation.details']
        vals = {
                    'bigcommerce_operation': operation,
                    'bigcommerce_operation_type': operation_type,
                    'bigcommerce_request_message': '{}'.format(req_data),
                    'bigcommerce_response_message': '{}'.format(response_data),
                    'operation_id':operation_id.id,
                    'warehouse_id': warehouse_id and warehouse_id.id or False,
                    'fault_operation':fault_operation,
                    'process_message':process_message,
                   }
        operation_detail_id = bigcommerce_operation_details_obj.create(vals)
        return operation_detail_id

    def category_request_data(self, category_id):
        category_name = category_id and category_id.name
        if " " in category_name:
            category_name = category_name.replace(" ","-")
        return  {
            "parent_id": int(category_id and category_id.parent_id and category_id.parent_id.bigcommerce_product_category_id) or 0,
            "name": category_id and category_id.name or "",
            "description": "",
            #"views": 1050,
            "sort_order": category_id and category_id.id or "",
            "meta_keywords": [],
            "is_visible": True,
            "default_product_sort": "use_store_settings",
            "custom_url": {"url": "/{}/".format(category_name),"is_customized": False}}

    def export_update_product_categories_odoo_to_bigcommerce(self):
        bigcommerce_store_id = self.bigcommerce_store_id
        bigcommerce_product_category_id = self.bigcommerce_product_category_id
        if self.is_exported_to_bigcommerce:
            try:
                if not bigcommerce_store_id:
                    raise ValidationError("Big commerce store not found fot this order.")
                api_url ='%s%s/v3/catalog/categories/%s'%(bigcommerce_store_id.bigcommerce_api_url,bigcommerce_store_id.bigcommerce_store_hash, bigcommerce_product_category_id)
                category_id = self
                request_data = {
                    "parent_id": int(category_id and category_id.parent_id and category_id.parent_id.bigcommerce_product_category_id) or 0,
                    "name": category_id and category_id.name or "",
                    "description": "",
                    "sort_order": category_id and category_id.id or "",
                    "meta_keywords": [],
                    "is_visible": True,
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
                if response_data.status_code in [200, 201]:
                    response_data = response_data.json()
                    return {
                        'effect': {
                            'fadeout': 'slow',
                            'message': 'Update Categories Exported : %s' % (self.name),
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
            raise ValidationError("Please First Export This Categories Then Try To Update Categories.!!!!")

    def odoo_to_bigcommerce_export_product_categories(self, warehouse_id=False, bigcommerce_store_ids=False, new_category_id=False):
        for bigcommerce_store_id in bigcommerce_store_ids:
            category_process_message = "Process Completed Successfully!"
            category_operation_id = self.create_bigcommerce_operation('product_category','export',bigcommerce_store_id,'Processing...',warehouse_id)
            self._cr.commit()
            try:
                if not new_category_id:
                    category_ids = self.search([('bigcommerce_product_category_id', '=', False),('is_exported_to_bigcommerce','=',False)])
                else:
                    category_ids = new_category_id
                _logger.info("List of Product Category Need to Export: {0}".format(category_ids))
                if not category_ids:
                    category_process_message="Product is not exists in odoo for export odoo to bigCommerce!"
                for category_id in category_ids:
                    category_request_data = self.category_request_data(category_id)
                    api_operation="/v3/catalog/categories"
                    response_data=bigcommerce_store_id.send_request_from_odoo_to_bigcommerce(category_request_data,api_operation)
                    _logger.info("Status Code of Export Product Category: {0}".format(response_data.status_code))
                    if response_data.status_code in [200, 201]:
                        response_data = response_data.json()
                        _logger.info("Category Response Data : %s" % (response_data))
                        if response_data.get('data') and response_data.get('data').get("id"):
                            bigcommerce_category_id = response_data.get('data').get("id")
                            category_id.bigcommerce_product_category_id=bigcommerce_category_id
                            category_id.bigcommerce_store_id=bigcommerce_store_id.id
                            category_id.is_exported_to_bigcommerce = True
                            process_message="%s : %s Product Category Exported Successfully."%(bigcommerce_category_id,category_id.name)
                            self.create_bigcommerce_operation_detail('product_category','export',category_request_data,response_data,category_operation_id,warehouse_id,False,process_message)
                        else:
                            process_message="Product Id Not Found!"
                            self.create_bigcommerce_operation_detail('product_category','export',category_request_data,response_data,category_operation_id,warehouse_id,True,process_message)
                    else:
                        response_data = response_data.json()
                        error_msg = response_data.get('errors')
                        self.create_bigcommerce_operation_detail('product_category','export',category_request_data,error_msg,category_operation_id,warehouse_id,True,error_msg)
                    self._cr.commit()
            except Exception as e:
                category_process_message = "Process Is Not Completed Yet!  {}".format(e)
                self.create_bigcommerce_operation_detail('product_category','export',category_request_data,response_data,category_operation_id,warehouse_id,True,category_process_message)
            category_operation_id and category_operation_id.write({'bigcommerce_message': category_process_message})
            self._cr.commit()

    def bigcommerce_to_odoo_import_product_categories(self,warehouse_id=False, bigcommerce_store_ids=False):
        for bigcommerce_store_id in bigcommerce_store_ids:
            req_data = False
            category_response_pages=[]
            category_process_message = "Process Completed Successfully!"
            category_operation_id = self.create_bigcommerce_operation('product_category','import',bigcommerce_store_id,'Processing...',warehouse_id)
            self._cr.commit()
            try:
                api_operation = "/v3/catalog/categories"
                response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(api_operation)
                _logger.info("BigCommerce Get Product Categoxry Response: {0}".format(response_data))
                _logger.info("Response Status: {0}".format(response_data.status_code))
                if response_data.status_code in [200, 201]:
                    response_data = response_data.json()
                    _logger.info("Category Response Data: {0}".format(response_data))
                    records = response_data.get('data')
                    total_pages = response_data.get('meta').get('pagination').get('total_pages')
                    if total_pages > 1:
                        while(total_pages!=0):
                            try:
                                page_api = "/v3/catalog/categories?page=%s"%(total_pages)
                                page_response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(
                                    page_api)
                                _logger.info("BigCommerce Get Product Category Response: {0}".format(page_response_data))
                                _logger.info("Response Status: {0}".format(page_response_data.status_code))
                                if page_response_data.status_code in [200, 201]:
                                    page_response_data = page_response_data.json()
                                    _logger.info("Category Response Data: {0}".format(page_response_data))
                                    records = page_response_data.get('data')
                                    category_response_pages.append(records)
                            except Exception as e:
                                category_process_message = "Page is not imported! %s" % (e)
                                _logger.info("Getting an Error In Import Product Category Response {}".format(e))
                                process_message = "Getting an Error In Import Product Category Response {}".format(e)
                                self.create_bigcommerce_operation_detail('product_category', 'import', page_response_data,
                                                                         category_process_message,
                                                                         category_operation_id, warehouse_id, True,
                                                                         process_message)
                            total_pages = total_pages - 1
                    else:
                        category_response_pages.append(records)

                    for category_response_page in category_response_pages:
                        for record in category_response_page:
                            category_id = self.env['bigcommerce.category'].search([('bigcommerce_product_category_id','=',record.get('id'))],limit=1)
                            if not category_id:
                                vals = {
                                    'name':record.get('name'),
                                    'bigcommerce_product_category_id':record.get('id'),
                                    'custom_url':record.get('custom_url') and record.get('custom_url').get('url'),
                                    'is_visible':record.get('is_visible'),
                                    'bigcommerce_parent_category_id':record.get('parent_id'),
                                    # 'property_cost_method':'standard',
                                    # 'property_valuation':'manual_periodic',
                                    'bigcommerce_store_id':bigcommerce_store_id.id,
                                    'is_exported_to_bigcommerce':True
                                    }
                                category_id = self.env['bigcommerce.category'].create(vals)
                                _logger.info("Product Category Created: {0}".format(category_id.name))
                                response_data = record
                                process_message="Product Category Created : {0}".format(category_id.name)
                            else:
                                vals = {
                                    'name':record.get('name'),
                                    'custom_url':record.get('custom_url') and record.get('custom_url').get('url'),
                                    'is_visible':record.get('is_visible'),
                                    'bigcommerce_parent_category_id':record.get('parent_id'),
                                    'bigcommerce_store_id':bigcommerce_store_id.id
                                    }
                                category_id.write(vals)
                                _logger.info("Product Category Updated: {0}".format(category_id.name))
                                process_message ="Product Category Updated : {0}".format(category_id.name)
                                req_data = record
                            self.create_bigcommerce_operation_detail('product_category','import',req_data,response_data,category_operation_id,warehouse_id,False,process_message)
                            self._cr.commit()
                    category_operation_id and category_operation_id.write({'bigcommerce_message': category_process_message})
                    all_catg_id = self.env['bigcommerce.category'].search([])
                    for category in all_catg_id:
                        parent_id = self.env['bigcommerce.category'].search([('bigcommerce_product_category_id', '=', category.bigcommerce_parent_category_id)], limit=1)
                        category.parent_id = parent_id and parent_id.id or False
                    _logger.info("Import Product Category Process Completed")
                else:
                    _logger.info("Getting an Error In Import Product Category Response {}".format(response_data))
                    response_data=response_data.content
                    process_message="Getting an Error In Import Product Category Response".format(response_data)
                    self.create_bigcommerce_operation_detail('product_category','import',req_data,response_data,category_operation_id,warehouse_id,True,process_message)
            except Exception as e:
                category_process_message = "Process Is Not Completed Yet! %s" % (e)
                _logger.info("Getting an Error In Import Product Category Response {}".format(e))
                process_message="Getting an Error In Import Product Category Response {}".format(e)
                self.create_bigcommerce_operation_detail('product_category','import',response_data,category_process_message,category_operation_id,warehouse_id,True,process_message)
            category_operation_id and category_operation_id.write({'bigcommerce_message': category_process_message})
            bigcommerce_store_ids.bigcommerce_operation_message = " Import Product Categories Process Complete "
            self._cr.commit()

    def delete_product_categories_odoo_to_bigcommerce(self):
        bigcommerce_store_id = self.bigcommerce_store_id
        bigcommerce_product_category_id = self.bigcommerce_product_category_id
        if self.is_exported_to_bigcommerce:
            try:
                if not bigcommerce_store_id:
                    raise ValidationError("Big commerce store not found fot this order.")
                api_url ='%s%s/v3/catalog/categories/%s'%(bigcommerce_store_id.bigcommerce_api_url,bigcommerce_store_id.bigcommerce_store_hash, bigcommerce_product_category_id)
                category_id = self
                request_data = {
                    "category_id": category_id.bigcommerce_product_category_id
                }
                headers = {"Accept": "application/json",
                           "X-Auth-Client": "{}".format(bigcommerce_store_id and bigcommerce_store_id.bigcommerce_x_auth_client),
                           "X-Auth-Token": "{}".format(bigcommerce_store_id and bigcommerce_store_id.bigcommerce_x_auth_token),
                           "Content-Type": "application/json"}
                data = json.dumps(request_data)
                url = "{0}".format(api_url)
                category_id.bigcommerce_product_category_id = False
                category_id.is_exported_to_bigcommerce = False
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
                            'message': 'Delete Categories : %s' % (self.name),
                            'img_url': '/web/static/src/img/smile.svg',
                            'type': 'rainbow_man',
                        }
                    }
            except Exception as e:
                raise ValidationError("Process Is Not Completed Yet!  {}".format(e))
