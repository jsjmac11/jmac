import math
import html
import time
from odoo import models, fields, api
from odoo.exceptions import Warning
from datetime import datetime, timedelta
from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT
import logging
_logger = logging.getLogger(__name__)

class amazon_product_ept(models.Model):
    _name = "amazon.product.ept"
    _description = "Amazon Product Mapping with Odoo Products"

    name = fields.Char("Name")
    product_id = fields.Many2one('product.product', string='Odoo Product', ondelete="cascade",
                                 help="ERP Product Reference")
    instance_id = fields.Many2one('amazon.instance.ept', string='Instance', required=True,
                                  copy=False, help="Recognise Products to unique Amazon Instances")
    product_asin = fields.Char("Product ASIN", copy=False, help="Amazon Product ASIN")
    asin_qty = fields.Integer("Number Of Items In One Package", default=1,
                              help="Amazon Product's Number of Quantity in One Packet")
    product_upc = fields.Char("UPC", copy=False)
    fulfillment_by = fields.Selection(
        [('FBM', 'Manufacturer Fulfillment Network'), ('FBA', 'Amazon Fulfillment Network')],
        string="Fulfillment By", default='FBM', help="Amazon Fulfillment Type")
    fix_stock_type = fields.Selection([('fix', 'Fix'), ('percentage', 'Percentage')],
                                      string='Fix Stock Type')
    fix_stock_value = fields.Float(string='Fix Stock Value', digits="Product UoS")
    exported_to_amazon = fields.Boolean("Exported In Amazon", default=False, copy=False,
                                        help="True:Product exported to Amazon or False: Product is not exported to Amazon.")
    title = fields.Char("Title", help="Short description of the product")
    seller_sku = fields.Char("Seller Sku", help="Amazon Seller SKU")
    barcode = fields.Char("Barcode", related="product_id.barcode")
    long_description = fields.Text("Product Description", help="Long description of the product")
    active = fields.Boolean("Active", related="product_id.active")
    fulfillment_channel_sku = fields.Char('Fulfillment Channel SKU')
    last_feed_submission_id = fields.Char("Last Feed Submission Id", readonly=True, copy=False)
    error_in_export_product = fields.Boolean("Error In Export Product", default=False, copy=False)
    shipping_template_id = fields.Many2one('amazon.product.shipping.template', string='Shipping Template', copy=False)
    _sql_constraints = [('amazon_instance_seller_sku_unique_constraint',
                         'unique(instance_id,seller_sku,fulfillment_by)',
                         "Seller sku must be unique per instance & Fulfullment By")]

    @api.model
    def search_product(self, seller_sku):
        product_obj = self.env['product.product']
        if self.env.ref('product.product_comp_rule').active == True:
            cur_usr = self.env.user
            company_id = cur_usr.company_id.id or False
            product = product_obj.search(
                ['|', ('company_id', '=', False), ('company_id', '=', company_id),
                 ('default_code', '=', seller_sku)])
            if len(product) > 1:
                raise Warning('Duplicate Product Found For Sku (%s)' % (seller_sku))
            if not product:
                product = product_obj.search(
                    ['|', ('company_id', '=', False), ('company_id', '=', company_id),
                     ('default_code', '=', seller_sku), ('active', '=', False)])
                if len(product) > 1:
                    raise Warning('Duplicate Product Found For Sku (%s)' % (seller_sku))
                if product and product.active == False:
                    product.write({'active': True})
            return product or False
        else:
            product = product_obj.search([('default_code', '=', seller_sku)])
            if len(product) > 1:
                raise Warning('Duplicate Product Found For Sku (%s)' % (seller_sku))
            if not product:
                product = product_obj.search(
                    [('default_code', '=', seller_sku), ('active', '=', False)])
                if len(product) > 1:
                    raise Warning('Duplicate Product Found For Sku (%s)' % (seller_sku))
                if product and product.active == False:
                    product.write({'active': True})
            return product or False

    @api.model
    def search_amazon_product(self, instance_id, seller_sku, fulfillment_by='FBM'):
        seller_sku = seller_sku.strip()
        amazon_product = self.search(
            ['|', ('active', '=', False), ('active', '=', True), ('seller_sku', '=', seller_sku),
             ('instance_id', '=', instance_id), ('fulfillment_by', '=', fulfillment_by)], limit=1)
        if not amazon_product:
            return False
        if amazon_product.product_id and not amazon_product.product_id.active:
            amazon_product.product_id.write({'active': True})
        return amazon_product

    standard_product_id_type = fields.Selection([('EAN', 'EAN'), ('ASIN', 'ASIN'), ('GTIN', 'GTIN'), ('UPC', 'UPC')],
                                                string="Standard Product ID", default='ASIN')
    related_product_type = fields.Selection([('UPC', 'UPC'), ('EAN', 'EAN'), ('GTIN', 'GTIN')])
    related_product_value = fields.Char("Related Product Value")
    launch_date = fields.Datetime("Launch Date",
                                  help="Controls when the product appears in search and "
                                       "browse on the Amazon website")
    release_date = fields.Datetime("Release Date", help="The date a product is released for sale")
    discontinue_date = fields.Datetime("Discontinue Date",
                                       help="The date a product is Discontinue for sale")
    condition = fields.Selection([('New', 'New'),
                                  ('UsedLikeNew', 'UsedLikeNew'),
                                  ('UsedVeryGood', 'UsedVeryGood'),
                                  ('UsedGood', 'UsedGood'),
                                  ('CollectibleLikeNew', 'CollectibleLikeNew'),
                                  ('CollectibleVeryGood', 'CollectibleVeryGood'),
                                  ('CollectibleGood', 'CollectibleGood'),
                                  ('CollectibleAcceptable', 'CollectibleAcceptable'),
                                  ('Club', 'Club')], string="Condition", default='New', copy=False)

    item_package_qty = fields.Integer(string="Item Package Quantity", default=1,
                                      help="Number of the same product contained within"
                                           " one package. "
                                           "For example, "
                                           "if you are selling a case of 10 packages of socks, "
                                           "ItemPackageQuantity would be 10.")

    brand = fields.Char(string="Product Brand",
                        related='product_id.product_tmpl_id.product_brand_id.name', readonly=True)
    designer = fields.Char("Designer", help="Designer of the product")

    bullet_point_ids = fields.One2many('amazon.product.bullet.description', 'amazon_product_id',
                                       string="Bullet Point Description")

    package_weight = fields.Float("Package Weight", help="Weight of the package", digits="Stock Weight")
    shipping_weight = fields.Float("Shipping Weight", help="Weight of the product when packaged to ship",
                                   digits="Stock Weight")
    max_order_quantity = fields.Integer("Max Order Quantity",
                                        help="Maximum quantity of the product that a customer can order")

    manufacturer = fields.Char(string="Manufacturer",
                               related='product_id.product_tmpl_id.product_brand_id.partner_id.name', readonly=True)

    search_term_ids = fields.One2many('amazon.product.search.term', 'amazon_product_id', string="Search Term")
    is_gift_wrap_available = fields.Boolean("Is Gift Wrap Available ?",
                                            help="Indicates whether gift wrapping is available for the product")

    is_gift_message_available = fields.Boolean("Is Gift Message Available ?",
                                               help="Indicates whether gift messaging is available for the product")
    gtin_exemption_reason = fields.Selection([('bundle', 'Bundle'), ('part', 'Part')], string="GtinExemptionReason")
    package_weight_uom = fields.Selection(
        [('GR', 'GR'), ('KG', 'KG'), ('OZ', 'OZ'), ('LB', 'LB'), ('MG', 'MG')], default='KG',
        string="Package Weight Uom")

    shipping_weight_uom = fields.Selection(
        [('GR', 'GR'), ('KG', 'KG'), ('OZ', 'OZ'), ('LB', 'LB'), ('MG', 'MG')], default='KG',
        string="Shipping Weight Uom")
    item_dimensions_uom = fields.Selection(
        [('CM', 'CM'), ('FT', 'FT'), ('M', 'M'), ('IN', 'IN'), ('MM', 'MM')], string="Item Dimension", default='CM')

    item_height = fields.Float("Item Height", help="Height of the item dimension", digits="Stock Height")
    item_length = fields.Float("Item Length", help="Length of the item dimension", digits="Stock Height")
    item_width = fields.Float("Item Width", help="Width of the item dimension", digits="Stock Height")

    package_dimensions_uom = fields.Selection(
        [('CM', 'CM'), ('FT', 'FT'), ('M', 'M'), ('IN', 'IN'), ('MM', 'MM')], string="Package Dimension", default='CM')
    package_height = fields.Float("Package Height", help="Height of the package dimension", digits="Stock Height")
    package_length = fields.Float("Package Length", help="Length of the package dimension", digits="Stock Height")
    package_width = fields.Float("Package Width", help="Width of the package dimension", digits="Stock Height")
    allow_package_qty = fields.Boolean("Allow Package Qty", default=False)
    fulfillment_latency = fields.Integer('Fullfillment Latency')

    def export_product_amazon(self, instance):
        """
        This Method Relocates export amazon product listing in amazon.
        :param instance:This argument relocates instance of amazon.
        :param amazon_products:This argument relocates amazon product listing of amazon.
        :return: This Method return Boolean(True/False).
        """
        feed_submission_obj = self.env['feed.submission.history']
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        data = self.create_product_envelope(instance)
        kwargs = {'merchant_id': instance.merchant_id and str(instance.merchant_id) or False,
                  'auth_token': instance.auth_token and str(instance.auth_token) or False,
                  'app_name': 'amazon_ept',
                  'account_token': account.account_token,
                  'emipro_api': 'export_product_amazon_v13',
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': instance.country_id.amazon_marketplace_code or
                                             instance.country_id.code,
                  'data': data,
                  'instance_id': instance.id, }
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(response.get('reason'))
        else:
            results = response.get('result')
        last_feed_submission_id = False
        if results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get('value', False):
            last_feed_submission_id = results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId',
                                                                                {}).get('value',
                                                                                        False)
            for amazon_product in self:
                amazon_product.write(
                    {'exported_to_amazon': True, 'last_feed_submission_id': last_feed_submission_id,
                     'error_in_export_product': False})

            vals = {'message': data, 'feed_result_id': last_feed_submission_id,
                    'feed_submit_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'instance_id': instance.id, 'user_id': self._uid,
                    'feed_type': 'export_product',
                    'seller_id': instance.seller_id.id}
            feed = feed_submission_obj.create(vals)
        return True

    def create_product_envelope(self, instance):
        """
        This Method relocates prepare envelope for amazon.
        :param amazon_products: This arguments relocates product listing of amazon.
        :param instance: This argument relocates instance of amazon.
        :return: This argument return envelope of amazon.
        """
        message_id = 0
        messages = ''
        for product in self:
            message_id = message_id + 1
            messages = "%s %s" % (messages, self.get_message(message_id, product))
        header = self.get_header(instance)
        data = "%s %s %s" % (header, messages, '</AmazonEnvelope>')
        return data

    def get_message(self, message_id, product):
        """
        This Method relocates prepare envelop message for amazon product.
        :param message_id:This argument relocates message id of amazon because of amazon depends on message id.
        :param product:This arguments relocates product listing of amazon
        :return: This Method return amazon envelope message.
        """
        message = """
                <MessageID>%s</MessageID>
                <OperationType>PartialUpdate</OperationType>
                <Product>""" % (message_id)
        message = "%s %s" % (message, self.standard_product_code(product))
        if product.standard_product_id_type == 'GTIN':
            message = "%s %s" % (message, "<GtinExemptionReason>%s</GtinExemptionReason>" % (
                product.gtin_exemption_reason))
        if product.related_product_type:
            message = "%s %s" % (message, self.get_related_product_type(product))

        luanch_date = self.get_lanuch_date(product)
        if luanch_date:
            message = "%s %s" % (message, luanch_date)
        discontinue_date = self.get_discontinue_date(product)
        if discontinue_date:
            message = "%s %s" % (message, discontinue_date)
        release_date = self.get_release_date(product)
        if release_date:
            message = "%s %s" % (message, release_date)
        condition = self.get_condition(product)
        if condition:
            message = "%s %s" % (message, condition)
        message = "%s %s" % (message, self.item_package_qty_and_no_of_items(product))
        description_data = self.get_description_data(product)
        message = "%s %s" % (message, description_data)

        item_dimension = self.get_item_dimension(product)
        if item_dimension:
            message = "%s %s" % (message, item_dimension)

        package_dimension = self.get_package_dimension(product)
        if package_dimension:
            message = "%s %s" % (message, package_dimension)

        amazon_only = "<Amazon-Only>"
        if len(amazon_only) > 14:
            amazon_only = "%s %s" % (amazon_only, "</Amazon-Only>")
            message = "%s %s" % (message, amazon_only)
        message = "%s </Product>" % (message)
        return "<Message>%s</Message>" % (message)

    def get_header(self, instnace):
        """
        This Method relocates prepare header of envelope for amazon product listing.
        :param instnace: This argument relocates instance of amazon.
        :return: This Method return header of envelope for amazon product listing.
        """
        return """<?xml version="1.0"?>
            <AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
            <Header>
                <DocumentVersion>1.01</DocumentVersion>
                <MerchantIdentifier>%s</MerchantIdentifier>
            </Header>
            <MessageType>Product</MessageType>
            <PurgeAndReplace>false</PurgeAndReplace>
         """ % (instnace.merchant_id)

    def standard_product_code(self, product):
        """
        This Method prepare envelope message of standard product type for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return standard product type envelope message for amazon.
        """
        product_code, product_type = '', ''
        if product.standard_product_id_type in ['GTIN']:
            return """<SKU>%s</SKU>
                       """ % (product.seller_sku)
        if product.standard_product_id_type == 'ASIN':
            product_code, product_type = product.product_asin, 'ASIN'
        elif product.standard_product_id_type == 'EAN':
            product_code, product_type = product.barcode, 'EAN'
        elif product.standard_product_id_type == 'GTIN':
            product_code, product_type = product.product_upc, 'GTIN'
        elif product.standard_product_id_type == 'UPC':
            product_code, product_type = product.product_upc, 'UPC'
        return """<SKU>%s</SKU>
                         <StandardProductID>
                             <Type>%s</Type>
                             <Value>%s</Value>
                         </StandardProductID>
                       """ % (product.seller_sku, product_type, product_code)

    def get_lanuch_date(self, product):
        """
        This Method prepare envelope message of lunch date for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return lunch date envelope message for amazon.
        """
        launch_date = product.launch_date and datetime.strftime(product.launch_date,
                                                                "%Y-%m-%d %H:%M:%S") or False
        return launch_date and " <LaunchDate>%s</LaunchDate>" % (launch_date) or False

    def get_related_product_type(self, product):
        """
        This Method prepare envelope message of related product type for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return related product type envelope message for amazon.
        """
        return """<RelatedProductID>
                          <Type>%s</Type>
                          <Value>%s</Value>
                      </RelatedProductID>""" % (
            product.related_product_type, product.related_product_value)

    def get_discontinue_date(self, product):
        """
        This Method prepare envelope message of discontinue date for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return discontinue date envelope message for amazon.
        """
        discontinue_date = product.discontinue_date and datetime.strftime(product.discontinue_date,
                                                                          "%Y-%m-%d %H:%M:%S") or False
        return discontinue_date and " <DiscontinueDate>%s</DiscontinueDate>" % (
            discontinue_date) or False

    def get_release_date(self, product):
        """
        This Method prepare envelope message of release date for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return release date envelope message for amazon.
        """
        release_date = product.release_date and datetime.strftime(product.release_date,
                                                                  "%Y-%m-%d %H:%M:%S") or False
        return release_date and " <ReleaseDate>%s</ReleaseDate>" % (release_date) or False

    def get_item_dimension(self, product):
        """
        This Method prepare envelope message of item dimension for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return item dimension envelope message for amazon.
        """
        if product.item_dimensions_uom:
            return """
                    <ItemDimensions>
                        <Length unitOfMeasure='%s'>%s</Length>
                        <Width unitOfMeasure='%s'>%s</Width>
                        <Height unitOfMeasure='%s'>%s</Height>

                    </ItemDimensions>
                    """ % (
                product.item_dimensions_uom, str(round(float(product.item_length), 2)), product.item_dimensions_uom,
                str(round(float(product.item_width), 2)), product.item_dimensions_uom,
                str(round(float(product.item_width), 2)))

    def get_package_dimension(self, product):
        """
        This Method prepare envelope message of package dimension for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return package dimension envelope message for amazon.
        """
        if product.package_dimensions_uom:
            return """
                    <PackageDimensions>
                        <Length unitOfMeasure='%s'>%s</Length>
                        <Width unitOfMeasure='%s'>%s</Width>
                        <Height unitOfMeasure='%s'>%s</Height>

                    </PackageDimensions>
                    """ % (
                product.package_dimensions_uom, str(round(float(product.package_length), 2)),
                product.item_dimensions_uom,
                str(round(float(product.package_width), 2)), product.item_dimensions_uom,
                str(round(float(product.package_width), 2)))

    def get_condition(self, product):
        """
        This Method prepare envelope message of condition for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return condition envelope message for amazon.
        """
        if product.condition:
            return """
                        <Condition>
                            <ConditionType>%s</ConditionType>
                        </Condition>
                        """ % (product.condition)
        else:
            return False

    def item_package_qty_and_no_of_items(self, product):
        """
        This Method prepare envelope message of item package qty and no of items for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return item package qty and no of items envelope message for amazon.
        """
        item_pack = ''
        if product.item_package_qty > 0:
            item_pack = "%s %s" % (
                item_pack,
                "<ItemPackageQuantity>%s</ItemPackageQuantity>" % (product.item_package_qty))
        if product.asin_qty > 0:
            item_pack = "%s %s" % (
                item_pack, "<NumberOfItems>%s</NumberOfItems>" % (product.asin_qty))
        return item_pack

    def get_description_data(self, product):
        """
        This Method prepare envelope message of description data for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return description data envelope message for amazon.
        """
        data = []
        if product.title:
            data.append("<Title>%s</Title>" % (html.escape(product.title)))  # .encode("utf-8")
        else:
            data.append("<Title>%s</Title>" % (
                html.escape(product.name)))  # .encode("utf-8")
        product.brand and data.append(
            "<Brand>%s</Brand>" % (html.escape(product.brand)))  # .encode("utf-8")
        product.designer and data.append(
            "<Designer>%s</Designer>" % (html.escape(product.designer)))  # .encode("utf-8")
        description = product.long_description or False
        description and data.append("<Description>%s</Description>" % (html.escape(description)))

        product.bullet_point_ids and data.append(self.get_bullet_points(product))
        if product.package_weight > 0.0:
            data.append("""<PackageWeight unitOfMeasure='%s'>%s</PackageWeight>""" % (
                product.package_weight_uom, str(round(float(product.package_weight), 2))))

        if product.shipping_weight > 0.0:
            data.append("""<ShippingWeight unitOfMeasure='%s'>%s</ShippingWeight>""" % (
                product.shipping_weight_uom, str(round(float(product.shipping_weight), 2))))
        if product.max_order_quantity > 0:
            data.append("<MaxOrderQuantity>%s</MaxOrderQuantity>" % (product.max_order_quantity))
        product.manufacturer and data.append(
            "<Manufacturer>%s</Manufacturer>" % (html.escape(product.manufacturer)))  # .encode("utf-8")
        product.search_term_ids and data.append(self.get_search_terms(product))
        data.append("<IsGiftWrapAvailable>%s</IsGiftWrapAvailable>" % (
            str(product.is_gift_wrap_available).lower()))
        data.append("<IsGiftMessageAvailable>%s</IsGiftMessageAvailable>" % (
            str(product.is_gift_message_available).lower()))

        description_data = ''
        for tag in data:
            description_data = "%s %s" % (description_data, tag)
        return "<DescriptionData>%s</DescriptionData>" % (str(description_data))

    def get_search_terms(self, product):
        """
        This Method prepare envelope message of search term for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return search term envelope message for amazon.
        """
        search_terms = ''
        for search_term in product.search_term_ids:
            search_term = """<SearchTerms>%s</SearchTerms>""" % (html.escape(search_term.name))
            search_terms = "%s %s" % (search_terms, search_term)
        return search_terms

    def get_bullet_points(self, product):
        """
        This Method prepare envelope message of bullet points description for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return bullet points description envelope message for amazon.
        """
        bullet_points = ''
        for bullet in product.bullet_point_ids:
            bullet_point = """<BulletPoint>%s</BulletPoint>""" % (html.escape(bullet.name))
            bullet_points = '%s %s' % (bullet_points, bullet_point)
        if product.bullet_point_ids:
            return bullet_points

    def process_export_stock_message_info_ept(self, instance, product_ids, amazon_products_ids, warehouse_ids):
        product_listing_stock = self.check_stock_type(instance, product_ids, warehouse_ids)
        if product_listing_stock:
            message_information = ''
            message_id = 1
            for amazon_product_id in amazon_products_ids:
                amazon_product = self.browse(amazon_product_id)
                product_val = next((product_dict for product_dict in product_listing_stock if
                     product_dict['product_id'] == amazon_product.product_id.id))
                stock = product_val.get('stock')
                message_information = self.prepare_export_stock_level_dict_operation(\
                    amazon_product, instance, stock, message_information, message_id)
                message_id = message_id + 1

            if message_information:
                self.process_amazon_export_stock_dict_ept(\
                    instance, message_information)
        return True

    def export_stock_levels(self, instance):
        warehouse_ids = instance.warehouse_id.ids
        if instance.stock_update_warehouse_ids:
            warehouse_ids += instance.stock_update_warehouse_ids.ids
            warehouse_ids = list(set(warehouse_ids))

        product_ids = self.product_id
        self.process_export_stock_message_info_ept(instance, product_ids.ids, self.ids, warehouse_ids)
        return True

    def export_stock_levels_operation(self, instance):
        """
        This Method relocates prepare envelop for inventory.
        :return: This Method return Boolean(True/False).
        """
        prod_obj = self.env['product.product']
        from_datetime = instance.inventory_last_sync_on
        company = instance.company_id

        warehouse_ids = instance.warehouse_id.ids
        warehouse_ids += instance.stock_update_warehouse_ids.ids if instance.stock_update_warehouse_ids else []
        warehouse_ids = list(set(warehouse_ids))

        if not from_datetime:
            from_datetime = datetime.today() - timedelta(days=365)
        product_ids = prod_obj.get_products_based_on_movement_date(from_datetime, company)
        product_ids = [product_id.get('product_id') for product_id in product_ids]
        amazon_products = self.env['amazon.product.ept'].search([('exported_to_amazon', '=', True),
                                                                 ('instance_id', '=', instance.id),
                                                                 ('fulfillment_by', '=', 'FBM'),
                                                                 ('product_id', 'in', product_ids)])
        product_ids = amazon_products.mapped('product_id')

        self.process_export_stock_message_info_ept(instance, product_ids.ids, amazon_products.ids,
                                                   warehouse_ids)
        return True

    def process_amazon_export_stock_dict_ept(self, instance, message_information):
        merchant_string = "<MerchantIdentifier>%s</MerchantIdentifier>" % (\
            instance.merchant_id)
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        amazon_process_job_log_obj = self.env['common.log.book.ept']
        amazon_feed_submit_history = self.env['feed.submission.history']

        data = """<?xml version="1.0" encoding="utf-8"?><AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd"><Header><DocumentVersion>1.01</DocumentVersion>""" + merchant_string + """</Header><MessageType>Inventory</MessageType>""" + message_information + """</AmazonEnvelope>"""
        kwargs = {'merchant_id': instance.merchant_id and str(
            instance.merchant_id) or False,
                  'auth_token': instance.auth_token and str(
                      instance.auth_token) or False,
                  'app_name': 'amazon_ept',
                  'account_token': account.account_token,
                  'emipro_api': 'export_stock_levels_v13',
                  'dbuuid': dbuuid,
                  'data': data,
                  'amazon_marketplace_code': instance.country_id.amazon_marketplace_code or
                                             instance.country_id.code,
                  'marketplaceids': [instance.market_place_id], }
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            amazon_process_job_log_obj.create({
                'module': 'amazon_ept',
                'type': 'export',
                'res_id': self.id,
                'model_id': self.env['ir.model']._get('amazon.product.ept').id,
                'active': True,
                'log_lines': [(0, 0, {'message': response.get('reason')})]
            })
        else:
            result = response.get('result')
            seller_id = self._context.get('seller_id',
                                          False) or instance.seller_id
            if seller_id:
                last_feed_submission_id = result.get('FeedSubmissionInfo',
                                                     {}).get(
                    'FeedSubmissionId', {}).get('value', False)
                vals = {'message': data,
                        'feed_result_id': last_feed_submission_id,
                        'feed_submit_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                        'instance_id': instance.id, 'user_id': self._uid,
                        'feed_type': 'export_stock',
                        'seller_id': instance.seller_id.id}
                amazon_feed_submit_history.create(vals)

        return True

    def check_stock_type(self, instance, product_ids, warehouse_ids):
        """
        This Method relocates check type of stock.
        :param instance: This arguments relocates instance of amazon.
        :param product_ids: This arguments product listing id of odoo.
        :param warehouse_ids:This arguments relocates warehouse of amazon.
        :return: This Method return product listing stock.

        Updated by twinkalc on 5th October to process to get product stock
        with warehouse ids and removed unnecessary args.
        """
        prod_obj = self.env['product.product']
        ware_obj = self.env['stock.warehouse']
        product_listing_stock = []
        if product_ids:
            products = prod_obj.browse(product_ids)
            warehouses = ware_obj.browse(warehouse_ids)
            if instance.stock_field == 'free_qty':
                product_listing_stock = prod_obj.get_qty_on_hand(warehouses, products)
            elif instance.stock_field == 'virtual_available':
                product_listing_stock = prod_obj.get_forecated_qty(warehouses, products)
        return product_listing_stock

    def prepare_export_stock_level_dict_operation(self, amazon_product, instance, actual_stock, message_information,
                                                  message_id):

        """
        This Method relocates prepare envelope of export stock value.
        :param amazon_product: This arguments relocates product of amazon.
        :param instance: This arguments relocates instance of amazon.
        :param message_information: This arguments relocates message information.
        :param message_id: This arguments relocates message id of amazon envelope.
        :return: This method return message envelope for amazon.
        """
        seller_sku = html.escape(amazon_product['seller_sku'])
        stock = self.stock_ept_calculation(actual_stock,
                                           amazon_product['fix_stock_type'],
                                           amazon_product['fix_stock_value'])
        if amazon_product['allow_package_qty']:
            asin_qty = amazon_product['asin_qty']
            stock = math.floor(stock / asin_qty) if asin_qty > 0.0 else stock

        stock = 0 if int(stock) < 1 else int(stock)
        fulfillment_latency = amazon_product.product_id.sale_delay or amazon_product['fulfillment_latency'] or \
                              instance.seller_id.fulfillment_latency
        message_information += """<Message><MessageID>%s</MessageID><OperationType>Update</OperationType><Inventory><SKU>%s</SKU><Quantity>%s</Quantity><FulfillmentLatency>%s</FulfillmentLatency> </Inventory></Message>""" % (
            message_id, seller_sku, stock, int(fulfillment_latency))
        return message_information

    def stock_ept_calculation(self, actual_stock, fix_stock_type=False, fix_stock_value=0):
        """
        This mehod relocates calculate stock.
        :param actual_stock: This arguments relocates actual stock.
        :param fix_stock_type: This arguments relocates type of stock type.
        :param fix_stock_value: This arguments relocates value of stock value.
        :return:
        """
        try:
            if actual_stock >= 1.00:
                if fix_stock_type == 'fix':
                    if fix_stock_value >= actual_stock:
                        return actual_stock
                    else:
                        return fix_stock_value

                elif fix_stock_type == 'percentage':
                    quantity = int((actual_stock * fix_stock_value) / 100.0)
                    if quantity >= actual_stock:
                        return actual_stock
                    else:
                        return quantity
            return actual_stock
        except Exception as e:
            raise Warning(e)

    def update_price(self, instance):
        """
        This Method relocates create envelope for update price in amazon.
        :param instance: This arguments relocates instance of amazon.
        :return:This Method return boolean(True/False).
        """
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        amazon_feed_submit_history = self.env['feed.submission.history']
        message_id = 1
        merchant_string = "<MerchantIdentifier>%s</MerchantIdentifier>" % (instance.merchant_id)
        message_type = """<MessageType>Price</MessageType>"""
        message_information = ''

        for amazon_products in self:
            message_information = self.update_price_dict(instance, amazon_products, message_information, message_id)
            message_id = message_id + 1
        if message_information:
            data = """<?xml version="1.0" encoding="utf-8"?><AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd"><Header><DocumentVersion>1.01</DocumentVersion>""" + merchant_string + """</Header>""" + message_type + """""" + message_information + """</AmazonEnvelope>"""
            kwargs = {'merchant_id': instance.merchant_id and str(instance.merchant_id) or False,
                      'auth_token': instance.auth_token and str(instance.auth_token) or False,
                      'app_name': 'amazon_ept',
                      'account_token': account.account_token,
                      'emipro_api': 'update_price_v13',
                      'dbuuid': dbuuid,
                      'amazon_marketplace_code': instance.country_id.amazon_marketplace_code or
                                                 instance.country_id.code,
                      'marketplaceids': [instance.market_place_id],
                      'instance_id': instance.id,
                      'data': data}

            response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
            if response.get('reason'):
                raise Warning(response.get('reason'))
            else:
                results = response.get('result')
                
                if results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get('value', False):
                    last_feed_submission_id = results.get('FeedSubmissionInfo', {}).get(
                        'FeedSubmissionId', {}).get('value', False)
                    self.write({'last_feed_submission_id': last_feed_submission_id})
                    vals = {'message': data, 'feed_result_id': last_feed_submission_id,
                            'feed_submit_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                            'instance_id': instance.id, 'user_id': self._uid,
                            'feed_type': 'export_price',
                            'seller_id': instance.seller_id.id}
                    amazon_feed_submit_history.create(vals)
        return True

    def update_price_dict(self, instance, amazon_product, message_information, message_id):
        """
        This Method relocates Prepare price dictionary for amazon.
        :param instance: This arguments relocates instance of amazon.
        :param amazon_product: This arguments relocates product listing of amazon.
        :param message_information: This arguments prepare message envelope of amazon.
        :param message_id: This arguments relocates message of amazon.
        :return:This Method return envelope message of amazon.
        """
        price = instance.pricelist_id.get_product_price_ept(amazon_product.product_id)
        price = price and round(price, 2) or 0.0
        seller_sku = html.escape(amazon_product.seller_sku)
        price_string = """<Message><MessageID>%(message_id)s</MessageID><Price><SKU>%(sku)s</SKU><StandardPrice currency="%(currency)s">%(price)s</StandardPrice></Price></Message>"""
        price_string = price_string % {'currency': instance.pricelist_id.currency_id.name,
                                       'message_id': message_id, 'sku': seller_sku, 'price': price}
        message_information += price_string
        return message_information

    def update_images(self, instance):
        """
        This Method relocates prepare image envelope for amazon.
        :param instance: This arguments relocates instance of amazon.
        :return: This Method return boolean(True/False).
        """
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        amazon_process_job_log_obj = self.env['common.log.book.ept']
        feed_submission_obj = self.env['feed.submission.history']
        message_id = 1
        merchant_string = "<MerchantIdentifier>%s</MerchantIdentifier>" % (instance.merchant_id)
        message_information = ''
        for amazon_product in self:
            if not amazon_product.exported_to_amazon:
                continue
            for image_obj in amazon_product.product_id.ept_image_ids:
                message_information = self.create_image_dict(amazon_product, image_obj,
                                                             message_information, message_id)
                message_id = message_id + 1
        if message_information:
            data = """<?xml version="1.0" encoding="utf-8"?><AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd"><Header><DocumentVersion>1.01</DocumentVersion>""" + merchant_string + """</Header><MessageType>ProductImage</MessageType>""" + message_information + """</AmazonEnvelope>"""
            kwargs = {'merchant_id': instance.merchant_id and str(instance.merchant_id) or False,
                      'auth_token': instance.auth_token and str(instance.auth_token) or False,
                      'app_name': 'amazon_ept',
                      'account_token': account.account_token,
                      'emipro_api': 'update_images_v13',
                      'dbuuid': dbuuid,
                      'amazon_marketplace_code': instance.country_id.amazon_marketplace_code or
                                                 instance.country_id.code,
                      'marketplaceids': [instance.market_place_id],
                      'data': data, }

            response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
            if response.get('reason'):
                raise Warning(response.get('reason'))
            else:
                results = response.get('result')

            last_feed_submission_id = False
            if results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get('value',
                                                                                     False):
                last_feed_submission_id = results.get('FeedSubmissionInfo', {}).get(
                    'FeedSubmissionId', {}).get('value', False)
                self.write({'last_feed_submission_id': last_feed_submission_id})

                vals = {'message': data, 'feed_result_id': last_feed_submission_id,
                        'feed_submit_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                        'instance_id': instance.id, 'user_id': self._uid,
                        'feed_type': 'export_image',
                        'seller_id': instance.seller_id.id}
                feed = feed_submission_obj.create(vals)
                amazon_process_job_log_obj.create({
                    'module': 'amazon_ept',
                    'type': 'import',
                    'res_id': self.id,
                    'model_id': self.env['ir.model']._get('amazon.product.ept').id,
                    'active': True,
                    'log_lines': [(0, 0, {'message': 'Requested Feed Id' + feed and feed.id or False})]
                })

        return True

    def create_image_dict(self, amazon_product, image_obj, message_information, message_id):
        """
        This Method relocates prepare image envelope for amazon.
        :param amazon_product: This arguments relocates product listing of amazon.
        :param image_obj: This arguments relocates image object of amazon.
        :param message_information: This arguments prepare message envelope of amazon.
        :param message_id:This arguments relocates message of amazon.
        :return: This Method return envelope message of amazon.
        """
        seller_sku = amazon_product.seller_sku
        amazon_image_type = 'Main'
        # image_obj.image_type or 'Main'
        amazon_image_url = image_obj.url

        message_information += """<Message><MessageID>%s</MessageID><OperationType>Update</OperationType><ProductImage><SKU>%s</SKU><ImageType>%s</ImageType><ImageLocation>%s</ImageLocation></ProductImage></Message>""" % (
            message_id, seller_sku, amazon_image_type, amazon_image_url)
        return message_information

    def name_get(self):
        """
        Use: Display Product title
        Added By: Dhaval Sanghani [@Emipro Technologies]
        Added On: 17-Jun-2020
        @param: {}
        @return: {}
        """
        _logger.info(self)
        _logger.info(self._context)
        if self._context.get('show_product_title', False):
            res = []
            for product in self:
                name = product.name or False
                if not name and product.title:
                    name = product.title
                res.append((product.id, name or "Title not found"))
            _logger.info(res)
            return res
        return super(amazon_product_ept, self).name_get()


class ProductProduct(models.Model):
    _inherit='product.product'


    is_mapped_with_amz = fields.Boolean(compute="_compute_is_amazon_mapped")

    def _compute_is_amazon_mapped(self):
        amz_product_obj = self.env['amazon.product.ept']
        self.is_mapped_with_amz = True if amz_product_obj.search([('product_id', '=', self.id)]) else False

    def action_view_amazon_product_ept(self):
        self.ensure_one()
        action = self.env.ref('amazon_ept.action_amazon_product_ept').read()[0]
        action['domain'] = [('product_id', '=', self.id)]
        return action

