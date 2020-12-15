from odoo import models,api,fields,_
import logging
import base64
from odoo.exceptions import ValidationError
import requests
import json
import time

_logger = logging.getLogger("BigCommerce")

class product_attribute(models.Model):
    _inherit = "product.attribute"
    
    bigcommerce_attribute_id = fields.Char(string='BigCommerce Attribute Id')
    
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
                    'process_message': process_message
                   }
        operation_detail_id = bigcommerce_operation_details_obj.create(vals)
        return operation_detail_id
    
    def get_product_attribute(self,attribute_string,type='radio',create_variant='always'):
        attributes=self.search([('name','=ilike',attribute_string),('create_variant','=',create_variant)])
        if not attributes:
                return self.create(({'name':attribute_string,'create_variant':create_variant,'type':type}))
        else:
            return attributes
    
    def attribute_request_data(self,bigcommerce_product_id,attribute_line):
        """
        Description : Prepare Product Attribute and Attribute Value Request Data For Generate/Create Product Attribute and Attribute Value in Bigcommerce.
        """
        attribute_data = {
            "product_id":bigcommerce_product_id,
            "name":attribute_line.attribute_id.name,
            "display_name":attribute_line.attribute_id.name,
            
            }
        option_values = []
        sort_order = 1
        if attribute_line.attribute_id.type == 'color':
            for attribute_value in attribute_line.value_ids:
                color = []
                color.append(attribute_value.html_color)
                if not attribute_value.bigcommerce_value_id:
                    option_values.append({'label':attribute_value.name,"sort_order":sort_order,"value_data": {"colors":color}})
                    sort_order += 1
        else:
            for attribute_value in attribute_line.value_ids:
                if not attribute_value.bigcommerce_value_id:
                    option_values.append({'label':attribute_value.name,"sort_order":sort_order})
                    sort_order += 1
        if attribute_line.attribute_id.type=='radio':
            attribute_data.update({"type": "radio_buttons" ,"option_values":option_values})
        elif attribute_line.attribute_id.type=='select':
            attribute_data.update({"type": "dropdown" ,"option_values":option_values})
        elif attribute_line.attribute_id.type=='color':
            attribute_data.update({"type": "swatch" ,"option_values":option_values})
        else:
            attribute_data.update({"type": "rectangles","option_values":option_values })
        return attribute_data
                    
    def import_product_attribute_from_bigcommerce(self,warehouse_id=False, bigcommerce_store_ids=False,product_objs=False,operation_id=False):
        for bigcommerce_store_id in bigcommerce_store_ids:
            process_complete = False
            product_process_message = "Process Completed Successfully!"
            location_id = bigcommerce_store_id.warehouse_id.lot_stock_id
            if not operation_id:
                process_complete = True
                operation_id = self.with_user(1).create_bigcommerce_operation('product_attribute','import',bigcommerce_store_id,'Processing...',warehouse_id)
            response_data = False
            _logger.info("Attribute Method ===> Products: {0}".format(product_objs))
            if not product_objs:
                product_objs = self.env['product.template'].with_user(1).search([('bigcommerce_product_id','!=',False)])
