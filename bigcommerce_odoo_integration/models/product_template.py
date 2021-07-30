from odoo import fields, models, api, _
from requests import request
import logging
import json
import requests
import json
import base64
from odoo.exceptions import UserError, ValidationError
import html2text
import re
from odoo.exceptions import Warning
from odoo.osv import expression

_logger = logging.getLogger("BigCommerce")

class ProductProduct(models.Model):
    _inherit = "product.product"
    
    bigcommerce_product_variant_id = fields.Char(string='Bigcommerce Product Variant ID')

    def export_stock_from_odoo_to_bigcommerce(self):
        try:
            if not self.bigcommerce_store_id:
                raise ValidationError("Big commerce store not found fot this product.")
            api_operation = "/v3/catalog/products/{0}/variants/{1}".format(self.bigcommerce_product_id,self.bigcommerce_product_variant_id) if self.bigcommerce_product_variant_id else "/v3/catalog/products/{0}".format(self.bigcommerce_product_id)
            request_data ={"inventory_level": int(self.qty_available)}

            headers = {"Accept": "application/json",
                       "X-Auth-Client": "{}".format(self.bigcommerce_store_id and self.bigcommerce_store_id.bigcommerce_x_auth_client),
                       "X-Auth-Token": "{}".format(self.bigcommerce_store_id and self.bigcommerce_store_id.bigcommerce_x_auth_token),
                       "Content-Type": "application/json"}
            data = json.dumps(request_data)
            url = "{0}{1}{2}".format(self.bigcommerce_store_id.bigcommerce_api_url, self.bigcommerce_store_id.bigcommerce_store_hash, api_operation)
            try:
                _logger.info("Send POST Request From odoo to BigCommerce: {0}".format(url))
                response_data =  request(method='PUT', url=url, data=data, headers=headers)
            except Exception as e:
                _logger.info("Getting an Error in POST Req odoo to BigCommerce: {0}".format(e))
                raise ValidationError(e)
            if response_data.status_code in [200, 201]:
                response_data = response_data.json()
                return {
                    'effect': {
                        'fadeout': 'slow',
                        'message': 'Product Stock Exported : %s' % (self.name),
                        'img_url': '/web/static/src/img/smile.svg',
                        'type': 'rainbow_man',
                    }
                }
            else:
                response_data = response_data.json()
                error_msg = "{0} : {1}".format(self.name, response_data)
                raise ValidationError(error_msg)
        except Exception as e:
            raise ValidationError("Process Is Not Completed Yet!  {}".format(e))

