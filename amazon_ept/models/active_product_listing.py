from odoo import models, fields, api, _
from odoo.addons.iap.models import iap
import time
import base64
import csv
from io import StringIO
from ..endpoint import DEFAULT_ENDPOINT


class active_product_listing_report_ept(models.Model):
    _name = "active.product.listing.report.ept"
    _description = "Active Product"
    _inherit = ['mail.thread']
    _order = 'id desc'

    @api.model
    @api.depends('seller_id')
    def get_company(self):
        """
            @author : Harnisha Patel
            @last_updated_on : 3/10/2019
            The below method sets company for a particular record.
            """
        for record in self:
            company_id = record.seller_id and record.seller_id.company_id.id or False
            if not company_id:
                company_id = self.env.company.id
            record.company_id = company_id

    def get_log_count(self):
        """
        Find all stock moves associated with this report
        :return:
        """
        log_obj = self.env['common.log.book.ept']
        model_id = self.env['ir.model']._get('active.product.listing.report.ept').id
        self.log_count = log_obj.search_count([('res_id', '=', self.id),('model_id','=',model_id)])

    name = fields.Char(size=256, string='Name', help='Record number')
    instance_id = fields.Many2one('amazon.instance.ept', string='Instance', help='Record of instance')
    report_id = fields.Char('Report ID', readonly='1', help='ID of report')
    report_request_id = fields.Char('Report Request ID', readonly='1', help='Request ID of the report')
    attachment_id = fields.Many2one('ir.attachment', string='Attachment', help='Record of attachment')
    report_type = fields.Char(size=256, string='Report Type', help='Type of report')
    state = fields.Selection(
        [('draft', 'Draft'), ('_SUBMITTED_', 'SUBMITTED'), ('_IN_PROGRESS_', 'IN_PROGRESS'),
         ('_CANCELLED_', 'CANCELLED'), ('_DONE_', 'DONE'),
         ('_DONE_NO_DATA_', 'DONE_NO_DATA'), ('processed', 'PROCESSED'), ('imported', 'Imported'),
         ('partially_processed', 'Partially Processed'), ('closed', 'Closed')
         ],
        string='Report Status', default='draft', help='State of record')
    seller_id = fields.Many2one('amazon.seller.ept', string='Seller', copy=False, help='ID of seller')
    user_id = fields.Many2one('res.users', string="Requested User", help='ID of user')
    company_id = fields.Many2one('res.company', string="Company", copy=False, compute="get_company", store=True,
                                 help='ID of company')
    update_price_in_pricelist = fields.Boolean(string='Update price in pricelist?', default=False,
                                               help='Update or create product line in pricelist if ticked.')
    auto_create_product = fields.Boolean(string='Auto create product?', default=False,
                                         help='Create product in ERP if not found.')
    log_count = fields.Integer(compute="get_log_count", string="Log Count",
                               help="Count number of created Stock Move")

    def list_of_process_logs(self):
        """
            List Of Logs View
            @author: Keyur Kanani
            :return:
            """
        model_id =  self.env['ir.model']._get('active.product.listing.report.ept').id
        action = {
            'domain': "[('res_id', '=', " + str(self.id) + " ),('model_id','=',"+str(model_id)+")]",
            'name': 'Active Product Logs',
            'view_mode': 'tree,form',
            'res_model': 'common.log.book.ept',
            'type': 'ir.actions.act_window',
        }
        return action

    @api.model
    def create(self, vals):
        """
            @author : Harnisha Patel
            @last_updated_on : 3/10/2019
            The below method sets name of a particular record as per the sequence.
            """
        try:
            sequence = self.env.ref('amazon_ept.seq_active_product_list')
            if sequence:
                report_name = sequence.next_by_id()
            else:
                report_name = '/'
        except:
            report_name = '/'
        vals.update({'name': report_name})
        return super(active_product_listing_report_ept, self).create(vals)

    @api.onchange('seller_id')
    def on_change_seller_id(self):
        if self.instance_id:
            self.instance_id = None

    def get_report_list(self):
        """
            @author : Harnisha Patel
            @last_updated_on : 3/10/2019
            The below method gets the list of report.
            """
        self.ensure_one()
        seller = self.instance_id.seller_id
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        if not seller:
            raise Warning('Please select seller')
        if not self.request_id:
            return True
        kwargs = {'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
                  'auth_token': seller.auth_token and str(seller.auth_token) or False,
                  'app_name': 'amazon_ept',
                  'account_token': account.account_token,
                  'emipro_api': 'get_report_list_v13',
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or seller.country_id.code,
                  'request_ids': [self.request_id],
                  }
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(response.get('reason'))
        else:
            list_of_wrapper = response.get('result')
        for result in list_of_wrapper:
            self.update_report_history(result)
        return True

    def update_report_history(self, request_result):
        """
            @author : Harnisha Patel
            @last_updated_on : 3/10/2019
            The below method updates the report history and changes state of a particular record.
            """
        report_info = request_result.get('ReportInfo', {})
        report_request_info = request_result.get('ReportRequestInfo', {})
        request_id = report_state = report_id = False
        if report_request_info:
            request_id = str(report_request_info.get('ReportRequestId', {}).get('value', ''))
            report_state = report_request_info.get('ReportProcessingStatus', {}).get('value', '_SUBMITTED_')
            report_id = report_request_info.get('GeneratedReportId', {}).get('value', False)
        elif report_info:
            report_id = report_info.get('ReportId', {}).get('value', False)
            request_id = report_info.get('ReportRequestId', {}).get('value', False)
        if report_state == '_DONE_' and not report_id:
            self.get_report_list()
        vals = {}
        if not self.report_request_id and request_id:
            vals.update({'report_request_id': request_id})
        if report_state:
            vals.update({'state': report_state})
        if report_id:
            vals.update({'report_id': report_id})
        self.write(vals)
        return True

    def request_report(self):
        """
            @author : Harnisha Patel
            @last_updated_on : 3/10/2019
            The below method requests the record of the report.
            """
        seller = self.instance_id.seller_id
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        if not seller:
            raise Warning('Please select instance')
        marketplace_ids = tuple([self.instance_id.market_place_id])
        kwargs = {'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
                  'auth_token': seller.auth_token and str(seller.auth_token) or False,
                  'app_name': 'amazon_ept',
                  'account_token': account.account_token,
                  'emipro_api': 'request_report_v13',
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or seller.country_id.code,
                  'report_type': self.report_type or '_GET_MERCHANT_LISTINGS_DATA_',
                  'marketplace_ids': marketplace_ids,
                  'start_date': None,
                  'end_date': None,
                  }
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(response.get('reason'))
        else:
            result = response.get('result')
            self.update_report_history(result)
        return True

    def get_report_request_list(self):
        """
            @author : Harnisha Patel
            @last_updated_on : 3/10/2019
            The below method checks status and gets the report list.
            """
        self.ensure_one()
        seller = self.instance_id.seller_id
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        if not seller:
            raise Warning(_('Please select Seller'))
        if not self.report_request_id:
            return True
        kwargs = {'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
                  'auth_token': seller.auth_token and str(seller.auth_token) or False,
                  'app_name': 'amazon_ept',
                  'account_token': account.account_token,
                  'emipro_api': 'get_report_request_list_v13',
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or seller.country_id.code,
                  'request_ids': (self.report_request_id,),
                  }

        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(response.get('reason'))
        else:
            list_of_wrapper = response.get('result')
        for result in list_of_wrapper:
            self.update_report_history(result)
        return True

    def get_report(self):
        """
            @author : Harnisha Patel
            @last_updated_on : 3/10/2019
            The below method gets the record of the report and also adds the same as an attachment.
            """
        self.ensure_one()
        seller = self.instance_id.seller_id
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        if not seller:
            raise Warning(_('Please select seller'))
        if not self.report_id:
            return True
        kwargs = {'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
                  'auth_token': seller.auth_token and str(seller.auth_token) or False,
                  'app_name': 'amazon_ept',
                  'account_token': account.account_token,
                  'emipro_api': 'get_report_v13',
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or seller.country_id.code,
                  'report_id': self.report_id,
                  }
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(response.get('reason'))
        else:
            result = response.get('result')
        result = result.encode()
        result = base64.b64encode(result)
        file_name = "Active_Product_List_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'datas': result,
            'res_model': 'mail.compose.message',
            'type': 'binary'
        })
        self.message_post(body=_("<b>Active Product Report Downloaded</b>"), attachment_ids=attachment.ids)
        self.write({'attachment_id': attachment.id})
        return True

    def download_report(self):
        """
            @author : Harnisha Patel
            @last_updated_on : 3/10/2019
            The below method downloads the report.
            """
        self.ensure_one()
        if self.attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' % (self.attachment_id.id),
                'target': 'self',
            }
        return True

    def get_fulfillment_type(self, fulfillment_channel):
        """
           @author : Harnisha Patel
           @last_updated_on : 4/10/2019
           The below method returns the fulfillment type value.
           """
        if fulfillment_channel and fulfillment_channel == 'DEFAULT':
            return 'FBM'  # 'MFN'
        else:
            return 'FBA'  # 'AFN'

    def update_pricelist_items(self, seller_sku, price):
        """
            @author : Harnisha Patel
            @last_updated_on : 5/10/2019
            The below method creates or updates the price of a product in the pricelist.
            """
        pricelist_item_obj = self.env['product.pricelist.item']
        product_obj = self.env['product.template']
        if self.instance_id.pricelist_id and self.update_price_in_pricelist:
            item = self.instance_id.pricelist_id.item_ids.filtered(
                lambda i: i.product_tmpl_id.default_code == seller_sku)
            if item and not item.fixed_price == float(price):
                item.fixed_price = price
            if not item:
                product = product_obj.search([('default_code', '=', seller_sku)])
                pricelist_item_obj.create({'product_tmpl_id': product.id,
                                           'min_quantity': 1,
                                           'fixed_price': price,
                                           'pricelist_id': self.instance_id.pricelist_id.id})

    def sync_products(self):
        """
            @author : Harnisha Patel
            @last_updated_on : 5/10/2019
            The below method syncs the products and also creates record of log if error is generated.
            """
        self.ensure_one()
        if not self.attachment_id:
            raise Warning(_("There is no any report are attached with this record."))
        if not self.instance_id:
            raise Warning(_("Instance not found "))
        if not self.instance_id.pricelist_id:
            raise Warning(_("Please configure Pricelist in Amazon Marketplace"))
        imp_file = StringIO(base64.b64decode(self.attachment_id.datas).decode())
        reader = csv.DictReader(imp_file, delimiter='\t')
        amazon_product_ept_obj = self.env['amazon.product.ept']
        product_obj = self.env['product.product']
        log_rec = self.amz_create_product_sycn_logs()
        transaction_log_lines = []

        price_list_id = self.instance_id.pricelist_id
        for row in reader:
            if 'fulfilment-channel' in row.keys():
                fulfillment_type = self.get_fulfillment_type(row.get('fulfilment-channel', ''))
            else:
                fulfillment_type = self.get_fulfillment_type(row.get('fulfillment-channel', ''))

            seller_sku = row.get('seller-sku', '').strip()
            odoo_product_id = product_obj.search(['|', ('default_code', '=ilike', seller_sku), ('barcode', '=ilike', seller_sku)])
            amazon_product_id = amazon_product_ept_obj.search_amazon_product(self.instance_id.id, seller_sku,
                                                             fulfillment_by=fulfillment_type)
            if not amazon_product_id and not odoo_product_id:
                amazon_product = amazon_product_ept_obj.search(
                        ['|', ('active', '=', False), ('active', '=', True), ('seller_sku', '=', seller_sku)], limit=1)
                odoo_product_id = amazon_product.product_id

            if amazon_product_id:
                self.create_or_update_amazon_product_ept(amazon_product_id,
                                                         amazon_product_id.product_id.id,
                                                         fulfillment_type, row, transaction_log_lines)
                if self.update_price_in_pricelist and row.get('price', False):
                    price_list_id.set_product_price_ept(amazon_product_id.product_id.id, float(row.get('price')))
            else:
                if len(odoo_product_id.ids) > 1:
                    not_found_msg = """Multiple product found for same sku %s in ERP""" % (seller_sku)
                    self.prepare_amz_sycn_product_log_line_vals(odoo_product_id.ids[0], seller_sku, not_found_msg,
                                                                fulfillment_type, transaction_log_lines)
                    continue
                self.create_odoo_or_amazon_product_ept(odoo_product_id, fulfillment_type, row, transaction_log_lines)

        if transaction_log_lines:
            log_rec.write({'log_lines': transaction_log_lines})
        else:
            log_rec.unlink()
        self.write({'state': 'processed'})
        return True

    def create_odoo_or_amazon_product_ept(self, odoo_product_id, fulfillment_type, row, transaction_log_lines):
        product_obj = self.env['product.product']
        seller_sku = row.get('seller-sku', '').strip()
        price_list_id = self.instance_id.pricelist_id
        if odoo_product_id:
            self.create_or_update_amazon_product_ept(False, odoo_product_id,
                                                     fulfillment_type, row, transaction_log_lines)
            if self.update_price_in_pricelist and row.get('price', False):
                price_list_id.set_product_price_ept(odoo_product_id.id, float(row.get('price')))
        else:
            if self.auto_create_product:
                if not row.get('item-name'):
                    message = """ Line Skipped due to product name not found of seller sku %s || Instance %s
                    """ % (seller_sku, self.instance_id.name)
                else:
                    created_product = product_obj.create({'default_code': row.get('seller-sku', ''),
                                                            'name': row.get('item-name'),
                                                            'type': 'product'})
                    self.create_or_update_amazon_product_ept(False, created_product, fulfillment_type, row, transaction_log_lines)
                    message = """ Product created for seller sku %s || Instance %s """ % (seller_sku, self.instance_id.name)
                    if self.update_price_in_pricelist and row.get('price', False):
                        price_list_id.set_product_price_ept(created_product.id, float(row.get('price')))
            else:
                message = """ Line Skipped due to product not found Seller Sku %s || Instance %s"""% (seller_sku, self.instance_id.name)

            self.prepare_amz_sycn_product_log_line_vals(odoo_product_id.id, seller_sku, message,
                                                          fulfillment_type, transaction_log_lines)
        return True

    def create_or_update_amazon_product_ept(self, amazon_product_id, odoo_product_id,
                                            fulfillment_type, row, transaction_log_lines):
        """
        This method will create tha amazon product if it is exist and if amazon
        product exist that it will update that
        param amazon_product_id : amazon product id
        param odoo_product_id : odoo product
        param fulfillment_type : selling on
        param row : report data
        """

        amazon_product_ept_obj = self.env['amazon.product.ept']
        description = row.get('item-description', '')
        name = row.get('item-name', '')
        if not amazon_product_id:
            amazon_product_ept_obj.create({
                'product_id': odoo_product_id.id,
                'instance_id': self.instance_id.id,
                'name': name,
                'long_description': description,
                'product_asin': row.get('asin1'),
                'seller_sku': row.get('seller-sku', ''),
                'fulfillment_by': fulfillment_type,
                'exported_to_amazon': True
            })
            message = """ Amazon product created for seller sku %s || Instance %s """ % (
                row.get('seller-sku', ''), self.instance_id.name)
            self.prepare_amz_sycn_product_log_line_vals(odoo_product_id.id, row.get('seller-sku', ''), message,
                                                        fulfillment_type, transaction_log_lines)
        else:
            amazon_product_id.write({
                'name': name,
                'long_description': description,
                'seller_sku': row.get('seller-sku', ''),
                'fulfillment_by': fulfillment_type,
                'product_asin': row.get('asin1'),
                'exported_to_amazon': True,
            })

    def amz_create_product_sycn_logs(self):
        log_book_obj = self.env['common.log.book.ept']
        log_vals = {
            'active': True,
            'type': 'import',
            'model_id': self.env['ir.model']._get('active.product.listing.report.ept').id,
            'res_id': self.id,
            'module': 'amazon_ept'
        }
        log_rec = log_book_obj.create(log_vals)
        return log_rec

    @staticmethod
    def prepare_amz_sycn_product_log_line_vals(product_id, default_code, message, fulfillment_by,
                                                 transaction_log_lines):
        log_line_vals = {
            'product_id': product_id,
            'default_code': default_code,
            'message': message,
            'fulfillment_by': fulfillment_by,
        }
        transaction_log_lines.append((0, 0, log_line_vals))
        return  transaction_log_lines