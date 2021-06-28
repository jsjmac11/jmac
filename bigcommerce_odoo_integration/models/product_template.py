from odoo import fields, models, api
from requests import request
import logging
import json
import requests
import json
import base64
from odoo.exceptions import UserError, ValidationError
import html2text

_logger = logging.getLogger("BigCommerce")

class ProductProduct(models.Model):
    _inherit = "product.product"
    
    bigcommerce_product_variant_id = fields.Char(string='Bigcommerce Product Variant ID')
    
class ProductTemplate(models.Model):
    _inherit = "product.template"

    bigcommerce_product_image_ids = fields.One2many('bigcommerce.product.image', 'product_template_id',
                                                    string="Bigcommerce Product Image Ids")
    bigcommerce_product_id = fields.Char(string='Product ID')
    bigcommerce_store_id = fields.Many2one('bigcommerce.store.configuration',string="Bigcommerce Store",copy=False)
    is_exported_to_bigcommerce = fields.Boolean(string="Is Exported to Big Commerce ?")
    inventory_tracking = fields.Selection([
        ('none', 'Inventory Level will not be tracked'),
        ('product', 'Inventory Level Tracked using the Inventory Level'),
        ('variant', 'Inventory Level Tracked Based on variant')
    ], "Inventory Tracking", default="none")
    inventory_warning_level = fields.Integer(string="Inventory Warning Level")
    inventory_level = fields.Integer(string="Inventory Level")
    is_visible = fields.Boolean(string="Is Visible",default=True)
    warranty = fields.Char(string="Warranty")
    is_imported_from_bigcommerce = fields.Boolean(string="Is Imported From Big Commerce ?")
    x_studio_manufacturer = fields.Many2one('bc.product.brand',string='Brand ID')
    bigcommerce_category_ids = fields.Many2many('bigcommerce.category', 'product_big_categ_rel', 'product_id', 'category_id', string="Bigcommerce Category")
    #Added new fields related to big commerce
    allow_purchases = fields.Boolean('Allow Purchases?')
    item_type = fields.Char('Item Type')
    option_set_align = fields.Char('Option Set')
    discontinued = fields.Boolean('Discontinued')
    product_image_description_1 = fields.Char('Product Image Description - 1')
    product_tax_class = fields.Selection([('Default Tax Class', 'Default Tax Class'),
                                          ('Non-Taxable Products', 'Non-Taxable Products'),
                                          ('Shipping', 'Shipping'),
                                          ('Gift Wrapping', 'Gift Wrapping')], 'Product Tax Class')
    product_visible = fields.Boolean('Product Visible?')
    product_weight = fields.Float('Weight', default=1.0)
    show_product_condition = fields.Boolean('Is Condition Shown?',
                                            default=False)
    stop_processing_rules = fields.Selection([('Y', 'Y'),
                                                ('N', 'N')], 'Stop Processing Rules',
                                            default='N')
    vendor_part_number = fields.Char('Vendor Part Number')
    
    is_free_shipping = fields.Boolean('Free Shipping')
    
    meta_description = fields.Text('Meta Description')
    
    meta_keywords = fields.Char('Meta Keywords')
    page_title = fields.Char('Page Title')
    product_availability = fields.Boolean('Availability')
    product_condition = fields.Char('Condition')
    product_URL = fields.Char('URL Is Customized')
    search_keywords = fields.Char('Search Keywords')
    sort_order =  fields.Integer('Sort Order')
    track_inventory = fields.Char('Track Inventory')
    product_type = fields.Char('Type')
    product_custom_fields = fields.Char('Product Custom Fields')
    product_depth = fields.Integer('Depth')
    gtin = fields.Char('GTIN')
    height = fields.Integer("Height")
    is_featured = fields.Boolean('Is Featured')
    is_preorder_only = fields.Boolean('Is Preorder Only')
    is_price_hidden = fields.Boolean('Is Price Hidden')
    map_price = fields.Integer("MAP Price")
    option_set_display = fields.Char('Option Set Display')
    order_quantity_maximum = fields.Integer('Order Quantity Maximum', default=0)
    order_quantity_minimum = fields.Integer('Order Quantity Minimum', default=0)
    price_hidden_label = fields.Char('Price Hidden Label')
    related_products = fields.Char('Related Products')
    retail_price = fields.Float('Retail Price')
    tax_class_id = fields.Integer('Tax Class ID')
    width = fields.Integer('Width')
    brand_id = fields.Integer("Brand ID")
    
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
                    'process_message':process_message
                   }
        operation_detail_id = bigcommerce_operation_details_obj.create(vals)
        return operation_detail_id

    def product_request_data(self, product_id,warehouse_id):
        """
        Description : Prepare Product Request Data For Generate/Create Product in Bigcomeerce
        """
        product_variants = []
        product_name = product_id and product_id.name
        product_data = {
            "name": product_id.name,
              "price": product_id.list_price,
              "categories": [int(product_id.categ_id and product_id.categ_id.bigcommerce_product_category_id)],
              "weight": product_id.weight or 1.0,
              "type": "physical",
              "sku":product_id.default_code or '',
              "description":product_id.name,
              "cost_price":product_id.standard_price,
              "inventory_tracking":product_id.inventory_tracking,
              "inventory_level":product_id.with_context(warehouse=warehouse_id.id).qty_available,
              "is_visible":product_id.is_visible,
              "warranty":product_id.warranty or ''
        }
        return  product_data


    def product_variant_request_data(self,product_variant):
        """
        Description : Prepare Product Variant Request Data For Create Product  Variant in Bigcommerce.
        """
        option_values = []
        product_data = {
          "cost_price":product_variant.standard_price,
          "price": product_variant.lst_price,
          "weight": product_variant.weight or 1.0,
          "sku":product_variant.default_code or '',
          "product_id":product_variant.product_tmpl_id.bigcommerce_product_id
            
        }
        for attribute_value in product_variant.attribute_value_ids:
            option_values.append({'id':attribute_value.bigcommerce_value_id,'option_id':attribute_value.attribute_id.bigcommerce_attribute_id})
        product_data.update({"option_values":option_values})
        return product_data
            
    def create_product_template(self,record,store_id):
        product_attribute_obj = self.env['product.attribute']
        product_attribute_value_obj = self.env['product.attribute.value']
        product_template_obj = self.env['product.template']
        template_title = ''
        if record.get('name',''):
            template_title = record.get('name')
        attrib_line_vals = []
        if record.get('variants'):
            for attrib in record.get('variants'):
                if not attrib.get('option_values'):
                    continue
                attrib_name = attrib.get('option_display_name')    
                attrib_values = attrib.get('label')
                attribute=product_attribute_obj.get_product_attribute(attrib_name,type='radio',create_variant='always')
                attribute_val_ids = []
                
                attrib_value = product_attribute_value_obj.get_product_attribute_values(attrib_values,attribute.id)
                attribute_val_ids.append(attrib_value.id)
                
                if attribute_val_ids:
                    attribute_line_ids_data = [0, False,{'attribute_id': attribute.id,'value_ids':[[6, False, attribute_val_ids]]}]
                    attrib_line_vals.append(attribute_line_ids_data)
        category_id = self.env['bigcommerce.category'].sudo().search([('bigcommerce_product_category_id','in',record.get('categories'))])
        if not category_id:
            message = "Category not found!"
            _logger.info("Category not found: {}".format(category_id))
            return False, message
        brand_id = self.env['bc.product.brand'].sudo().search([('bc_brand_id','=',record.get('brand_id'))],limit=1)
        _logger.info("BRAND : {0}".format(brand_id))
        description_sale = html2text.html2text(record.get('description'))
        availability = False
        condition = 'N'
        if record.get('availability', False) == 'available':
            availability = True
        if record.get('is_condition_shown', False):
            condition = 'Y'  
        vals = {
                'name':template_title,
                'type':'product',
                # 'categ_id':category_id and category_id[0].id,
                'bigcommerce_category_ids':category_id and [(6,0, category_id.ids)],
                "weight":record.get("weight"),
                "list_price":record.get("price"),
                "is_visible":record.get("is_visible"),
                "bigcommerce_product_id":record.get('id'),
                "bigcommerce_store_id":store_id.id,
                "default_code":record.get("sku"),
                "is_imported_from_bigcommerce":True,
                "x_studio_manufacturer":brand_id and brand_id.id,
                "description_sale":description_sale,
                "allow_purchases": availability,
                "item_type": record.get('type'),
                "product_visible": record.get('is_visible'),
                "product_weight": record.get('weight'),
                "show_product_condition": record.get('condition'),
                "product_type" : record.get('type'),
                "vendor_part_numbe" : record.get('mpn'),
                "track_inventory" : record.get('inventory_tracking'),
                "sort_order" : record.get('sort_order'),
                "show_product_condition" : record.get('is_condition_shown'),
                "search_keywords" : record.get('search_keywords'),
                "product_visible" : record.get('is_visible'),
                "product_URL" : record.get('custom_url'),
                "product_condition" : record.get('condition'),
                "product_availability" :  record.get('availability'),
                "page_title" : record.get('page_title'),
                "meta_keywords" : record.get('meta_keywords'),
                "meta_description" : record.get('meta_description'),
                "is_free_shipping" : record.get('is_free_shipping'),
                "standard_price": record.get('cost_price'),
                "product_depth": record.get('depth'),
                "gtin": record.get('gtin'),
                "height": record.get('height'),
                "inventory_level": record.get('inventory_level'),
                "is_featured": record.get('is_featured'),
                "option_set_align": record.get('option_set_align'),
                "is_preorder_only": record.get('is_preorder_only'),
                "is_price_hidden": record.get('is_price_hidden'),
                "map_price": record.get("map_price"),
                "option_set_display": record.get('option_set_display'),
                "order_quantity_maximum": record.get('order_quantity_maximum'),
                "order_quantity_minimum": record.get('order_quantity_minimum'),
                "price_hidden_label": record.get('price_hidden_label'),
                "related_products": record.get('related_products'),
                "retail_price": record.get('retail_price'),
                "tax_class_id" : record.get('tax_class_id'),
                "width" : record.get('width'),
                "brand_id" : record.get("brand_id")
                }
        product_template = product_template_obj.with_user(1).create(vals)
        _logger.info("Product Created: {}".format(product_template))
        return True, product_template
    
    def import_product_from_bigcommerce(self, warehouse_id=False, bigcommerce_store_ids=False):
        for bigcommerce_store_id in bigcommerce_store_ids:
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Auth-Client': '{}'.format(bigcommerce_store_ids.bigcommerce_x_auth_client),
                'X-Auth-Token': "{}".format(bigcommerce_store_ids.bigcommerce_x_auth_token)
            }
            req_data = False
            bigcommerce_store_id.bigcommerce_product_import_status = "Import Product Process Running..."
            product_process_message = "Process Completed Successfully!"
            operation_id = self.with_user(1).create_bigcommerce_operation('product','import',bigcommerce_store_id,'Processing...',warehouse_id)
            self._cr.commit()
            product_response_pages=[]
            try:
                api_operation="/v3/catalog/products"
                response_data = bigcommerce_store_id.with_user(1).send_get_request_from_odoo_to_bigcommerce(api_operation)
                #_logger.info("BigCommerce Get Product  Response : {0}".format(response_data))
                product_ids = self.with_user(1).search([('bigcommerce_product_id', '=', False)])
                _logger.info("Response Status: {0}".format(response_data.status_code))
                if response_data.status_code in [200, 201]:
                    response_data = response_data.json()
                    #_logger.info("Product Response Data : {0}".format(response_data))
                    records = response_data.get('data')
                    location_id = bigcommerce_store_id.warehouse_id.lot_stock_id
                    total_pages= response_data.get('meta').get('pagination').get('total_pages')

                    to_page = bigcommerce_store_id.source_of_import_data
                    total_pages = bigcommerce_store_id.destination_of_import_data

                    if total_pages > 1:
                        while (total_pages >= to_page):
                            try:
                                page_api = "/v3/catalog/products?page=%s" % (total_pages)
                                page_response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(
                                    page_api)
                                #_logger.info("Response Status: {0}".format(page_response_data.status_code))
                                if page_response_data.status_code in [200, 201]:
                                    page_response_data = page_response_data.json()
                                    _logger.info("Product Response Data : {0}".format(page_response_data))
                                    records = page_response_data.get('data')
                                    product_response_pages.append(records)
                            except Exception as e:
                                product_process_message = "Page is not imported! %s" % (e)
                                _logger.info("Getting an Error In Import Product Category Response {}".format(e))
                                process_message = "Getting an Error In Import Product Category Response {}".format(e)
                                self.with_user(1).create_bigcommerce_operation_detail('product', 'import', response_data,
                                                                         process_message, operation_id,
                                                                         warehouse_id, True, product_process_message)

                            total_pages = total_pages - 1
                    else:
                        product_response_pages.append(records)
                    
                    for product_response_page in product_response_pages:
                        for record in product_response_page:
                            location = []
                            try:
                                if bigcommerce_store_id.bigcommerce_product_skucode and record.get('sku'):
                                    product_template_id = self.env['product.template'].sudo().search(
                                        [('default_code', '=', record.get('sku'))], limit=1)
                                else:
                                    product_template_id = self.env['product.template'].sudo().search([('bigcommerce_product_id','=',record.get('id'))],limit=1)
                                if not product_template_id:
                                    status, product_template_id = self.with_user(1).create_product_template(record,bigcommerce_store_id)
                                    if not status:
                                        product_process_message = "%s : Product is not imported Yet! %s" % (
                                        record.get('id'), product_template_id)
                                        _logger.info("Getting an Error In Import Product Responase :{}".format(product_template_id))
                                        self.with_user(1).create_bigcommerce_operation_detail('product', 'import', "",
                                                                                 "", operation_id,
                                                                                 warehouse_id, True,
                                                                                 product_process_message)
                                        continue
                                    process_message = "Product Created : {}".format(product_template_id.name)
                                    _logger.info("{0}".format(process_message))
                                    response_data = record
                                    self.with_user(1).create_bigcommerce_operation_detail('product','import',req_data,response_data,operation_id,warehouse_id,False,process_message)
                                    self._cr.commit()
                                else:
                                    process_message = "{0} : Product Already Exist In Odoo!".format(product_template_id.name)
                                    category_id = self.env['bigcommerce.category'].sudo().search([('bigcommerce_product_category_id','in',record.get('categories'))])
                                    if not category_id:
                                        message = "Category not found!"
                                        _logger.info("Category not found: {}".format(category_id))
                                        return False, message
                                    brand_id = self.env['bc.product.brand'].sudo().search([('bc_brand_id','=',record.get('brand_id'))],limit=1)
                                    _logger.info("BRAND : {0}".format(brand_id))
                                    availability = False
                                    condition = 'N'
                                    if record.get('availability', False) == 'available':
                                        availability = True
                                    if record.get('is_condition_shown', False):
                                        condition = 'Y'
                                    product_template_id.write({
                                        "list_price": record.get("price"),
                                        "is_visible": record.get("is_visible"),
                                        "bigcommerce_product_id": record.get('id'),
                                        "bigcommerce_category_ids":category_id and [(6,0, category_id.ids)],
                                        "bigcommerce_store_id": bigcommerce_store_id.id,
                                        "default_code": record.get("sku"),
                                        "is_imported_from_bigcommerce": True,
                                        "is_exported_to_bigcommerce": True,
                                        "x_studio_manufacturer":brand_id and brand_id.id,
                                        "name":record.get('name'),
                                        "allow_purchases": availability,
                                        "item_type": record.get('type'),
                                        "product_visible": record.get('is_visible'),
                                        "product_weight": record.get('weight'),
                                        "show_product_condition": record.get('condition'),
                                        "product_type" : record.get('type'),
                                        "vendor_part_numbe" : record.get('mpn'),
                                        "track_inventory" : record.get('inventory_tracking'),
                                        "sort_order" : record.get('sort_order'),
                                        "show_product_condition" : record.get('is_condition_shown'),
                                        "search_keywords" : record.get('search_keywords'),
                                        "product_visible" : record.get('is_visible'),
                                        "product_URL" : record.get('custom_url'),
                                        "product_condition" : record.get('condition'),
                                        "product_availability" :  record.get('availability'),
                                        "page_title" : record.get('page_title'),
                                        "meta_keywords" : record.get('meta_keywords'),
                                        "meta_description" : record.get('meta_description'),
                                        "is_free_shipping" : record.get('is_free_shipping'),
                                        "standard_price": record.get('cost_price'),
                                        "product_depth": record.get('depth'),
                                        "gtin": record.get('gtin'),
                                        "height": record.get('height'),
                                        "inventory_level": record.get('inventory_level'),
                                        "is_featured": record.get('is_featured'),
                                        "option_set_align": record.get('option_set_align'),
                                        "is_preorder_only": record.get('is_preorder_only'),
                                        "is_price_hidden": record.get('is_price_hidden'),
                                        "map_price": record.get("map_price"),
                                        "option_set_display": record.get('option_set_display'),
                                        "order_quantity_maximum": record.get('order_quantity_maximum'),
                                        "order_quantity_minimum": record.get('order_quantity_minimum'),
                                        "price_hidden_label": record.get('price_hidden_label'),
                                        "related_products": record.get('related_products'),
                                        "retail_price": record.get('retail_price'),
                                        "tax_class_id" : record.get('tax_class_id'),
                                        "width" : record.get('width'),
                                        "brand_id" : record.get("brand_id")
                                    })
                                    self.with_user(1).create_bigcommerce_operation_detail('product', 'import', req_data, response_data,operation_id, warehouse_id, False, process_message)
                                    _logger.info("{0}".format(process_message))
                                    self._cr.commit()
                                self.env['bigcommerce.product.image'].with_user(1).import_multiple_product_image(bigcommerce_store_id,product_template_id)
                                location = location_id.ids + location_id.child_ids.ids
                                quant_id = self.env['stock.quant'].with_user(1).search([('product_tmpl_id','=',product_template_id.id),('location_id','in',location)])
                                if len(quant_id) > 1:
                                    stock_quant_id = self.env['stock.quant'].with_user(1).search([('product_tmpl_id','=',product_template_id.id),('location_id','=',location_id.id)])
                                    _logger.info(" Stock Quant : {0}".format(stock_quant_id))
                                    stock_quant_id.with_user(1).unlink()
                                quant_id = self.env['stock.quant'].with_user(1).search([('product_tmpl_id','=',product_template_id.id),('location_id','in',location)])
                                if not quant_id:
                                    product_id = self.env['product.product'].sudo().search([('product_tmpl_id','=',product_template_id.id)],limit=1)
                                    vals = {'product_tmpl_id':product_template_id.id,'location_id':location_id.id,'inventory_quantity':record.get('inventory_level'),'product_id':product_id.id,'quantity':record.get('inventory_level')}
                                    self.env['stock.quant'].sudo().create(vals)
                                else:
                                    quant_id.sudo().write({'inventory_quantity':record.get('inventory_level'),'quantity':record.get('inventory_level')})
                                self._cr.commit()
                            except Exception as e:
                                product_process_message = "%s : Product is not imported Yet! %s" % (record.get('id'),e)
                                _logger.info("Getting an Error In Import Product Responase".format(e))
                                self.with_user(1).create_bigcommerce_operation_detail('product', 'import', "",
                                                                         "", operation_id,
                                                                         warehouse_id, True, product_process_message)

                    operation_id and operation_id.with_user(1).write({'bigcommerce_message': product_process_message})
                    _logger.info("Import Product Process Completed ")
                else:
                    process_message="Getting an Error In Import Product Responase : {0}".format(response_data)
                    _logger.info("Getting an Error In Import Product Responase".format(response_data))
                    self.with_user(1).create_bigcommerce_operation_detail('product','import',req_data,response_data,operation_id,warehouse_id,True,)
            except Exception as e:
                product_process_message = "Process Is Not Completed Yet! %s" % (e)
                _logger.info("Getting an Error In Import Product Responase".format(e))
                self.with_user(1).create_bigcommerce_operation_detail('product','import',"","",operation_id,warehouse_id,True,product_process_message)
            bigcommerce_store_id.bigcommerce_product_import_status = "Import Product Process Completed."
            #product_process_message = product_process_message + "From :" + to_page +"To :" + total_pages
            operation_id and operation_id.with_user(1).write({'bigcommerce_message': product_process_message})
            self._cr.commit()
    
    def import_product_manually_from_bigcommerce(self, warehouse_id=False, bigcommerce_store_id=False,product_id=False):
        headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Auth-Client': '{}'.format(bigcommerce_store_id.bigcommerce_x_auth_client),
                'X-Auth-Token': "{}".format(bigcommerce_store_id.bigcommerce_x_auth_token)
            }
        req_data = False
        product_process_message = "Process Completed Successfully!"
        self._cr.commit()
        product_response_pages=[]
        try:
            api_operation="/v3/catalog/products/{}".format(product_id)
            response_data = bigcommerce_store_id.with_user(1).send_get_request_from_odoo_to_bigcommerce(api_operation)
            _logger.info("Response Status: {0}".format(response_data.status_code))
            if response_data.status_code in [200, 201]:
                response_data = response_data.json()
                record = response_data.get('data')
                location_id = bigcommerce_store_id.warehouse_id.lot_stock_id
                if bigcommerce_store_id.bigcommerce_product_skucode and record.get('sku'):
                    product_template_id = self.env['product.template'].sudo().search(
                        [('default_code', '=', record.get('sku'))], limit=1)
                else:
                    product_template_id = self.env['product.template'].sudo().search([('bigcommerce_product_id','=',record.get('id'))],limit=1)
                if not product_template_id:
                    status, product_template_id = self.with_user(1).create_product_template(record,bigcommerce_store_id)
                    if not status:
                        product_process_message = "%s : Product is not imported Yet! %s" % (record.get('id'), product_template_id)
                        _logger.info("Getting an Error In Import Product Responase :{}".format(product_template_id))
                        raise UserError(product_process_message)
                    process_message = "Product Created : {}".format(product_template_id.name)
                    _logger.info("{0}".format(process_message))
                else:
                    product_name = record.get('name')
                    process_message = "{0} : Product Already Exist In Odoo!".format(product_template_id.name)
                    category_id = self.env['bigcommerce.category'].sudo().search([('bigcommerce_product_category_id','in',record.get('categories'))])
                    if not category_id:
                        message = "Category not found!"
                        _logger.info("Category not found: {}".format(category_id))
                        return False, message
                    brand_id = self.env['bc.product.brand'].sudo().search([('bc_brand_id','=',record.get('brand_id'))],limit=1)
                    _logger.info("BRAND : {0}".format(brand_id))
                    description_sale = html2text.html2text(record.get('description'))
                    availability = False
                    condition = 'N'
                    if record.get('availability', False) == 'available':
                        availability = True
                    if record.get('is_condition_shown', False):
                        condition = 'Y'  
                    product_template_id.write({
                        "list_price": record.get("price"),
                        "is_visible": record.get("is_visible"),
                        "bigcommerce_category_ids":category_id and [(6,0, category_id.ids)],
                        "bigcommerce_product_id": record.get('id'),
                        "bigcommerce_store_id": bigcommerce_store_id.id,
                        "default_code": record.get("sku"),
                        "is_imported_from_bigcommerce": True,
                        "is_exported_to_bigcommerce": True,
                        "name":product_name,
                        "x_studio_manufacturer":brand_id and brand_id.id,
                        "description_sale":description_sale,
                        "allow_purchases": availability,
                        "item_type": record.get('type'),
                        "product_visible": record.get('is_visible'),
                        "product_weight": record.get('weight'),
                        "show_product_condition": record.get('condition'),
                        "product_type" : record.get('type'),
                        "vendor_part_numbe" : record.get('mpn'),
                        "track_inventory" : record.get('inventory_tracking'),
                        "sort_order" : record.get('sort_order'),
                        "show_product_condition" : record.get('is_condition_shown'),
                        "search_keywords" : record.get('search_keywords'),
                        "product_visible" : record.get('is_visible'),
                        "product_URL" : record.get('custom_url'),
                        "product_condition" : record.get('condition'),
                        "product_availability" :  record.get('availability'),
                        "page_title" : record.get('page_title'),
                        "meta_keywords" : record.get('meta_keywords'),
                        "meta_description" : record.get('meta_description'),
                        "is_free_shipping" : record.get('is_free_shipping'),
                        "standard_price": record.get('cost_price'),
                        "product_depth": record.get('depth'),
                        "gtin": record.get('gtin'),
                        "height": record.get('height'),
                        "inventory_level": record.get('inventory_level'),
                        "is_featured": record.get('is_featured'),
                        "option_set_align": record.get('option_set_align'),
                        "is_preorder_only": record.get('is_preorder_only'),
                        "is_price_hidden": record.get('is_price_hidden'),
                        "map_price": record.get("map_price"),
                        "option_set_display": record.get('option_set_display'),
                        "order_quantity_maximum": record.get('order_quantity_maximum'),
                        "order_quantity_minimum": record.get('order_quantity_minimum'),
                        "price_hidden_label": record.get('price_hidden_label'),
                        "related_products": record.get('related_products'),
                        "retail_price": record.get('retail_price'),
                        "tax_class_id" : record.get('tax_class_id'),
                        "width" : record.get('width'),
                        "brand_id" : record.get("brand_id")
                    })
                    _logger.info("{0}".format(process_message))
                    self._cr.commit()
                self.env['product.attribute'].import_product_attribute_from_bigcommerce(warehouse_id,bigcommerce_store_id,product_template_id)
                self.env['bigcommerce.product.image'].sudo().import_multiple_product_image(bigcommerce_store_id,product_template_id)
                location = location_id.ids + location_id.child_ids.ids
                quant_id = self.env['stock.quant'].with_user(1).search([('product_tmpl_id','=',product_template_id.id),('location_id','in',location)])
                if len(quant_id) > 1:
                    stock_quant_id = self.env['stock.quant'].with_user(1).search([('product_tmpl_id','=',product_template_id.id),('location_id','=',location_id.id)])
                    _logger.info(" Stock Quant : {0}".format(stock_quant_id))
                    stock_quant_id.with_user(1).unlink()
                quant_id = self.env['stock.quant'].with_user(1).search([('product_tmpl_id','=',product_template_id.id),('location_id','in',location)])
                if not quant_id:
                    product_id = self.env['product.product'].sudo().search([('product_tmpl_id','=',product_template_id.id)],limit=1)
                    vals = {'product_tmpl_id':product_template_id.id,'location_id':location_id.id,'inventory_quantity':record.get('inventory_level'),'product_id':product_id.id,'quantity':record.get('inventory_level')}
                    self.env['stock.quant'].sudo().create(vals)
                else:
                    quant_id.sudo().write({'inventory_quantity':record.get('inventory_level'),'quantity':record.get('inventory_level')})
                self._cr.commit()
                return {
                    'effect': {
                        'fadeout': 'slow',
                        'message': "Yeah! Successfully Product Imported".format(product_template_id.name),
                        'img_url': '/web/static/src/img/smile.svg',
                        'type': 'rainbow_man',
                    }
                }
        except Exception as e:
            _logger.info("Getting an Error In Import Product Responase".format(e))
            raise UserError("Getting an Error In Import Product Responase".format(e))
