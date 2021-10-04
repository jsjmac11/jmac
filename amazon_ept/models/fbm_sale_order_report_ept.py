import time
import base64
import pytz
import logging
from odoo import models, fields, api, _
from odoo.exceptions import Warning
from io import StringIO
import csv
from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT

utc = pytz.utc
_logger = logging.getLogger(__name__)


class FbmSaleOrderReportEpt(models.Model):
    _name = "fbm.sale.order.report.ept"
    _description = "FBM Sale Order Report Ept"
    _inherit = ['mail.thread']
    _order = 'name desc'

    seller_id = fields.Many2one('amazon.seller.ept', string='Seller', help="Select Amazon Seller Name listed in odoo",
                                )
    company_id = fields.Many2one('res.company', string="Company", related="seller_id.company_id", store=False)
    name = fields.Char(size=256, string='Name', readonly=True)
    attachment_id = fields.Many2one('ir.attachment', string='Attachment')
    report_type = fields.Char(size=256, string='Report Type')
    report_request_id = fields.Char(size=256, string='Report Request ID')
    report_id = fields.Char(size=256, string='Report ID')
    requested_date = fields.Datetime('Requested Date', default=time.strftime("%Y-%m-%d %H:%M:%S"))
    state = fields.Selection(
        [('draft', 'Draft'), ('_SUBMITTED_', 'SUBMITTED'), ('_IN_PROGRESS_', 'IN_PROGRESS'),
         ('_CANCELLED_', 'CANCELLED'), ('_DONE_', 'DONE'),
         ('_DONE_NO_DATA_', 'DONE_NO_DATA'), ('processed', 'PROCESSED'), ('imported', 'Imported'),
         ('partially_processed', 'Partially Processed'), ('closed', 'Closed')
         ],
        string='Report Status', default='draft')
    user_id = fields.Many2one('res.users', string="Requested User")
    sales_order_report_ids = fields.One2many('sale.order', 'amz_sales_order_report_id', string="Sale Orders")
    sales_order_count = fields.Integer(compute='_compute_order_count', string='# of Orders')
    log_book_ids = fields.One2many('common.log.book.ept', 'fbm_sales_order_report_id', string="Log Book Id")
    child_sales_order_report_id = fields.Many2one('fbm.sale.order.report.ept', string='Unshipped Sales Order Report')
    is_parent = fields.Boolean('Is Parent Report', default=True)
    is_encrypted_attachment = fields.Boolean(string="Is Encrypted Attachment?", default=False,
                                             help="Used for identify encrypted attachments")

    # @api.constrains('start_date', 'end_date')
    # def _check_duration(self):
    #     if self.start_date and self.end_date < self.start_date:
    #         raise Warning('Error!\nThe start date must be precede its end date.')
    #     return True
    @api.model
    def auto_import_unshipped_order_report(self, seller):
        if seller.id:
            sale_order_report = self.create({'report_type': '_GET_FLAT_FILE_ORDER_REPORT_DATA_',
                                             'seller_id': seller.id,
                                             'state': 'draft',
                                             'requested_date': time.strftime("%Y-%m-%d %H:%M:%S")
                                             })
            sale_order_report.with_context(is_auto_process=True).request_report()
        return True

    @api.model
    def auto_process_unshipped_order_report(self, seller):
        if seller:
            sale_order_reports = self.search([('seller_id', '=', seller.id),
                                              ('state', 'in', ['_SUBMITTED_', '_IN_PROGRESS_'])])
            for sale_order_report in sale_order_reports:
                time.sleep(3) # For request trotted
                sale_order_report.with_context(is_auto_process=True).get_report_request_list()
                if sale_order_report.state == '_DONE_' and not sale_order_report.attachment_id:
                    sale_order_report.with_context(is_auto_process=True).get_report()
                    sale_order_report.process_fbm_sale_order_file()
                    self._cr.commit()
        return True

    @api.model
    def create(self, vals):
        seq = self.env['ir.sequence'].next_by_code('fbm_shipped_sale_order_report_ept_sequence') or '/'
        vals['name'] = seq
        return super(FbmSaleOrderReportEpt, self).create(vals)

    @api.model
    def default_get(self, fields):
        res = super(FbmSaleOrderReportEpt, self).default_get(fields)
        if not fields:
            return res
        res.update({'report_type': '_GET_FLAT_FILE_ORDER_REPORT_DATA_',
                    })
        return res

    def _compute_order_count(self):
        """
        This method Calculate the Total sales order with Sale order Report Id.
        :return: True
        """
        sale_order_obj = self.env['sale.order']
        self.sales_order_count = sale_order_obj.search_count([('amz_sales_order_report_id', '=', self.id)])

    def action_view_sales_order(self):
        """
        This method show the Sales order connected with particular report.
        :return:action
        """
        action = {
            'name': 'Sales Orders',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'sale.order',
            'type': 'ir.actions.act_window',
        }

        orders = self.env['sale.order'].search([('amz_sales_order_report_id', '=', self.id)])
        if len(orders) > 1:
            action['domain'] = [('id', 'in', orders.ids)]
        elif orders:
            action['views'] = [(self.env.ref('sale.view_order_form').id, 'form')]
            action['res_id'] = orders.id
        return action

    def request_report(self):
        """
        This method request in Amazon for unshipped Sales Orders.
        :return:True
        """
        seller = self.seller_id
        report_type = self.report_type
        instances = seller.instance_ids
        marketplace_ids = tuple(map(lambda x: x.market_place_id, instances))
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo(
        ).get_param('database.uuid')

        if not seller:
            raise Warning('Please select Seller')

        kwargs = {'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
                  'auth_token': seller.auth_token and str(seller.auth_token) or False,
                  'app_name': 'amazon_ept',
                  'account_token': account.account_token,
                  'emipro_api': 'request_report_fbm_v13',
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                             seller.country_id.code,
                  'report_type': report_type,
                  'marketplace_ids': marketplace_ids,
                  'ReportOptions': "ShowSalesChannel=true"
                  }
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(response.get('reason'))
        else:
            result = response.get('result')
            self.update_report_history(result)
        return True

    def create_record_for_all_orders(self):
        """
        This method create the child records.
        :return: record object
        """
        sales_report_object = self.env['fbm.sale.order.report.ept']
        sales_report_values = {
            'seller_id': self.seller_id.id,
            'report_type': '_GET_FLAT_FILE_ACTIONABLE_ORDER_DATA_',
        }
        record = sales_report_object.create(sales_report_values)
        return record

    def get_report_request_list(self):
        """
        This method check the status of the Report.
        :return:True
        """
        list_of_wrapper = []
        seller = self.seller_id
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo(
        ).get_param('database.uuid')

        if not seller:
            raise Warning('Please select Seller')

        if not self.report_request_id:
            return True

        kwargs = {'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
                  'auth_token': seller.auth_token and str(seller.auth_token) or False,
                  'app_name': 'amazon_ept',
                  'account_token': account.account_token,
                  'emipro_api': 'get_report_request_list_v13',
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                             seller.country_id.code,
                  'request_ids': (self.report_request_id,),
                  }

        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            if self._context.get('is_auto_process'):
                _logger.info("Reason %s." % response.get('reason'))
            else:
                raise Warning(response.get('reason'))
        else:
            list_of_wrapper = response.get('result')

        for result in list_of_wrapper:
            self.update_report_history(result)

        return True

    def get_report(self):
        """
        This method get the report and store in one csv file and attached with one attachment.
        :return:True
        """
        seller = self.seller_id
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo(
        ).get_param('database.uuid')
        if not seller:
            raise Warning('Please select seller')
        if not self.report_id:
            return True

        kwargs = {'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
                  'auth_token': seller.auth_token and str(seller.auth_token) or False,
                  'app_name': 'amazon_ept',
                  'account_token': account.account_token,
                  'emipro_api': 'get_report_v13',
                  'amz_report_type': 'fbm_report',
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                             seller.country_id.code,
                  'report_id': self.report_id,
                  }

        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(response.get('reason'))
        else:
            result = response.get('result')
        file_name = "FBM_Sale_Order_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'datas': result.encode(),
            'res_model': 'mail.compose.message',
            'type': 'binary'
        })
        self.message_post(body=_("<b>FBM Sale Order Report Downloaded</b>"),
                          attachment_ids=attachment.ids)
        self.write({'attachment_id': attachment.id, 'is_encrypted_attachment':True})

        return True

    @api.model
    def update_report_history(self, request_result):
        report_info = request_result.get('ReportInfo', {})
        report_request_info = request_result.get('ReportRequestInfo', {})
        request_id = report_state = report_id = False
        if report_request_info:
            request_id = str(report_request_info.get('ReportRequestId', {}).get('value', ''))
            report_state = report_request_info.get('ReportProcessingStatus', {}).get('value',
                                                                                     '_SUBMITTED_')
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

    def download_report(self):
        """
        Through this method, user can download the report.
        :return:True
        """
        self.ensure_one()
        if self.attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' % (self.attachment_id.id),
                'target': 'self',
            }
        return True

    def prepare_fbm_customer_vals(self, row):
        """
        This method prepare the customer vals
        :param row: row of data
        :return: customer vals
        """
        # vat = row.get('vat-number', '')
        # if vat and vat[:2] != row.get('ship-country', ''):
        #     vat = row.get('ship-country', '') + vat

        return {
            'BuyerEmail': row.get('buyer-email'),
            'BuyerName': row.get('buyer-name'),
            'BuyerNumber': row.get('buyer-phone-number'),
            'AddressLine1': row.get('ship-address-1'),
            'AddressLine2': row.get('ship-address-2'),
            'AddressLine3': row.get('ship-address-3'),
            'City': row.get('ship-city'),
            'ShipName': row.get('recipient-name'),
            'CountryCode': row.get('ship-country'),
            'StateOrRegion': row.get('ship-state') or False,
            'PostalCode': row.get('ship-postal-code'),
            'ShipNumber': row.get('ship-phone-number'),
            'vat-number': row.get('vat-number', ''),
        }

    def process_fbm_sale_order_file(self):
        """
        This method process the attached file with record and create Sales orders.
        :return:True
        """
        self.ensure_one()
        ir_cron_obj = self.env['ir.cron']
        if not self._context.get('is_auto_process',False):
            ir_cron_obj.with_context({'raise_warning': True}).find_running_schedulers(
                'ir_cron_process_amazon_unshipped_orders_seller_', self.seller_id.id)

        common_log_book_obj = self.env['common.log.book.ept']
        marketplaceids = tuple(map(lambda x: x.market_place_id, self.seller_id.instance_ids))
        if not marketplaceids:
            raise Warning("There is no any instance is configured of seller %s" % (self.seller_id.name))
        if not self.attachment_id:
            raise Warning("There is no any report are attached with this record.")

        file_order_list = self.get_unshipped_order()
        unshipped_order_list = []
        business_prime_dict = {}
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        kwargs = {'merchant_id': self.seller_id.merchant_id and str(self.seller_id.merchant_id) or False,
                  'auth_token': self.seller_id.auth_token and str(self.seller_id.auth_token) or False,
                  'app_name': 'amazon_ept',
                  'account_token': account.account_token,
                  'emipro_api': 'get_order_v13',
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': self.seller_id.country_id.amazon_marketplace_code or
                                             self.seller_id.country_id.code,
                  'marketplaceids': marketplaceids}

        for x in range(0, len(file_order_list), 50):
            result = []
            sale_orders_list = file_order_list[x:x + 50]
            kwargs.update({'sale_order_list': sale_orders_list})
            # TODO: Max_request_quota = 6, restore_rate = 1req/min
            response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
            if response.get('reason'):
                if self._context.get('is_auto_process'):
                    common_log_book_vals = {
                        'type': 'import',
                        'module': 'amazon_ept',
                        'model_id': self.env['ir.model']._get('fbm.sale.order.report.ept').id,
                        'res_id': self.id,
                        'active': True,
                        'log_lines': [(0, 0, {'message': 'FBM Sale Order Report Auto Process'})]
                    }
                    common_log_book_obj.create(common_log_book_vals)
                else:
                    raise Warning(response.get('reason'))
            elif response.get('result'):
                result = [response.get('result')]
                time.sleep(4)
            for wrapper_obj in result:
                orders = []
                if not isinstance(wrapper_obj.get('Orders', {}).get('Order', []), list):
                    orders.append(wrapper_obj.get('Orders', {}).get('Order', {}))
                else:
                    orders = wrapper_obj.get('Orders', {}).get('Order', [])
                for order in orders:
                    order_status = order.get('OrderStatus').get('value')
                    amazon_order_ref = order.get('AmazonOrderId', {}).get('value', False)
                    if not amazon_order_ref:
                        continue

                    is_business_order = True if order.get('IsBusinessOrder', {}).get(\
                        'value', '').lower() in ['true', 't'] else False
                    is_prime_order = True if order.get('IsPrime', {}).get(\
                        'value', '').lower() in ['true', 't'] else False

                    if order_status == 'Unshipped' and amazon_order_ref not in unshipped_order_list:
                        unshipped_order_list.append(amazon_order_ref)
                        if is_business_order or is_prime_order == True:
                            business_prime_dict.update({amazon_order_ref: {'is_business_order': is_business_order,
                                                                           'is_prime_order': is_prime_order}})


        marketplace_obj = self.env['amazon.marketplace.ept']
        auto_work_flow_obj = self.env['sale.workflow.process.ept']
        sale_order_obj = self.env['sale.order']
        sale_order_line_obj = self.env['sale.order.line']
        amazon_instance_obj = self.env['amazon.instance.ept']
        delivery_carrier_obj = self.env['delivery.carrier']
        seller = self.seller_id
        order_dict = dict()
        marketplace_dict = {}
        amazon_instance_dict = {}
        state_dict = {}
        country_dict = {}
        dict_product_details = {}
        order_skip_list = []

        common_log_book_vals = {
            'type': 'import',
            'module': 'amazon_ept',
            'model_id': self.env['ir.model']._get('fbm.sale.order.report.ept').id,
            'res_id': self.id,
            'active': True,
            'log_lines': [(0, 0, {'message': 'FBM Sale Order Report'})]
        }
        log_book = common_log_book_obj.create(common_log_book_vals)
        imp_file = self.decode_amazon_encrypted_fbm_attachments_data(self.attachment_id, log_book)
        reader = csv.DictReader(imp_file, delimiter='\t')
        for row in reader:
            if not row.get('sku'):
                continue
            if not row.get('order-id') in unshipped_order_list:
                continue
            amz_ref = row.get('order-id')
            marketplace_record = marketplace_dict.get(row.get('sales-channel'))
            if not marketplace_record:
                marketplace_record = marketplace_obj.search(
                    [('name', '=', row.get('sales-channel')), ('seller_id', '=', self.seller_id.id)])
                marketplace_dict.update({row.get('sales-channel'): marketplace_record})

            instance = amazon_instance_dict.get((self.seller_id, marketplace_record))
            if not instance:
                instance = self.seller_id.instance_ids.filtered(lambda l: l.marketplace_id.id == marketplace_record.id)
                amazon_instance_dict.update({(self.seller_id, marketplace_record): instance})

            if (amz_ref, instance.id) in order_skip_list:
                continue
            order = self.check_order_exist_in_odoo(amz_ref, instance.id, sale_order_obj)
            if order:
                order_skip_list.append((amz_ref, instance.id))
                continue
            order_dict = self.prepare_order_dict(order_dict, amz_ref, instance.id, row)

        count_order_number = 0
        module_obj = self.env['ir.module.module']
        vat_module = module_obj.sudo().search([('name', '=', 'base_vat'), ('state', '=', 'installed')])
        for order_ref, order_details in order_dict.items():
            skip_order, dict_product_details = self.create_or_find_amazon_fbm_product(order_ref, order_details,
                                                                           dict_product_details, log_book)
            if skip_order:
                continue

            customer_vals = self.prepare_fbm_customer_vals(order_details[0])
            instance = amazon_instance_obj.browse(order_ref[1])
            customer_vals.update({'check_vat_ept': True if vat_module else False})
            partner = self.get_partner(customer_vals, state_dict, country_dict, instance)
            order_values = {'PurchaseDate': {'value': order_details[0].get('purchase-date') or False},
                            'AmazonOrderId': {'value': order_ref[0] or False}}
            vals = sale_order_obj.prepare_amazon_sale_order_vals(instance, partner, order_values)
            ordervals = sale_order_obj.create_sales_order_vals_ept(vals)
            if not seller.is_default_odoo_sequence_in_sales_order:
                if seller.order_prefix:
                    name = seller.order_prefix + order_ref[0]
                else:
                    name = order_ref[0]
                ordervals.update({'name': name})
            updated_ordervals = self.prepare_updated_ordervals(instance, order_ref)
            if business_prime_dict.get(order_ref[0], False):
                updated_ordervals.update(
                    {'is_business_order': business_prime_dict.get(order_ref[0]).get('is_business_order'),
                     'is_prime_order': business_prime_dict.get(order_ref[0]).get('is_prime_order')})

            if order_details:
                updated_ordervals.update(
                    {'amz_shipment_service_level_category': order_details[0].get('ship-service-level', False)})
                # update sale order vals set carrier which amz_shipment_service_level_category and
                # unshipped order ship-service-level is same
                shipping_category = order_details[0].get('ship-service-level', False)
                if shipping_category:
                    carrier = delivery_carrier_obj.search(
                        [('amz_shipping_service_level_category', '=', shipping_category)], limit=1)
                    updated_ordervals.update({'carrier_id': carrier.id if carrier else False})

            ordervals.update(updated_ordervals)
            order = sale_order_obj.create(ordervals)
            self.amz_create_order_lines(order, instance, order_details, sale_order_line_obj, dict_product_details)
            auto_work_flow_obj.auto_workflow_process(instance.seller_id.fbm_auto_workflow_id.id, [order.id])
            count_order_number += 1
            if count_order_number >= 10:
                self._cr.commit()
                count_order_number = 0
        if not log_book.log_lines:
            log_book.unlink()
        self.write({'state': 'processed'})
        return True

    def get_unshipped_order(self):
        """
        Give the list of unshipped orders.
        :return: unshipped order list
        """
        shipping_report_obj = self.env['shipping.report.request.history']
        file_order_list = []
        if self.attachment_id and self.is_encrypted_attachment:
            imp_file = self.decode_amazon_encrypted_fbm_attachments_data(self.attachment_id, job=False)
        else:
            imp_file = StringIO(base64.decodebytes(self.attachment_id.datas).decode())
        reader = csv.DictReader(imp_file, delimiter='\t')
        for row in reader:
            file_order_list.append(row.get('order-id'))
        return file_order_list

    def prepare_order_dict(self, order_dict, amz_ref, instance_id, row):
        """
        This method prepare the order dictionary.
        :param order_dict: order dictionary
        :param amz_ref: amazon order id
        :param row: file line
        :return: order dictionary
        """

        fbm_order_dict = {
            'order-item-id': row.get('order-item-id'),
            'purchase-date': row.get('purchase-date'),
            'buyer-email': row.get('buyer-email'),
            'buyer-name': row.get('buyer-name'),
            'buyer-phone-number': row.get('buyer-phone-number'),
            'ship-phone-number': row.get('ship-phone-number'),
            'sku': row.get('sku'),
            'product-name': row.get('product-name'),
            'quantity-purchased': row.get('quantity-purchased'),
            'item-price': row.get('item-price'),
            'item-tax': row.get('item-tax'),
            'shipping-price': row.get('shipping-price'),
            'shipping-tax': row.get('shipping-tax'),
            'recipient-name': row.get('recipient-name'),
            'ship-address-1': row.get('ship-address-1'),
            'ship-address-2': row.get('ship-address-2'),
            'ship-city': row.get('ship-city'),
            'ship-state': row.get('ship-state'),
            'ship-postal-code': row.get('ship-postal-code'),
            'ship-country': row.get('ship-country'),
            'item-promotion-discount': abs(float(row.get('item-promotion-discount', 0.0))),
            'ship-promotion-discount': abs(float(row.get('ship-promotion-discount', 0.0))),
            'sales-channel': row.get('sales-channel'),
            'vat-number': row.get('buyer-tax-registration-id', ''),
            'ship-service-level': row.get('ship-service-level', '')
        }

        if order_dict.get((amz_ref, instance_id)):
            fbm_order_dict.update({'promise-date': row.get('promise-date'), })
            order_dict.get((amz_ref, instance_id)).append(fbm_order_dict)
        else:
            order_dict.update({(amz_ref, instance_id): [fbm_order_dict]})
        return order_dict

    def check_order_exist_in_odoo(self, amz_ref, instance_id, sale_order_obj):
        """
        This method check that the order is already exist in odoo or not.
        :param amz_ref: Amazon Order Reference
        :return: True or False
        """
        order = sale_order_obj.search(
            [('amz_instance_id', '=', instance_id), ('amz_order_reference', '=', amz_ref),
             ('amz_fulfillment_by', '=', 'FBM')])
        return order

    def get_partner(self, vals, state_dict, country_dict, instance):
        """
        This method is find the partner and if it's not found than it create the new partner.
        :param vals: {}
        :param state_dict: {}
        :param country_dict: {}
        :param instance: amazon.instance.ept()
        :return: Partner {}
        """
        partner_obj = self.env['res.partner']
        country = country_dict.get(vals.get('CountryCode'), False)
        if not country:
            country = partner_obj.get_country(vals.get('CountryCode'))
            country_dict.update({vals.get('CountryCode'): country})

        state = state_dict.get(vals.get('StateOrRegion'), False)
        if not state and country and vals.get('StateOrRegion') != '--':
            state = partner_obj.create_order_update_state(country.code, vals.get('StateOrRegion'),
                                                          vals.get('PostalCode'), country)
            state_dict.update({vals.get('StateOrRegion'): state})
        email = vals.get('BuyerEmail', '')
        buyer_name = vals.get('BuyerName', '')
        shipping_address_name = vals.get('ShipName', '')
        street = vals.get('AddressLine1') if vals.get('AddressLine1') else ''
        address_line2 = vals.get('AddressLine2') if vals.get('AddressLine2') else ''
        address_line3 = vals.get('AddressLine3') if vals.get('AddressLine3') else ''
        street2 = "%s %s" % (address_line2, address_line3) if address_line2 or address_line3 else False
        city = vals.get('City', '')
        zip_code = vals.get('PostalCode', '')
        phone = vals.get('ShipNumber', False)

        new_partner_vals = {
            'street': street,
            'street2': street2,
            'zip': zip_code,
            'city': city,
            'country_id': country.id if country else False,
            'state_id': state.id if state else False,
            'phone': phone,
            'company_id': instance.company_id.id,
            'email': email,
            'lang': instance.lang_id and instance.lang_id.code,
            'is_amz_customer': True
        }
        vat = vals.get('vat-number', '')
        is_update_via_query = False
        if vat:
            vat_country = vals.get('vat-country', '') or vals.get('CountryCode', '')
            if vals.get('check_vat_ept', False):
                if vat_country != country.code and not vat[:2].isalpha():
                    vat = vat_country + vat
                check_vat = partner_obj.check_amz_vat_validation_ept(vat, country, vat_country, instance)
                if check_vat:
                    new_partner_vals.update({'vat': vat})
                else:
                    is_update_via_query = True
            else:
                new_partner_vals.update({'vat': vat})

        if instance.amazon_property_account_payable_id:
            new_partner_vals.update({'property_account_payable_id': instance.amazon_property_account_payable_id.id})
        if instance.amazon_property_account_receivable_id:
            new_partner_vals.update({'property_account_receivable_id': instance.amazon_property_account_receivable_id.id})

        if not email and buyer_name == 'Amazon':
            partner = partner_obj.with_context(is_amazon_partner=True).search(
                [('name', '=', buyer_name), ('city', '=', city), ('state_id', '=', state.id), ('country_id', '=', country.id),
                 '|', ('company_id', '=', False), ('company_id', '=', instance.company_id.id)], limit=1)
        else:
            partner = partner_obj.with_context(is_amazon_partner=True).search([('email', '=', email),
                 '|', ('company_id', '=', False), ('company_id', '=', instance.company_id.id)], limit=1)

        if not partner:
            partner = partner_obj.with_context(tracking_disable=True).create({
                'name': buyer_name,
                'type': 'invoice',
                **new_partner_vals,
            })
            invoice_partner = partner
        elif (buyer_name and partner.name != buyer_name):
            partner.is_company = True
            invoice_partner = partner_obj.with_context(tracking_disable=True).create({
                'parent_id': partner.id,
                'name': buyer_name,
                'type': 'invoice',
                **new_partner_vals,
            })
        else:
            invoice_partner = partner

        delivery = invoice_partner if \
            (invoice_partner.name == shipping_address_name and invoice_partner.street == street
             and (not invoice_partner.street2 or invoice_partner.street2 == street2)
             and invoice_partner.zip == zip_code and invoice_partner.city == city
             and invoice_partner.country_id == country
             and invoice_partner.state_id == state) else False
        if not delivery:
            delivery = partner_obj.with_context(is_amazon_partner=True).search(
                [('name', '=', shipping_address_name), ('street', '=', street),
                 '|', ('street2', '=', False), ('street2', '=', street2), ('zip', '=', zip_code),
                 ('city', '=', city), ('country_id', '=', country.id if country else False),
                 ('state_id', '=', state.id if state else False),
                 '|', ('company_id', '=', False), ('company_id', '=', instance.company_id.id)], limit=1)
            if not delivery:
                invoice_partner.is_company = True
                delivery = partner_obj.with_context(tracking_disable=True).create({
                    'name': shipping_address_name,
                    'type': 'delivery',
                    'parent_id': invoice_partner.id,
                    **new_partner_vals,
                })
        if is_update_via_query:
            invoice_partner.message_post(body=_("<b>VAT Number [%s] is invalid!</b>" % str(vat)))
            if invoice_partner != delivery:
                delivery.message_post(body=_("<b>VAT Number [%s] is invalid!</b>" % str(vat)))
        return {'invoice_partner': invoice_partner.id, 'shipping_partner': delivery.id}

    # @staticmethod
    # def prepare_buy_partner_vals(row, instance):
    #     """
    #     Prepare Buy Partner values
    #     @author: Keyur kanani
    #     :param row: {}
    #     :param instance:amazon.instance.ept()
    #     :return: {}
    #     """
    #     return {
    #         'state_code': row.get('bill-state', False).capitalize(),
    #         'state_name': row.get('bill-state', False).capitalize(),
    #         'country_code': row.get('bill-country', False),
    #         'country_name': row.get('bill-country', False),
    #         'name': row.get('buyer-name', False),
    #         'street': row.get('bill-address-1', False),
    #         'street2': False,
    #         'city': row.get('bill-city', False),
    #         'phone': row.get('buyer-phone-number', False),
    #         'email': row.get('buyer-email', False),
    #         'zip': row.get('bill-postal-code', False),
    #         'lang': instance.lang_id and instance.lang_id.code or False,
    #         'company_id': instance.company_id and instance.company_id.id or False,
    #         'type': False,
    #         'is_company': False
    #     }

    # def create_partner_vals(self, address_type, vals, partner, state, country):
    #     """
    #     This method create the partner vals.
    #     :param type: Which type of partner, Like 'delivery', 'contact'
    #     :param vals: dictionary of values
    #     :param partner: partner object
    #     :param state: state object
    #     :param country: country object
    #     :return: partner vals
    #     """
    #     partner_vals = {
    #         'parent_id': partner.id,
    #         'type': address_type,
    #         'name': vals.get('name'),
    #         'email': vals.get('email'),
    #         'phone': vals.get('number'),
    #         'street': vals.get('address_1'),
    #         'street2': vals.get('address_2'),
    #         'city': vals.get('city'),
    #         'zip': vals.get('zip'),
    #         'state_id': state and state.id,
    #         'country_id': country.id
    #     }
    #     return partner_vals

    def create_or_find_amazon_fbm_product(self, order_ref, order_details, product_details, job):
        """
        This method is find product in odoo based on sku. If not found than create new product.
        :param sku:Product SKU
        :param product_name:Product name or Description
        :param seller_id:Seller Object
        :param instance: instance Object
        :return: Odoo Product Object
        """
        product_obj = self.env['product.product']
        amz_product_obj = self.env['amazon.product.ept']
        instance_obj = self.env['amazon.instance.ept']
        instance_id = instance_obj.browse(order_ref[1])
        skip_order = False
        for order_detail in order_details:
            sku = order_detail.get('sku').strip()
            amz_product = amz_product_obj.search(
                [('seller_sku', '=', sku), ('instance_id', '=', order_ref[1]), ('fulfillment_by', '=', 'FBM')])
            if not amz_product:
                odoo_product = product_obj.search([('default_code', '=', sku)])
                if not odoo_product and instance_id.seller_id.create_new_product:
                    odoo_product = product_obj.create({
                        'name': order_detail.get('product-name'),
                        'description_sale': order_detail.get('product-name'),
                        'default_code': sku,
                        'type': 'product'
                    })
                    amz_product = amz_product_obj.create({
                        'name': odoo_product.name,
                        'title': odoo_product.name,
                        'product_id': odoo_product.id,
                        'seller_sku': odoo_product.default_code,
                        'fulfillment_by': 'FBM',
                        'instance_id': order_ref[1]
                    })
                    job.log_lines.create({
                        'log_line_id': job.id,
                        'order_ref': order_ref[0],
                        'fulfillment_by': 'FBM',
                        'default_code': order_detail.get('sku'),
                        'message': 'Product is not available in Amazon Odoo Connector and Odoo, So it\'ll created in both.'
                    })
                elif odoo_product:
                    amz_product = amz_product_obj.create({
                        'name': odoo_product.name,
                        'title': odoo_product.name,
                        'product_id': odoo_product.id,
                        'seller_sku': odoo_product.default_code,
                        'fulfillment_by': 'FBM',
                        'instance_id': order_ref[1]
                    })
                else:
                    skip_order = True
                    job.log_lines.create({
                        'log_line_id': job.id,
                        'fulfillment_by': 'FBM',
                        'order_ref': order_ref[0],
                        'default_code': order_detail.get('sku'),
                        'message': 'Order skipped due to product is not available.'
                    })
            else:
                odoo_product = amz_product.product_id
            product_details.update({(sku, order_ref[1]): odoo_product})
        return skip_order, product_details

    def check_order_line_exist(self, instance, amz_ref, order_line_ref, sale_order_obj):
        """
        This method find the order line is exist in Sales order or not.
        :param instance:instance object
        :param amz_ref:Order Reference
        :param order_line_ref: Order Line reference
        :param sale_order_obj:Sale order Object
        :return: Order line or False
        """
        order = sale_order_obj.search(
            [('amz_instance_id', '=', instance.id), ('amz_order_reference', '=', amz_ref)])
        order_line = order.order_line.filtered(lambda x: x.amazon_order_item_id == order_line_ref)
        if order_line:
            return order_line
        else:
            return False

    def prepare_updated_ordervals(self, instance, order_ref):
        """
        This method prepare the order vals.
        :param expected_delivery_date: Expected Delivery Date
        :param instance: instance object
        :param seller: seller object
        :param order_ref: order reference
        :return: Order Vals
        """
        ordervals = {
            'amz_sales_order_report_id': self.id,
            'amz_instance_id': instance and instance.id or False,
            'amz_seller_id': instance.seller_id.id,
            'amz_fulfillment_by': 'FBM',
            'amz_order_reference': order_ref[0] or False,
            'auto_workflow_process_id': instance.seller_id.fbm_auto_workflow_id.id
        }
        return ordervals

    def amz_create_order_lines(self, order, instance, order_details, sale_order_line_obj, dict_product_details):
        """
        This method prepare order lines.
        :param order: order Object
        :param instance: instance object
        :param order_details: sale order line from dictionary
        :param sale_order_line_obj: sale order line object
        :return: True
        """
        for order_detail in order_details:
            if not order_detail.get('sku'):
                continue
            taxargs = {}
            product = dict_product_details.get((order_detail.get('sku'), instance.id))
            item_price = self.get_item_price(order_detail,instance)
            unit_price = item_price / float(order_detail.get('quantity-purchased'))
            item_tax = float(order_detail.get('item-tax'))
            if instance.is_use_percent_tax:
                item_tax_percent = ((item_tax/float(order_detail.get('quantity-purchased')) * 100)) / unit_price
                amz_tax_id = order.amz_instance_id.amz_tax_id
                taxargs = {'line_tax_amount_percent': item_tax_percent, 'tax_id': [(6, 0, [amz_tax_id.id])]}
            line_vals = {
                'order_id': order.id,
                'product_id': product.id,
                'company_id': instance.company_id.id or False,
                'name': order_detail.get('product-name'),
                'order_qty': order_detail.get('quantity-purchased'),
                'price_unit': unit_price,
                'discount': False,
                'shipping-price': order_detail.get('shipping-price', 0.0),
                'shipping-tax': order_detail.get('shipping-tax', 0.0)
            }
            order_line_vals = sale_order_line_obj.create_sale_order_line_ept(line_vals)
            order_line_vals.update({
                'amazon_order_item_id': order_detail.get('order-item-id'),
                'line_tax_amount': item_tax,
                **taxargs
            })
            sale_order_line_obj.create(order_line_vals)
            if float(order_detail.get('shipping-price')) > 0 and instance.seller_id.shipment_charge_product_id:
                taxargs = {}
                shipping_price = self.get_shipping_price(line_vals,instance)
                if instance.is_use_percent_tax:
                    shipping_tax = order_detail.get('shipping-tax', 0.0)
                    ship_tax_percent = (float(shipping_tax) * 100) / float(shipping_price)
                    amz_tax_id = order.amz_instance_id.amz_tax_id
                    taxargs = {'line_tax_amount': shipping_tax, 'line_tax_amount_percent': ship_tax_percent,
                               'tax_id': [(6, 0, [amz_tax_id.id])]}
                charges_vals = {
                    'order_id': order.id,
                    'product_id': instance.seller_id.shipment_charge_product_id.id,
                    'company_id': instance.company_id.id or False,
                    'name': instance.seller_id.shipment_charge_product_id.description_sale or instance.seller_id.shipment_charge_product_id.name,
                    'product_uom_qty': '1.0',
                    'price_unit': shipping_price,
                    'discount': False,
                    'amazon_order_item_id': order_detail.get('order-item-id'),
                    **taxargs
                }
                sale_order_line_obj.create(charges_vals)
            if float(order_detail.get(
                    'item-promotion-discount') or 0) > 0 and instance.seller_id.promotion_discount_product_id:
                item_discount = float(order_detail.get('item-promotion-discount')) * (-1)
                item_promotion_vals = {
                    'order_id': order.id,
                    'product_id': instance.seller_id.promotion_discount_product_id.id,
                    'company_id': instance.company_id.id or False,
                    'name': instance.seller_id.promotion_discount_product_id.description_sale or instance.seller_id.promotion_discount_product_id.name,
                    'product_uom_qty': '1.0',
                    'price_unit': item_discount,
                    'discount': False,
                    'amazon_order_item_id': order_detail.get('order-item-id')
                }
                sale_order_line_obj.create(item_promotion_vals)
            if float(order_detail.get(
                    'ship-promotion-discount') or 0) > 0 and instance.seller_id.ship_discount_product_id:
                ship_discount = float(order_detail.get('ship-promotion-discount')) * (-1)
                ship_promotion_vals = {
                    'order_id': order.id,
                    'product_id': instance.seller_id.ship_discount_product_id.id,
                    'company_id': instance.company_id.id or False,
                    'name': instance.seller_id.ship_discount_product_id.description_sale or instance.seller_id.ship_discount_product_id.name,
                    'product_uom_qty': '1.0',
                    'price_unit': ship_discount,
                    'discount': False,
                    'amazon_order_item_id': order_detail.get('order-item-id')
                }
                sale_order_line_obj.create(ship_promotion_vals)
        return True

    def amz_find_product(self, order_detail):
        """
        This method find the odoo product.
        :param order_detail: order line
        :return: odoo product object
        """
        amz_product_obj = self.env['amazon.product.ept']
        amz_product = amz_product_obj.search([('seller_sku', '=', order_detail.get('sku'))])
        product = amz_product.product_id
        return product

    def prepare_updated_orderline_vals(self, order_line_vals, order_detail):
        """
        This method prepare updated order line vals.
        :param order_line_vals: old order line vals
        :param order_detail: order line
        :return:order_line_vals
        """
        order_line_vals.update({
            'amazon_order_item_id': order_detail.get('order-item-id')
        })
        return order_line_vals

    def get_item_price(self, order_detail,instance):
        """
        This method addition the price and tax of product item cost.
        :param unit_price: item price
        :param tax: item tax
        :return: sum of price and tax.
        """
        unit_price = float(order_detail.get('item-price', 0.0))
        tax = float(order_detail.get('item-tax', 0.0))
        if self.seller_id.is_vcs_activated or (instance.amz_tax_id and not instance.amz_tax_id.price_include):
            return unit_price
        return unit_price + tax

    def get_shipping_price(self, order_detail,instance):
        """
        This method addition the price and tax of shipping cost.
        :param shipping_price: shipping price
        :param shipping_tax: shipping tax
        :return: sum of price and tax
        """
        shipping_price = float(order_detail.get('shipping-price', 0.0))
        shipping_tax = float(order_detail.get('shipping-tax', 0.0))
        if self.seller_id.is_vcs_activated or (instance.amz_tax_id and not instance.amz_tax_id.price_include):
            return shipping_price
        return shipping_price + shipping_tax

    def decode_amazon_encrypted_fbm_attachments_data(self, attachment_id, job):
        if self.is_encrypted_attachment:
            dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
            req = {
                'dbuuid': dbuuid,
                'report_id': self.report_id,
                'datas': attachment_id.datas.decode(),
                'amz_report_type': 'fbm_report'}
            response = iap.jsonrpc(DEFAULT_ENDPOINT + '/decode_data', params=req, timeout=1000)
            if response.get('result'):
                try:
                    imp_file = StringIO(base64.b64decode(response.get('result')).decode())
                except:
                    imp_file = StringIO(base64.b64decode(response.get('result')).decode('ISO-8859-1'))
            elif self._context.get('is_auto_process', False):
                job.log_lines.create({'message': 'Error found in Decryption of Data %s' % response.get('error', '')})
                return True
            else:
                raise Warning(response.get('error'))
        else:
            imp_file = StringIO(base64.b64decode(attachment_id.datas).decode())
        return imp_file