class ProductTemplate(models.Model):
    _inherit = "product.template"

    name = fields.Char('Product Name', index=True, required=False, translate=True)
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
    x_studio_manufacturer = fields.Many2one('bc.product.brand',string='Brand Name')
    bigcommerce_category_ids = fields.Many2many('bigcommerce.category', 'product_big_categ_rel', 'product_id', 'category_id', string="Bigcommerce Category")
    #Added new fields related to big commerce
    allow_purchases = fields.Boolean('Allow Purchases?')
    item_type = fields.Char('Item Type')
    option_set_align = fields.Char('Option Set')
    discontinued = fields.Boolean('Discontinued')
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
    page_title_override = fields.Char('Page Title Override')
    product_availability = fields.Boolean('Availability')
    product_condition = fields.Char('Condition')
    product_URL = fields.Char('Product URL', compute='_compute_product_url',
        store=True)
    manufacturer_URL = fields.Char('Manufacturer URL')
    mpn_URL = fields.Char('MPN URL')
    search_keywords = fields.Text('Search Keywords',
                                  compute='_compute_search_keyword')
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
    # brand_id = fields.Integer("Brand ID")
    free_shipping_override = fields.Char("Free Shipping Override")
    description_override = fields.Char("Description Override")
    search_keywords_override = fields.Char("Search Keywords Override")
    super_pmo = fields.Char("Super PMO")
    pmo = fields.Char("PMO")
    pack_qty = fields.Integer("Pack Qty")
    product_image_file_1 = fields.Char(string="Product Image File - 1")
    product_image_file_overide = fields.Char(string="Product Image File - 1(Override)")
    bigcommerce_product_image_id = fields.Char(related='bigcommerce_product_image_ids.bigcommerce_product_image_id', string="Product Image ID")
    product_image_description_1 = fields.Char('Product Image Description - 1', compute="_compute_product_image_description", store=True, readonly=False)
    image_is_thumbnail = fields.Char("Image Is Thumbnail", default="X")
    image_sort = fields.Char("Image Sort", default=0)
    photos_cloned_from_id = fields.Many2one('product.template', string="Photos Cloned From")
    image_type = fields.Selection([('real', 'Real'),('box', 'Box'), ('child', 'Child'), ('none', 'None')], 'Photo Type', default='real')
    product_URL_final = fields.Char('Product URL Final')
    mpn_URL_final = fields.Char('MPN URL Override')

    search_keyword_ids = fields.One2many('product.search.keyword', 
                    'product_template_id',
                    string="Search Keywords")

    monkey_activator = fields.Selection([('off', 'Off'), ('on', 'On')], 'Monkey Activator', default='off')
    monkey_product_name = fields.Char(string="Monkey Product Name")
    monkey_product_name_override = fields.Char(string="Product Name Override")
    manufacturer_info = fields.Char(string="Manufacturer Info::Web Name")

    def name_get(self):
        if self._context.get('photos_cloned_from'):
            res = []
            for rec in self:
                if rec.default_code:
                    res.append((rec.id, _("%s") %
                                (rec.default_code or '')))
                else:
                    res.append((rec.id, _("%s") %
                                (rec.name or '')))
            return res
        else:
            return super(ProductTemplate, self).name_get()

    @api.onchange('x_studio_manufacturer')
    def onchange_x_studio_manufacturer(self):
        brand_id = self.x_studio_manufacturer.name
        if brand_id:
            res = re.sub('[^A-Za-z0-9]+', '-', brand_id)
            if not res[-1].isalnum():
               self.manufacturer_URL = re.sub('[^A-Za-z0-9]+', '-', brand_id)[:-1]
            else:
                self.manufacturer_URL = re.sub('[^A-Za-z0-9]+', '-', brand_id)
        else:
            self.manufacturer_URL = "MFG-URL-MISSING"

    @api.onchange('vendor_part_number')
    def onchange_vendor_part_number(self):
        vendor_part_number = self.vendor_part_number
        v_part_number = ''
        if vendor_part_number:
            v_part_number = re.sub('[^+A-Za-z0-9]', '-', vendor_part_number)
            if v_part_number:
                res_1= re.sub('[+]', '-PLUS-', v_part_number)
                res = re.sub('\W+','-', res_1)
                v_part_number = res

            if not v_part_number[-1].isalnum():
                v_part_number  = v_part_number[:-1]
            if not v_part_number[0].isalnum():
                v_part_number  = v_part_number[1:]
            self.mpn_URL = v_part_number
            self.mpn_URL_final = v_part_number
        else:
            self.mpn_URL = "MPN-URL-MISSING"
            self.mpn_URL_final = False

    @api.onchange('mpn_URL_final')
    def onchange_mpn_URL_final(self):
        mpn_URL_final = self.mpn_URL_final
        v_mpn_URL_final =''
        if mpn_URL_final:
            v_mpn_URL_final = re.sub('[^+A-Za-z0-9]', '-', mpn_URL_final)
            if v_mpn_URL_final:
                res_1= re.sub('[+]', '-PLUS-', v_mpn_URL_final)
                res = re.sub('\W+','-', res_1)
                v_mpn_URL_final = res
            if not v_mpn_URL_final[-1].isalnum():
                v_mpn_URL_final  = v_mpn_URL_final[:-1]
            if not v_mpn_URL_final[0].isalnum():
                v_mpn_URL_final  = v_mpn_URL_final[1:]
            self.mpn_URL = v_mpn_URL_final

    @api.depends('manufacturer_URL', 'mpn_URL')
    def _compute_product_url(self):
        for rec in self:
            if rec.manufacturer_URL and rec.mpn_URL:
                url = rec.manufacturer_URL + '-' + rec.mpn_URL
                rec.product_URL = "/{}/".format(url)
                rec.product_URL_final = "/{}/".format(url)

    @api.constrains('manufacturer_URL', 'mpn_URL', 'x_studio_manufacturer','vendor_part_number')
    def _check_url_fields(self):
        if self.manufacturer_URL == "MFG-URL-MISSING" and self.mpn_URL == "MPN-URL-MISSING":
            self.product_URL = False
            self.product_URL_final = False
        elif self.manufacturer_URL == "MFG-URL-MISSING" and self.mpn_URL:
            self.product_URL = False
            self.product_URL_final = False
        elif self.manufacturer_URL and self.mpn_URL == "MPN-URL-MISSING":
            self.product_URL = False
            self.product_URL_final = False
        elif not self.manufacturer_URL:
            self.manufacturer_URL = "MFG-URL-MISSING"
        elif not self.mpn_URL:
            self.mpn_URL = "MPN-URL-MISSING"
        if not self.x_studio_manufacturer or not self.vendor_part_number and not self.page_title_override:
            self.page_title = False
        if not self.x_studio_manufacturer or not self.vendor_part_number:
            self.name = False


    @api.depends('search_keyword_ids')
    def _compute_search_keyword(self):
        for rec in self:
            str = ''
            if rec.search_keywords_override:
                override_key = rec.search_keywords_override
                res = re.sub('[^+A-Za-z0-9]', '', override_key)
                if not res[-1].isalnum():
                   override_key = re.sub('[^A-Za-z0-9]', '', override_key)[:-1]
                else:
                    override_key = re.sub('[^A-Za-z0-9]', '', override_key)
                str = override_key
            elif rec.search_keyword_ids:
                for keyword in rec.search_keyword_ids:
                    if not str:
                        str = keyword.name
                    else:
                        str = str +', ' +keyword.name 
            rec.search_keywords = str
            
    @api.model
    def create(self, vals):
        res = super(ProductTemplate, self).create(vals)
        product_image_url = ''
        page_title = ''
        product_name = ''
        if res.product_image_file_overide:
            product_image_url = res.product_image_file_overide
        elif res.photos_cloned_from_id and res.photos_cloned_from_id.product_image_file_1:
            product_image_url = res.photos_cloned_from_id.product_image_file_1
        elif res.default_code:
            product_image_url = 'https://s3.us-east-2.amazonaws.com/jmacimg/' + res.default_code +'-2'+'.jpg'
        if not res.page_title_override:
            if res.vendor_part_number and res.x_studio_manufacturer:
                page_title = res.vendor_part_number + ' - ' + res.x_studio_manufacturer.name
            else:
                page_title = res.page_title_override
        if not res.monkey_activator == 'on' and not res.monkey_product_name_override and not res.manufacturer_info and res.vendor_part_number and res.x_studio_manufacturer:
            product_name = res.x_studio_manufacturer.name + ' ' + res.vendor_part_number
        elif res.monkey_activator == 'on' and res.monkey_product_name:
            product_name = res.monkey_product_name
        elif res.monkey_activator == 'off' and res.monkey_product_name and res.monkey_product_name_override:
            product_name = res.monkey_product_name_override
        elif res.monkey_activator == 'off' and not res.monkey_product_name and not res.monkey_product_name_override and res.manufacturer_info:
            product_name = res.manufacturer_info + ' ' + res.vendor_part_number
        res.write({'product_image_file_1':product_image_url, 'page_title': page_title, 'name': product_name})
            # try:
            #     img_response = requests.get(res.product_image_file_1, timeout=5)
            #     img_response.raise_for_status()
            #     if img_response.status_code == 200:
            #         data = base64.b64encode(img_response.content).replace(
            #             b"\n", b"").decode('ascii')
                    # res.write({'image_1920':data})
            # except Exception as e:
            #     raise Warning(_("Please dont have image in Amazon S3!."))
        return res

    def write(self, vals):
        res_write = super(ProductTemplate, self).write(vals)
        product_image_url = ''
        page_title = ''
        product_name = ''
        if self.product_image_file_overide:
            product_image_url = self.product_image_file_overide
        elif self.photos_cloned_from_id and self.photos_cloned_from_id.product_image_file_1:
            product_image_url = self.photos_cloned_from_id.product_image_file_1
        elif self.default_code:
            product_image_url = 'https://s3.us-east-2.amazonaws.com/jmacimg/' + self.default_code +'-2'+'.jpg'
        if product_image_url and not self._context.get('url_updated', False):
            self.with_context(url_updated=True).write({'product_image_file_1':product_image_url})
        if not self.page_title_override:
            if self.vendor_part_number and self.x_studio_manufacturer:
                page_title = self.vendor_part_number + ' - ' + self.x_studio_manufacturer.name
            else:
                page_title = self.page_title_override
        if self.page_title_override:
            page_title = self.page_title_override
        if page_title and not self._context.get('page_title', False):
            self.with_context(page_title=True).write({'page_title':page_title})

        if not self.monkey_activator == 'on' and not self.monkey_product_name_override and not self.manufacturer_info and self.vendor_part_number and self.x_studio_manufacturer:
            product_name = self.x_studio_manufacturer.name + ' ' + self.vendor_part_number
        elif self.monkey_activator == 'on' and self.monkey_product_name:
            product_name = self.monkey_product_name
        elif self.monkey_activator == 'off' and self.monkey_product_name and self.monkey_product_name_override:
            product_name = self.monkey_product_name_override
        elif self.monkey_activator == 'off' and not self.monkey_product_name and not self.monkey_product_name_override and self.manufacturer_info:
            product_name = self.manufacturer_info + ' ' + self.vendor_part_number
        if product_name and not self._context.get('product_name', False):
            self.with_context(product_name=True).write({'name':product_name})
        if  vals.get('mpn_URL') and self.vendor_part_number:
            mpn_url = vals.get('mpn_URL')
            res = re.sub('[^+A-Za-z0-9]', '', mpn_url)
            if not res[-1].isalnum():
               mpn_url = re.sub('[^A-Za-z0-9]', '', mpn_url)[:-1]
            else:
                mpn_url = re.sub('[^A-Za-z0-9]', '', mpn_url)
            v = {'name': mpn_url,
                     'product_template_id': self.id}
            self.env['product.search.keyword'].create(v)
        return res_write

    @api.constrains('default_code')
    def check_default_code(self):
        for record in self:
            if len(self.search([('default_code', '=', record.default_code),
                            ('id', '!=', record.id)], limit=1)) == 1 and record.default_code:
                    raise ValidationError(_("%s default code is already exist...!" % record.default_code))
        #     if self.env.context.get('from_aws_url'):
    #         return
    #     if self.product_image_file_overide:
    #         try:
    #             img_response = requests.get(self.product_image_file_overide, timeout=5)
    #             img_response.raise_for_status()
    #             if img_response.status_code == 200:
    #                 data = base64.b64encode(img_response.content).replace(
    #                     b"\n", b"").decode('ascii')
    #                 self.write({'image_1920':data})
    #         except Exception as e:
    #             raise Warning(_(e))
    #     else:
    #         self.write({'image_1920':False})

    # @api.onchange('product_image_file_1')
    # def onchange_product_image_file_1(self):
    #     if self.product_image_file_1:
    #         try:
    #             img_response = requests.get(self.product_image_file_1, timeout=5)
    #             img_response.raise_for_status()
    #             if img_response.status_code == 200:
    #                 data = base64.b64encode(img_response.content).replace(
    #                     b"\n", b"").decode('ascii')
    #                 res.write({'image_1920':data})
    #         except Exception as e:
    #             raise Warning(_(e))
    #     else:
    #         self.product_image_file_1 = False

    @api.onchange('product_image_file_overide')
    def onchange_product_image_file_override(self):
        if self.product_image_file_overide:
            self.product_image_file_1 = self.product_image_file_overide
        else:
            self.product_image_file_1 = False
    
    @api.onchange('photos_cloned_from_id')
    def onchange_photos_cloned_from_id(self):
        if self.photos_cloned_from_id.product_image_file_1:
            if not self.product_image_file_overide:
                self.product_image_file_1 = 'https://s3.us-east-2.amazonaws.com/jmacimg/' + self.photos_cloned_from_id.default_code +'-2'+'.jpg'
            # else:
                # raise ValidationError("Product Image File Overide All Ready Exist!")
            # raise Warning(_("Please dont have image in Amazon S3!."))

            # product_template_id = self.env['product.template'].search(
            #                             [('default_code', '=', self.photos_cloned_from_id.default_code)], limit=1)
            # try:
            #     img_response = requests.get(product_template_id.product_image_file_1, timeout=5)
            #     img_response.raise_for_status()
            #     if img_response.status_code == 200:
            #         data = base64.b64encode(img_response.content).replace(
            #             b"\n", b"").decode('ascii')
            #         self.write({'image_1920':product_template_id.image_1920, 'product_image_file_1': product_image_file_1})
            # except Exception as e:
            #     raise Warning(_(e))
        # else:
        #     self.write({'image_1920':False})

    @api.depends('x_studio_manufacturer', 'vendor_part_number')
    def _compute_product_image_description(self):
        for rec in self:
            company_id = self.env.company
            if rec.x_studio_manufacturer and rec.vendor_part_number and company_id:
                self.product_image_description_1 = rec.vendor_part_number +' by '+ rec.x_studio_manufacturer.name +' | '+ company_id.name
            else:
                self.product_image_description_1 = False

    def export_stock_from_odoo_to_bigcommerce(self):
        raise ValidationError("Kindly Export product using product variant menu!")

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
        if warehouse_id:
            qty_available = product_id.with_context(warehouse=warehouse_id.id).qty_available
        else:
            qty_available = product_id.qty_available

        if product_id.product_URL:
            product_url = product_id.product_URL
        else:
            raise ValidationError("PRODUCT-URL-MISSING")
        product_data = {
            "name": product_id.name,
            "price": product_id.list_price,
            "categories": product_id.bigcommerce_category_ids and product_id.bigcommerce_category_ids.mapped("bigcommerce_product_category_id"),
            "weight": product_id.weight or 1.0,
            "type": "physical",
            "sku":product_id.default_code or '',
            "description":product_id.name,
            "cost_price":product_id.standard_price,
            "inventory_tracking":product_id.inventory_tracking,
            "inventory_level":int(qty_available),
            "is_visible":product_id.is_visible,
            "warranty":product_id.warranty or '',
            "custom_url": {"url": "{}".format(product_url),"is_customized": False}
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

    def export_bulk_product_to_bigcommerce(self):
        if self._context.get('active_model') == 'product.template':
            product_ids = self.env.context.get('active_ids')
            product_objs = self.env['product.template'].browse(product_ids)
            self.export_product_to_bigcommerce(bigcommerce_store_ids= product_objs.bigcommerce_store_id,new_product_id=product_objs, warehouse_id=product_objs.bigcommerce_store_id.warehouse_id)
            # product_objs.write({'is_exported_to_bigcommerce':True})
        return

    def export_update_product_to_bigcommerce(self):
        bigcommerce_store_id = self.bigcommerce_store_id
        bigcommerce_product_id = self.bigcommerce_product_id
        if self.is_exported_to_bigcommerce:
            try:
                if not bigcommerce_store_id:
                    raise ValidationError("Big commerce store not found fot this order.")
                api_url ='%s%s/v3/catalog/products/%s'%(bigcommerce_store_id.bigcommerce_api_url,bigcommerce_store_id.bigcommerce_store_hash, bigcommerce_product_id)
                product_id = self
                product_name = product_id and product_id.name
                if self.warehouse_id:
                    qty_available = product_id.with_context(warehouse=self.warehouse_id.id).qty_available
                else:
                    qty_available = product_id.qty_available

                request_data = {
                    "name": product_id.name,
                    "price": product_id.list_price,
                    "categories": product_id.bigcommerce_category_ids and product_id.bigcommerce_category_ids.mapped("bigcommerce_product_category_id"),
                    "weight": product_id.weight or 1.0,
                    "type": "physical",
                    "sku":product_id.default_code or '',
                    "description":product_id.name,
                    "cost_price":product_id.standard_price,
                    "inventory_tracking":product_id.inventory_tracking,
                    "inventory_level":int(qty_available),
                    "is_visible":product_id.is_visible,
                    "warranty":product_id.warranty or ''
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
                            'message': 'Update Product Exported : %s' % (self.name),
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
            raise ValidationError("Please First Export This Product Then Try To Update Product.!!!!")

    def export_product_to_bigcommerce(self, warehouse_id=False, bigcommerce_store_ids=False,new_product_id=False):
        for bigcommerce_store_id in bigcommerce_store_ids:
            product_process_message = "Process Completed Successfully!"
            bigcommerce_operation_details_obj = self.env['bigcommerce.operation.details']
            operation_id = self.env['bigcommerce.operation']
            if not operation_id:
                operation_id = self.create_bigcommerce_operation('product','export',bigcommerce_store_id,'Processing...',warehouse_id)
            try:
                if not new_product_id:
                    product_ids = self.search([('bigcommerce_product_id','=',False),('is_exported_to_bigcommerce','=',False)])
                else:
                    product_ids = new_product_id
                _logger.info("List of Products Need to Export: {0}".format(product_ids))
                for product_id in product_ids:
                    if warehouse_id:
                        product_request_data = self.product_request_data(product_id,warehouse_id)
                    else:
                        product_request_data = self.product_request_data(product_id)
                    api_operation="/v3/catalog/products"
                    response_data=bigcommerce_store_id.send_request_from_odoo_to_bigcommerce(product_request_data,api_operation)
                    _logger.info("Status Code of Export Product : {0}".format(response_data.status_code))
                    if response_data.status_code in [200, 201]:
                        response_data = response_data.json()
                        _logger.info("Product Response Data : %s" % (response_data))
                        if response_data.get('data') and response_data.get('data').get("id"):
                            bigcommerce_product_id = response_data.get('data').get("id")
                            product_id.bigcommerce_product_id=bigcommerce_product_id
                            product_id.bigcommerce_store_id=bigcommerce_store_id.id
                            product_id.is_exported_to_bigcommerce = True
                            process_message="{0} : Product Operation Sucessfully Completed".format(product_id.name)
                            self.create_bigcommerce_operation_detail('product','export',product_request_data,response_data,operation_id,warehouse_id,False,process_message)
                            product_variant_option = "/v3/catalog/products/{}/variants".format(product_id.bigcommerce_product_id)
                        else:
                            process_message="{0} : {1}".format(product_id.name, response_data)
                            self.create_bigcommerce_operation_detail('product','export',product_request_data,response_data,operation_id,warehouse_id,True,response_data)
                    else:
                        response_data = response_data.json()
                        process_message = "{0} : {1}".format(product_id.name ,response_data.get('errors'))
                        self.create_bigcommerce_operation_detail('product','export',product_request_data,process_message,operation_id,warehouse_id,True,process_message)
                    self._cr.commit()
            except ValidationError as e:
                raise
            except Exception as e:
                product_process_message = "Process Is Not Completed Yet!  {}".format(e)
                self.create_bigcommerce_operation_detail('product','export',product_request_data,response_data,operation_id,warehouse_id,True,product_process_message)
            operation_id and operation_id.write({'bigcommerce_message': product_process_message})
            self._cr.commit()

    def delete_product_odoo_to_bigcommerce(self):
        bigcommerce_store_id = self.bigcommerce_store_id
        bigcommerce_product_id = self.bigcommerce_product_id
        if self.is_exported_to_bigcommerce:
            try:
                if not bigcommerce_store_id:
                    raise ValidationError("Big commerce store not found fot this order.")
                api_url ='%s%s/v3/catalog/products/%s'%(bigcommerce_store_id.bigcommerce_api_url,bigcommerce_store_id.bigcommerce_store_hash, bigcommerce_product_id)
                product_id = self
                request_data = {
                    "product_id": product_id.bigcommerce_product_id
                }
                headers = {"Accept": "application/json",
                           "X-Auth-Client": "{}".format(bigcommerce_store_id and bigcommerce_store_id.bigcommerce_x_auth_client),
                           "X-Auth-Token": "{}".format(bigcommerce_store_id and bigcommerce_store_id.bigcommerce_x_auth_token),
                           "Content-Type": "application/json"}
                data = json.dumps(request_data)
                url = "{0}".format(api_url)
                product_id.bigcommerce_product_id = False
                product_id.is_exported_to_bigcommerce = False
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
                            'message': 'Delete Product : %s' % (self.name),
                            'img_url': '/web/static/src/img/smile.svg',
                            'type': 'rainbow_man',
                        }
                    }
            except Exception as e:
                raise ValidationError("Process Is Not Completed Yet!  {}".format(e))

    def export_product_variant_to_bigcommerce(self, warehouse_id=False, bigcommerce_store_ids=False):
        for bigcommerce_store_id in bigcommerce_store_ids:
            product_process_message = "Process Completed Successfully!"
            operation_id = self.env['bigcommerce.operation']
            if not operation_id:
                operation_id = self.create_bigcommerce_operation('product_variant','export',bigcommerce_store_id,'Processing...',warehouse_id)
            try:
                product_ids = self.search([('product_variant_ids','!=',False),('bigcommerce_product_id','!=',False),('is_exported_to_bigcommerce','=',True),('product_variant_ids.attribute_value_ids','!=',False)])
                _logger.info("List of Products Need to Export: {0}".format(product_ids))
                for product_id in product_ids:
                    for product_variant in product_id.product_variant_ids:
                        product_variant_request_data = self.product_variant_request_data(product_variant)
                        variant_api_operation="/v3/catalog/products/{}/variants".format(product_id.bigcommerce_product_id)
                        response_data=bigcommerce_store_id.send_request_from_odoo_to_bigcommerce(product_variant_request_data,variant_api_operation)
                        if response_data.status_code in [200, 201]:
                            response_data = response_data.json()
                            _logger.info("Attribute Response Data : %s" % (response_data))
                            if response_data.get('data') and response_data.get('data').get("id"):
                                bigcommerce_product_variant_id = response_data.get('data').get("id")
                                product_variant.bigcommerce_product_variant_id = bigcommerce_product_variant_id
                                for option_value in response_data.get('data').get('option_values'):
                                    attribute_value = self.env['product.attribute.value'].search([('name','=',option_value.get('label'))],limit=1)
                                    attribute_value.bigcommerce_value_id = option_value.get('id')
                                process_message="{0} : Variant Added/Changed".format(product_variant.name)
                                self.create_bigcommerce_operation_detail('product_variant','export',product_variant_request_data,response_data,operation_id,warehouse_id,False,process_message)
                        else:
                            response_data = response_data.json()
                            error_msg = "{0} : {1}".format(product_variant.name,response_data.get('errors'))
                            self.create_bigcommerce_operation_detail('product_variant','export',product_variant_request_data,error_msg,operation_id,warehouse_id,True,error_msg)
            except Exception as e:
                product_process_message = "Process Is Not Completed Yet!  {}".format(e)
                self.create_bigcommerce_operation_detail('product_variant','export',"","",operation_id,warehouse_id,True,product_process_message)
            operation_id and operation_id.write({'bigcommerce_message': product_process_message})
            self._cr.commit()
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
                "vendor_part_number" : record.get('mpn'),
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
                                        "vendor_part_number" : record.get('mpn'),
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
                        "vendor_part_number" : record.get('mpn'),
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