#             attribute_line = self.env['product.template.attribute.line'].search([("product_tmpl_id",'=',product_objs.id)])
#             if attribute_line:
#                 attribute_line.with_user(1).unlink()
#                 self._cr.commit()
            product_objs = product_objs.filtered(lambda pp:pp.with_user(1).product_variant_count <= 1)
            self._cr.commit()
            for product in product_objs:
                try:
                    _logger.info("BigCommerce Product ID: {0} Product Template ID:{1}".format(product.bigcommerce_product_id,product))
                    api_operation = "/v3/catalog/products/{}/options".format(product.bigcommerce_product_id)
                    time.sleep(5)
                    response_data = bigcommerce_store_id.with_user(1).send_get_request_from_odoo_to_bigcommerce(api_operation)
                    if response_data and response_data.status_code in [200, 201]:
                        _logger.info("Status Code :{0}".format(response_data.status_code))
                        response_data = response_data.json()
                        _logger.info("response data :{0}".format(response_data))
                        records = response_data.get('data')
                        _logger.info("Attribute Record:{}".format(records))
                        if records:
                            self.with_user(1).create_bigcommerce_operation_detail('product_attribute', 'import', api_operation, records,operation_id, warehouse_id, False, records)
                        for record in records:
                            attribute_id = self.env['product.attribute'].with_user(1).search([('bigcommerce_attribute_id','=',record.get('id'))],limit=1) 
                            if not attribute_id:
                                vals = {}
                                if record.get('type')=='swatch':
                                    vals.update({'display_type':'color'})
                                elif record.get('type')=='radio_buttons':
                                    vals.update({'display_type':'radio'})
                                else:
                                    vals.update({'display_type':'select'})
                                vals.update({'name':record.get('display_name') + "-" + str(record.get('id')),'create_variant':'always','bigcommerce_attribute_id':str(record.get('id'))})
                                attribute_id = self.env['product.attribute'].with_user(1).create(vals)
                            else:
                                attribute_id.with_user(1).write({'bigcommerce_attribute_id':record.get('id')})
                                
                            attribute_value_ids = []
                            for option_value in record.get('option_values'):
                                attribute_value_obj = self.env['product.attribute.value'].with_user(1).search([('name','=',option_value.get('label')),('attribute_id','=',attribute_id.id)],limit=1)
                                if not attribute_value_obj:
                                    attribute_value = {'name':option_value.get('label'),"bigcommerce_value_id":option_value.get("id"),"attribute_id":attribute_id.id}
                                    if option_value.get("value_data"):
                                        # attribute_value.update({"html_color":option_value.get("value_data").get("colors")[0]})
                                        attribute_value.update({"html_color": option_value.get("label")})
                                    attribute_value_obj = self.env['product.attribute.value'].with_user(1).create(attribute_value)
                                else:
                                    attribute_value_obj.with_user(1).write({'bigcommerce_value_id':option_value.get('id')})
                                attribute_value_ids.append(attribute_value_obj.id)
                            attribute_line = self.env['product.template.attribute.line'].with_user(1).search([('attribute_id','=',attribute_id.id),("product_tmpl_id",'=',product.id)])
                            if attribute_line:
                                vals = {"attribute_id":attribute_id.id,"value_ids":[(6,0,attribute_value_ids)]}
                                attribute_line.with_user(1).write(vals)
                            else:
                                vals = {"attribute_id":attribute_id.id,"value_ids":[(6,0,attribute_value_ids)],"product_tmpl_id":product.id}
                                attribute_line = self.env['product.template.attribute.line'].with_user(1).create(vals)
                                self._cr.commit()
                        
                        product.with_user(1)._create_variant_ids()
                        self._cr.commit()
                        api_operation_variant = "/v3/catalog/products/{}/variants".format(product.bigcommerce_product_id)
                        api_operation_variant_response_data = bigcommerce_store_id.with_user(1).send_get_request_from_odoo_to_bigcommerce(
                            api_operation_variant)
                        _logger.info("BigCommerce Get Product Variant Response : {0}".format(api_operation_variant_response_data))
                        _logger.info("Response Status: {0}".format(api_operation_variant_response_data.status_code))
                        if api_operation_variant_response_data.status_code in [200, 201]:
                            api_operation_variant_response_data = api_operation_variant_response_data.json()
                            variant_datas = api_operation_variant_response_data.get('data')
                            for variant_data in variant_datas:
                                option_labales = []
                                option_values = variant_data.get('option_values')
                                for option_value in option_values:
                                    option_labales.append(option_value.get('label'))
                                v_id = variant_data.get('id')
                                product_sku = variant_data.get('sku')
                                _logger.info("Total Product Variant : {0} Option Label : {1}".format(product.product_variant_ids,option_labales))
                                for product_variant_id in product.product_variant_ids:
                                    if product_variant_id.mapped(lambda pv: pv.with_user(1).product_template_attribute_value_ids.mapped('name') == option_labales)[0]:
                                        _logger.info("Inside If Condition option Label =====> {0} Product Template Attribute Value ====> {1} variant_id====>{2}".format(option_labales,product_variant_id.with_user(1).mapped('product_template_attribute_value_ids').mapped('name'),product_variant_id))
                                        if variant_data.get('price'):
                                            price = variant_data.get('price')
                                        else:
                                            price = variant_data.get('calculated_price')
                                        vals = {'default_code':product_sku,'lst_price':price,'bigcommerce_product_variant_id':v_id,'standard_price':variant_data.get('cost_price',0.0)} 
                                        variant_product_img_url = variant_data.get('image_url')
                                        if variant_product_img_url:
                                            image = base64.b64encode(requests.get(variant_product_img_url).content)
                                            vals.update({'image_1920':image})
                                        product_variant_id.with_user(1).write(vals)
                                        _logger.info("Product Variant Updated : {0}".format(product_variant_id.default_code))
                                        self._cr.commit()
#                                         product_qty = variant_data.get('inventory_level')
#                                         if product_qty > 0:
#                                             quant_id = self.env['stock.quant'].search([('product_id','=',product_variant_id.id),('location_id','=',location_id.id)],limit=1)
#                                             if not quant_id:
#                                                 quant_vals = {'product_tmpl_id':product_variant_id.product_tmpl_id.id,'location_id':location_id.id,'inventory_quantity':product_qty,'product_id':product_variant_id.id,'quantity':product_qty}
#                                                 self.env['stock.quant'].sudo().create(quant_vals)
#                                             else:
#                                                 quant_id.sudo().write({'inventory_quantity':product_qty,'quantity':product_qty})
#                                            self._cr.commit()
                        else:
                            api_operation_variant_response_data = api_operation_variant_response_data.json()
                            error_msg = api_operation_variant_response_data.get('errors')
                            self.create_bigcommerce_operation_detail('product_attribute', 'import', '', error_msg,
                                                                     operation_id, warehouse_id, True, error_msg)


                    else:
                            response_data = response_data.json()
                            error_msg = response_data.get('errors')
                            self.create_bigcommerce_operation_detail('product_attribute','import','',error_msg,operation_id,warehouse_id,True,error_msg)
                except Exception as e:
                    product_process_message = "Product : {0} Process Is Not Completed Yet!  {1}".format(product,e)
                    self.create_bigcommerce_operation_detail('product_attribute','export',"",response_data,operation_id,warehouse_id,True,product_process_message)
            if process_complete:
                operation_id and operation_id.write({'bigcommerce_message': product_process_message})
                bigcommerce_store_id.bigcommerce_operation_message = "Import Product Attribute Process Completed."
            self._cr.commit()        
        
class product_attribute_value(models.Model):
    _inherit = "product.attribute.value"
    
    bigcommerce_value_id = fields.Char(string="BigCommerce Value Id")
    
    def get_product_attribute_values(self,name,attribute_id):
        attribute_values=self.search([('name','=ilike',name),('attribute_id','=',attribute_id)])
        if not attribute_values:
            return self.create(({'name':name,'attribute_id':attribute_id}))
        else:
            return attribute_values