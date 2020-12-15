from odoo import fields,models,api
from odoo.exceptions import ValidationError
import requests
import json
import base64
import logging
_logger = logging.getLogger("Bigcommerce")

class BigcommerceProductBrand(models.Model):
    _name = "bc.product.brand"
    
    bc_brand_id = fields.Char(string='Brand Id')
    name = fields.Char(string='Brand Name')
    bigcommerce_store_id = fields.Many2one('bigcommerce.store.configuration',string='Bigcommerce Store')
    
    def bigcommerce_to_odoo_import_product_brands(self,warehouse_id=False, bigcommerce_store_ids=False):
        for bigcommerce_store_id in bigcommerce_store_ids:
            req_data = False
            brand_response_pages=[]
            brand_process_message = "Process Completed Successfully!"
            brand_operation_id = bigcommerce_store_id.create_bigcommerce_operation('brand','import',bigcommerce_store_id,'Processing...',warehouse_id)
            self._cr.commit()
            try:
                api_operation = "/v3/catalog/brands"
                response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(api_operation)
                _logger.info("BigCommerce Get Product Brand Response : {0}".format(response_data))
                _logger.info("Response Status: {0}".format(response_data.status_code))
                if response_data.status_code in [200, 201]:
                    response_data = response_data.json()
                    records = response_data.get('data')
                    total_pages = response_data.get('meta').get('pagination').get('total_pages')
                    if total_pages > 1:
                        while(total_pages!=0):
                            try:
                                page_api = "/v3/catalog/brands?page=%s"%(total_pages)
                                page_response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(
                                    page_api)
                                _logger.info("Response Status: {0}".format(page_response_data.status_code))
                                if page_response_data.status_code in [200, 201]:
                                    page_response_data = page_response_data.json()
                                    records = page_response_data.get('data')
                                    brand_response_pages.append(records)
                            except Exception as e:
                                brand_process_message = "Page is not imported! %s" % (e)
                                _logger.info("Getting an Error In Import Product Category Response {}".format(e))
                                process_message = "Getting an Error In Import Product Category Response {}".format(e)
                                bigcommerce_store_id.create_bigcommerce_operation_detail('brand', 'import', page_response_data,
                                                                         brand_process_message,
                                                                         brand_operation_id, warehouse_id, True,
                                                                         process_message)
                            total_pages = total_pages - 1
                    else:
                        brand_response_pages.append(records)

                    for brand_response_page in brand_response_pages:
                        for record in brand_response_page:
                            brand_id = self.env['bc.product.brand'].search([('bc_brand_id','=',record.get('id'))],limit=1)
                            if not brand_id:
                                vals = {
                                    'name':record.get('name'),
                                    'bc_brand_id':record.get('id'),
                                    'bigcommerce_store_id':bigcommerce_store_id.id
                                    }
                                brand_id = self.env['bc.product.brand'].create(vals)
                                _logger.info("Product Brand Created : {0}".format(brand_id.name))
                                response_data = record
                                process_message="Product Brand Created : {0}".format(brand_id.name)
                            else:
                                vals = {
                                    'name':record.get('name'),
                                    'bigcommerce_store_id':bigcommerce_store_id.id
                                    }
                                brand_id.write(vals)
                                process_message ="Product Brand Updated : {0}".format(brand_id.name)
                                req_data = record
                            bigcommerce_store_id.create_bigcommerce_operation_detail('brand','import',req_data,response_data,brand_operation_id,warehouse_id,False,process_message)
                            self._cr.commit()
                    brand_operation_id and brand_operation_id.write({'bigcommerce_message': brand_process_message})
                else:
                    response_data=response_data.content
                    process_message="Getting an Error In Import Product Brand Response".format(response_data)
                    bigcommerce_store_id.create_bigcommerce_operation_detail('product_category','import',req_data,response_data,brand_operation_id,warehouse_id,True,process_message)
            except Exception as e:
                brand_process_message = "Process Is Not Completed Yet! %s" % (e)
                process_message="Getting an Error In Import Product Category Response {}".format(e)
                bigcommerce_store_id.create_bigcommerce_operation_detail('product_category','import',response_data,brand_process_message,brand_operation_id,warehouse_id,True,process_message)
            brand_operation_id and brand_operation_id.write({'bigcommerce_message': brand_process_message})
            bigcommerce_store_ids.bigcommerce_operation_message = " Import Product Brand Process Complete "
            self._cr.commit()