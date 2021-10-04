# -*- coding: utf-8 -*-
import time
from datetime import datetime, timedelta
import base64
import csv
import pytz
from dateutil import parser
from io import StringIO, BytesIO
from odoo import models, fields, api, _
from odoo.exceptions import Warning
from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT
import logging

utc = pytz.utc
_logger = logging.getLogger(__name__)


class ShippingReportRequestHistory(models.Model):
    _name = "shipping.report.request.history"
    _description = "Shipping Report"
    _inherit = ['mail.thread']
    _order = 'id desc'

    @api.depends('seller_id')
    def get_company(self):
        """
        Find Company id on change of seller
        :return:  company_id
        """
        for record in self:
            company_id = record.seller_id.company_id.id if record.seller_id else False
            if not company_id:
                company_id = self.env.company.id
            record.company_id = company_id

    def get_order_count(self):
        """
        Get number of orders processed in the report
        :return:
        """
        self.order_count = len(self.amazon_sale_order_ids.ids)

    def get_moves_count(self):
        """
        Find all stock moves assiciated with this report
        :return:
        """
        stock_move_obj = self.env['stock.move']
        self.moves_count = stock_move_obj.search_count([('amz_shipment_report_id', '=', self.id)])

    def get_log_count(self):
        """
        Find all stock moves associated with this report
        :return:
        """
        log_obj = self.env['common.log.book.ept']
        model_id = self.env['ir.model']._get('shipping.report.request.history').id
        self.log_count = log_obj.search_count([('res_id', '=', self.id), ('model_id', '=', model_id)])

    name = fields.Char(size=256, string='Name')
    state = fields.Selection(
        [('draft', 'Draft'), ('_SUBMITTED_', 'SUBMITTED'), ('_IN_PROGRESS_', 'IN_PROGRESS'),
         ('_CANCELLED_', 'CANCELLED'), ('_DONE_', 'DONE'),
         ('partially_processed', 'Partially Processed'),
         ('_DONE_NO_DATA_', 'DONE_NO_DATA'), ('processed', 'PROCESSED')],
        string='Report Status', default='draft', help="Report Processing States")
    attachment_id = fields.Many2one('ir.attachment', string="Attachment",
                                    help="Find Shipping report from odoo Attachment")
    seller_id = fields.Many2one('amazon.seller.ept', string='Seller', copy=False,
                                help="Select Seller id from you wanted to get Shipping report")
    report_request_id = fields.Char(size=256, string='Report Request ID',
                                    help="Report request id to recognise unique request")
    report_id = fields.Char(size=256, string='Report ID',
                            help="Unique Report id for recognise report in Odoo")
    report_type = fields.Char(size=256, string='Report Type', help="Amazon Report Type")
    start_date = fields.Datetime('Start Date', help="Report Start Date")
    end_date = fields.Datetime('End Date', help="Report End Date")
    requested_date = fields.Datetime('Requested Date', default=time.strftime("%Y-%m-%d %H:%M:%S"),
                                     help="Report Requested Date")
    company_id = fields.Many2one('res.company', string="Company", copy=False,
                                 compute="get_company", store=True)
    user_id = fields.Many2one('res.users', string="Requested User",
                              help="Track which odoo user has requested report")
    amazon_sale_order_ids = fields.One2many('sale.order', 'amz_shipment_report_id',
                                            string="Sales Order Ids",
                                            help="For list all Orders created while shipment report process")
    order_count = fields.Integer(compute="get_order_count", string="Order Count", store=False,
                                 help="Count number of processed orders")
    moves_count = fields.Integer(compute="get_moves_count", string="Move Count", store=False,
                                 help="Count number of created Stock Move")
    log_count = fields.Integer(compute="get_log_count", string="Log Count", store=False,
                               help="Count number of created Stock Move")
    is_fulfillment_center = fields.Boolean(string="Is Fulfillment Center", default=False,
                                           help="if missing fulfillment center get then set as True")
    is_encrypted_attachment = fields.Boolean(string="Is Encrypted Attachment?", default=False,
                                             help="Used for identify encrypted attachments")

    def unlink(self):
        """
        This Method if report is processed then raise warning.
        """
        for report in self:
            if report.state == 'processed' or report.state == 'partially_processed':
                raise Warning(_('You cannot delete processed report.'))
        return super(ShippingReportRequestHistory, self).unlink()

    @api.constrains('start_date', 'end_date')
    def _check_duration(self):
        """
        Compare Start date and End date, If End date is before start date rate warning.
        @author: Keyur Kanani
        :return:
        """
        if self.start_date and self.end_date < self.start_date:
            raise Warning(_('Error!\nThe start date must be precede its end date.'))
        return True

    @api.model
    def default_get(self, fields):
        """
        Save report type when shipment report created
        @author: Keyur Kanani
        :param fields:
        :return:
        """
        res = super(ShippingReportRequestHistory, self).default_get(fields)
        if not fields:
            return res
        res.update({'report_type': '_GET_AMAZON_FULFILLED_SHIPMENTS_DATA_',
                    })
        return res

    def list_of_sales_orders(self):
        """
        List Amazon Sale Orders in Shipment View
        @author: Keyur Kanani
        :return:
        """
        action = {
            'domain': "[('id', 'in', " + str(self.amazon_sale_order_ids.ids) + " )]",
            'name': 'Amazon Sales Orders',
            'view_mode': 'tree,form',
            'res_model': 'sale.order',
            'type': 'ir.actions.act_window',
        }
        return action

    def list_of_process_logs(self):
        """
        List Shipment Report Log View
        @author: Keyur Kanani
        :return:
        """
        model_id = self.env['ir.model']._get('shipping.report.request.history').id
        action = {
            'domain': "[('res_id', '=', " + str(self.id) + " ), ('model_id','='," + str(model_id) + ")]",
            'name': 'Shipment Report Logs',
            'view_mode': 'tree,form',
            'res_model': 'common.log.book.ept',
            'type': 'ir.actions.act_window',
        }
        return action

    def list_of_stock_moves(self):
        """
        List All Stock Moves which is generated in a process
        @author: Keyur Kanani
        :return:
        """
        stock_move_obj = self.env['stock.move']
        records = stock_move_obj.search([('amz_shipment_report_id', '=', self.id)])
        action = {
            'domain': "[('id', 'in', " + str(records.ids) + " )]",
            'name': 'Amazon FBA Order Stock Move',
            'view_mode': 'tree,form',
            'res_model': 'stock.move',
            'type': 'ir.actions.act_window',
        }
        return action

    @api.model
    def create(self, vals):
        """
        Create Sequence for import Shipment Reports
        @author: Keyur Kanani
        :param vals: {}
        :return:
        """
        try:
            sequence = self.env.ref('amazon_ept.seq_import_shipping_report_job')
            if sequence:
                report_name = sequence.next_by_id()
            else:
                report_name = '/'
        except:
            report_name = '/'
        vals.update({'name': report_name})
        return super(ShippingReportRequestHistory, self).create(vals)

    @api.onchange('seller_id')
    def on_change_seller_id(self):
        """
        Set Start and End date of report as per seller configurations
        Default is 3 days
        @author: Keyur Kanani
        """
        if self.seller_id:
            self.start_date = datetime.now() - timedelta(self.seller_id.shipping_report_days)
            self.end_date = datetime.now()

    def prepare_amazon_request_report_kwargs(self, seller):
        """
        Prepare General Amazon Request dictionary.
        @author: Keyur Kanani
        :param seller: amazon.seller.ept()
        :return: {}
        """
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        instances_obj = self.env['amazon.instance.ept']
        instances = instances_obj.search([('seller_id', '=', seller.id)])
        marketplaceids = tuple(map(lambda x: x.market_place_id, instances))

        return {'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
                'auth_token': seller.auth_token and str(seller.auth_token) or False,
                'app_name': 'amazon_ept',
                'account_token': account.account_token,
                'dbuuid': dbuuid,
                'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                           seller.country_id.code,
                'marketplaceids': marketplaceids,
                }

    def report_start_and_end_date(self):
        """
        Prepare Start and End Date for request reports
        @author: Keyur Kanani
        :return: start_date, end_date
        """
        start_date, end_date = self.start_date, self.end_date
        if start_date:
            db_import_time = start_date.strftime("%Y-%m-%dT%H:%M:%S")
            start_date = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(
                time.mktime(time.strptime(db_import_time, "%Y-%m-%dT%H:%M:%S"))))
            start_date = str(start_date) + 'Z'
        else:
            today = datetime.now()
            earlier = today - timedelta(days=30)
            earlier_str = earlier.strftime("%Y-%m-%dT%H:%M:%S")
            start_date = earlier_str + 'Z'
        if end_date:
            db_import_time = end_date.strftime("%Y-%m-%dT%H:%M:%S")
            end_date = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(
                time.mktime(time.strptime(db_import_time, "%Y-%m-%dT%H:%M:%S"))))
            end_date = str(end_date) + 'Z'
        else:
            today = datetime.now()
            earlier_str = today.strftime("%Y-%m-%dT%H:%M:%S")
            end_date = earlier_str + 'Z'

        return start_date, end_date

    def request_report(self):
        """
        Request _GET_AMAZON_FULFILLED_SHIPMENTS_DATA_ Report from Amazon for specific date range.
        @author: Keyur Kanani
        :return: Boolean
        """
        seller, report_type = self.seller_id, self.report_type
        common_log_book_obj = self.env['common.log.book.ept']
        if not seller:
            raise Warning(_('Please select Seller'))

        start_date, end_date = self.report_start_and_end_date()

        kwargs = self.prepare_amazon_request_report_kwargs(seller)
        kwargs.update({
            'emipro_api': 'shipping_request_report_v13',
            'report_type': report_type,
            'start_date': start_date,
            'end_date': end_date,
        })
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            if self._context.get('is_auto_process'):
                common_log_book_obj.create({
                    'type': 'import',
                    'module': 'amazon_ept',
                    'active': True,
                    'log_lines': [(0, 0, {'message': response.get('reason')})]
                })
            else:
                raise Warning(response.get('reason'))
        else:
            result = response.get('result')
            self.update_report_history(result)
        return True

    def update_report_history(self, request_result):
        """
        Update Report History in odoo
        @author: Keyur Kanani
        :param request_result:
        :return:
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

    def get_report_list(self):
        """
        Call Get report list api from amazon
        @author: Keyur Kanani
        :return:
        """
        self.ensure_one()
        common_log_book_obj = self.env['common.log.book.ept']
        list_of_wrapper = []
        if not self.seller_id:
            raise Warning(_('Please select seller'))

        kwargs = self.prepare_amazon_request_report_kwargs(self.seller_id)
        kwargs.update({'emipro_api': 'get_report_list_v13', 'request_id': [self.request_id]})
        if not self.request_id:
            return True

        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            if self._context.get('is_auto_process'):
                common_log_book_obj.create({
                    'type': 'import',
                    'module': 'amazon_ept',
                    'active': True,
                    'log_lines': [(0, 0,
                                   {'message': 'Shipping Report Process ' + response.get('reason')}
                                   )]
                })
            else:
                raise Warning(response.get('reason'))
        else:
            list_of_wrapper = response.get('result')

        for result in list_of_wrapper:
            self.update_report_history(result)
        return True

    def get_report_request_list(self):
        """
        Get Report Requests List from Amazon, Check Status of Process.
        @author: Keyur kanani
        :return: Boolean
        """
        self.ensure_one()
        if not self.seller_id:
            raise Warning(_('Please select Seller'))
        if not self.report_request_id:
            return True
        kwargs = self.prepare_amazon_request_report_kwargs(self.seller_id)
        kwargs.update({'emipro_api': 'get_report_request_list_v13', 'request_ids': (self.report_request_id)})

        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if not response.get('reason'):
            list_of_wrapper = response.get('result')
        else:
            raise Warning(response.get('reason'))
        for result in list_of_wrapper:
            self.update_report_history(result)
        return True

    def amz_search_or_create_logs_ept(self, response):
        common_log_book_obj = self.env['common.log.book.ept']
        model_id = self.env['ir.model']._get('shipping.report.request.history').id
        log = common_log_book_obj.search([('module', '=', 'amazon_ept'),('model_id','=',model_id),('res_id','=',self.id)])
        if not log:
            log = common_log_book_obj.create({
                'type': 'import',
                'module': 'amazon_ept',
                'model_id': model_id,
                'res_id': self.id,
                'active': True,
                'log_lines': [(0, 0, {'message': 'Shipping Report Process ' + response.get('reason', '')})]
            })
        return log

    def get_report(self):
        """
        Get Shipment Report as an attachment in Shipping reports form view.
        @author: Keyur kanani
        :return:
        """
        self.ensure_one()
        result = {}
        seller = self.seller_id
        if not seller:
            raise Warning(_('Please select seller'))
        if not self.report_id:
            return True
        kwargs = self.prepare_amazon_request_report_kwargs(self.seller_id)
        kwargs.update({'emipro_api': 'get_report_v13', 'report_id': self.report_id, 'amz_report_type': 'shipment_report'})
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            if self._context.get('is_auto_process'):
                self.amz_search_or_create_logs_ept(response)
            else:
                raise Warning(response.get('reason'))
        else:
            result = response.get('result')
        if result:
            file_name = "Shipment_report_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'
            attachment = self.env['ir.attachment'].create({
                'name': file_name,
                'datas': result.encode(),
                'res_model': 'mail.compose.message',
                'type': 'binary'
            })
            self.message_post(body=_("<b>Shipment Report Downloaded</b>"), attachment_ids=attachment.ids)
            self.is_encrypted_attachment = True
            """
            Get Missing Fulfillment Center from attachment file
            If get missing Fulfillment Center then set true value of field is_fulfillment_center
            @author: Deval Jagad (09/01/2020)
            """
            unavailable_fulfillment_center = self.get_missing_fulfillment_center(attachment)
            is_fulfillment_center = False
            if unavailable_fulfillment_center:
                is_fulfillment_center = True
            self.write({'attachment_id': attachment.id, 'is_fulfillment_center': is_fulfillment_center})
        return True

    def download_report(self):
        """
        Download Shipment Report from Attachment
        @author: Keyur kanani
        :return: boolean
        """
        self.ensure_one()
        if self.attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' % (self.attachment_id.id),
                'target': 'self',
            }
        return True

    def process_shipment_file(self):
        """
        Process Amazon Shipment File from attachment,
        Import FBA Sale Orders and Sale Order lines for specific amazon Instance
        Test Cases: https://docs.google.com/spreadsheets/d/1IcbZM7o7k4V4DccN3nbR_QpXnBBWbztjpglhpNQKC_c/edit?usp=sharing
        @author: Keyur kanani
        :return: True
        """
        self.ensure_one()
        ir_cron_obj = self.env['ir.cron']
        if not self._context.get('is_auto_process', False):
            ir_cron_obj.with_context({'raise_warning': True}).find_running_schedulers(
                'ir_cron_process_amazon_fba_shipment_report_seller_', self.seller_id.id)

        if not self.attachment_id:
            raise Warning(_("There is no any report are attached with this record."))

        common_log_book_obj = self.env['common.log.book.ept']
        marketplace_obj = self.env['amazon.marketplace.ept']
        stock_move_obj = self.env['stock.move']
        sale_order_obj = self.env["sale.order"]
        instances = {}
        order_dict = {}
        transaction_log_lines = []
        b2b_order_list = []
        order_details_dict_list = {}
        outbound_orders_dict = {}
        fulfillment_warehouse = {}
        skip_orders = []

        model_id = self.env['ir.model']._get('shipping.report.request.history').id
        job = common_log_book_obj.search(
            [('model_id', '=', model_id),
             ('res_id', '=', self.id)])
        if not job:
            common_log_book_vals = {
                'type': 'import',
                'module': 'amazon_ept',
                'model_id': model_id,
                'res_id': self.id,
                'active': True,
                'log_lines': [(0, 0, {'message': 'Shipment Report Import Start'})]
            }
            job = common_log_book_obj.create(common_log_book_vals)
        imp_file = self.decode_amazon_encrypted_attachments_data(self.attachment_id, job)
        reader = csv.DictReader(imp_file, delimiter='\t')
        for row in reader:
            if row.get('sales-channel', '') == "Non-Amazon":
                order = sale_order_obj.search([
                    ("amz_order_reference", "=", row.get('merchant-order-id', "")),
                    ("amz_is_outbound_order", "=", True)])
                instance = order.amz_fulfillment_instance_id
            elif row.get('sales-channel', '') not in instances:
                instance = marketplace_obj.find_instance(self.seller_id, row.get('sales-channel', ''))
                instances.update({row.get('sales-channel', ''): instance})
            else:
                instance = instances.get(row.get('sales-channel', ''))
            if not instance:
                log_line_vals = {
                    'order_ref': row.get('amazon-order-id'),
                    'message': 'Skipped Amazon order (%s) because Sales Channel (%s) not found in Odoo. ' % (
                        row.get('amazon-order-id'), row.get('sales-channel'))}
                transaction_log_lines.append((0, 0, log_line_vals))
                continue
            if row.get('merchant-order-id', False):
                result = self.env['shipping.report.order.history'].verify_outbound_order_processed(row, instance.id)
                if result:
                    continue
            where_clause = (row.get('shipment-id'), instance.id, row.get('amazon-order-id'),
                            row.get('amazon-order-item-id').lstrip('0'), row.get('shipment-item-id'))
            if order_dict.get(where_clause):
                log_line_vals = {
                    'order_ref': row.get('amazon-order-id'),
                    'message': 'Amazon order %s Already Available in Odoo' % (
                        row.get('amazon-order-id'))}
                transaction_log_lines.append((0, 0, log_line_vals))
                continue
            move_found = stock_move_obj.search(
                [('amazon_shipment_id', '=', row.get('shipment-id')), ('amazon_instance_id', '=', instance.id),
                 ('amazon_order_reference', '=', row.get('amazon-order-id')),
                 ('amazon_order_item_id', '=', row.get('amazon-order-item-id').lstrip('0')),
                 ('amazon_shipment_item_id', '=', row.get('shipment-item-id'))])
            if move_found:
                for move in move_found.filtered(lambda x: x.state not in ('done', 'cancel')):
                    move._do_unreserve()
                    move._action_assign()
                    move._set_quantity_done(move.product_uom_qty)
                    self.validate_stock_move(move, job, row.get('amazon-order-id'))
                order_dict.update({where_clause: move_found})
                continue
            row.update({'instance_id': instance.id})
            # Fullfilment centers
            if row.get('amazon-order-id') not in skip_orders:
                fulfillment_id = row.get('fulfillment-center-id')
                if fulfillment_id not in fulfillment_warehouse:
                    fulfillment_center, fn_warehouse = self.get_warehouse(fulfillment_id, instance)
                    if not fn_warehouse:
                        skip_orders.append(row.get('amazon-order-id'))
                        log_line_vals = {
                            'order_ref': row.get('amazon-order-id'),
                            'message': 'Skipped Amazon order %s because Amazon Fulfillment Center not found in Odoo' % (
                                row.get('amazon-order-id'))}
                        transaction_log_lines.append((0, 0, log_line_vals))
                        continue
                    fulfillment_warehouse.update({fulfillment_id: [fn_warehouse, fulfillment_center]})
                warehouse = fulfillment_warehouse.get(fulfillment_id, [False])[0]
                fullfillment_center = fulfillment_warehouse.get(fulfillment_id, [False])[1]
                row.update({'fulfillment_center': fullfillment_center.id, 'warehouse': warehouse.id})
            if row.get('merchant-order-id', False):
                outbound_orders_dict = self.prepare_amazon_sale_order_line_values(row, outbound_orders_dict)
            else:
                order_details_dict_list = self.prepare_amazon_sale_order_line_values(row, order_details_dict_list)
                if row.get('amazon-order-id', False) and row.get('amazon-order-id') not in b2b_order_list:
                    b2b_order_list.append(row.get('amazon-order-id'))
        if transaction_log_lines:
            job.write({'log_lines': transaction_log_lines})
        if outbound_orders_dict:
            if self.seller_id.amz_fba_us_program == 'narf':
                self.process_narf_outbound_orders(outbound_orders_dict, job)
            elif self.seller_id.amazon_program == 'pan_eu':
                self.process_pan_eu_outbound_orders(outbound_orders_dict, job)
            else:
                self.process_outbound_orders(outbound_orders_dict, job)
        if order_details_dict_list:
            if self.seller_id.is_european_region:
                self.request_and_process_b2b_order_response_ept(order_details_dict_list, b2b_order_list, job)
            else:
                self.process_fba_shipment_orders(order_details_dict_list, {}, job, b2b_order_list)
        self.write({'state': 'processed'})
        return True

    def get_amazon_order(self, order_ref, job):
        """
            Gets Amazon order based on order reference.
            :param order_ref: str
            :param job: common.log.book.ept
            :return: sale.order
        """
        amz_order = self.env["sale.order"].search([('amz_order_reference', '=', order_ref),
                                                   ('amz_is_outbound_order', '=', True),
                                                   ('amz_seller_id', '=', self.seller_id.id)])
        if not amz_order:
            message = "Order %s is not found." % order_ref
            model_id = self.env['ir.model']._get('shipping.report.request.history').id
            self.env['common.log.lines.ept'].amazon_create_common_log_line_ept(message, model_id, self.id, job)
            return amz_order
        for sale_order in amz_order:
            if amz_order.picking_ids and all([p.state in ('done', 'cancel') for p in sale_order.picking_ids]):
                amz_order -= sale_order
        return amz_order

    def get_amazon_product(self, instance, sku, job):
        """
            Gets Amazon product based on SKU and instance.
            :param instance: amazon.instance.ept
            :param sku: str
            :param job: common.log.book.ept
            :return amazon.product.ept or bool
        """
        amz_product = self.env['amazon.product.ept'].search_amazon_product(instance.id, sku, 'FBA')
        if not amz_product:
            model_id = self.env['ir.model']._get('shipping.report.request.history').id
            message = 'Amazon product {} could not be found for instance {}.'.format(sku, instance.name)
            self.env["common.log.lines.ept"].amazon_create_common_log_line_ept(message, model_id, self.id, job)
        return amz_product

    @staticmethod
    def get_shipment_details(dict_val):
        """
            Gets shipment details from dictionary.
            :param dict_val: dict
            :return: tuple
        """
        return (dict_val.get('shipment-id', ''), dict_val.get('warehouse', False), float(dict_val.get('quantity-shipped', 0.0)),
                dict_val.get('sku', False), str(dict_val.get('shipment-item-id', False)))

    def prepare_pan_eu_orders_dict(self, amz_order, dict_vals, job, order_data, order_lines):
        """
            Prepares PAN EU outbound orders dict warehouse wise.
            :param amz_order: sale.order
            :param dict_vals: dict
            :param job: common.log.book.ept
            :param order_data: dict
            :param order_lines: sale.order.line
            :return: tuple
        """
        model_id = self.env['ir.model']._get('shipping.report.request.history').id
        for dict_val in dict_vals:
            shipment_id, fc_warehouse_id, shipped_qty, product_sku, ship_item_id = self.get_shipment_details(dict_val)
            amz_product = self.get_amazon_product(amz_order.amz_instance_id, product_sku, job)
            if not amz_product:
                continue
            product = amz_product.product_id
            ord_line = amz_order.order_line.filtered(lambda ol: ol.product_id.id == product.id)
            if not ord_line:
                message = 'Skipped an order line because product named {} is not available.'.format(product.name)
                self.env['common.log.lines.ept'].amazon_create_common_log_line_ept(message, model_id, self.id, job)
                continue
            if fc_warehouse_id not in list(order_data.keys()):
                order_data.update({fc_warehouse_id: {product.id: [dict_val]}})
            else:
                product_data = order_data.get(fc_warehouse_id)
                if product.id in product_data.keys():
                    product_data.update({product.id: product_data.get(product.id) + [dict_val]})
                else:
                    product_data.update({product.id: [dict_val]})
        if amz_order.warehouse_id.id in list(order_data.keys()):
            shipment_data = order_data.get(amz_order.warehouse_id.id)
            order_data.pop(amz_order.warehouse_id.id)
            order_data.update({amz_order.warehouse_id.id: shipment_data})
        return amz_order, dict_vals, order_data, order_lines

    def process_pan_eu_outbound_dict(self, amz_order, order_lines, order_data, orders_to_process):
        """
            Processes Prepared PAN EU outbound dict.
            :param amz_order: sale.order
            :param order_lines: sale.order.line
            :param order_data: dict
            :param orders_to_process: sale.order
            :return: tuple
        """
        should_cancel = []
        for warehouse, product_data in order_data.items():
            if warehouse == amz_order.warehouse_id.id:
                amz_order.filtered(lambda o: o.state in ['draft', 'sent']).action_confirm()
                for product_id, shipment_data in product_data.items():
                    line = order_lines.filtered(lambda ol: ol.product_id.id == product_id and ol.product_uom_qty != 0.0)
                    self.amz_update_stock_move(line, shipment_data)
                amz_order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel']).move_lines._action_done()
                self.amazon_check_back_order_ept(amz_order)
                orders_to_process |= amz_order
            else:
                if len(list(order_data.keys())) == 1 and self.should_process_whole_order(product_data, order_lines):
                    amz_order.warehouse_id = warehouse
                    amz_order.onchange_warehouse_id()
                    amz_order.filtered(lambda o: o.state in ['draft', 'sent']).action_confirm()
                    self.update_amz_stock_move_ept(amz_order, product_data)
                    orders_to_process |= amz_order
                else:
                    new_order, flag = self.get_historical_or_create_new_order(amz_order, warehouse, product_data)
                    if flag:
                        for product_id, shipment_data in product_data.items():
                            done_qty = sum([float(val.get('quantity-shipped', 0.0)) for val in shipment_data])
                            lines = order_lines.filtered(lambda ol: ol.product_id.id == product_id)
                            for line in lines:
                                amz_extra_vals = self.amz_prepare_outbound_order_line_extra_vals(line)
                                if line.product_uom_qty > 0 and line.product_uom_qty <= done_qty:
                                    line.copy(default={'order_id': new_order.id, 'product_uom_qty': line.product_uom_qty,
                                                       **amz_extra_vals})
                                    done_qty -= line.product_uom_qty
                                    line.product_uom_qty -= line.product_uom_qty
                                elif line.product_uom_qty > 0:
                                    line.copy(default={'order_id': new_order.id, 'product_uom_qty': done_qty,
                                                       **amz_extra_vals})
                                    line.product_uom_qty -= done_qty
                        if amz_order.state not in ['draft', 'sent']:
                            should_cancel.append(amz_order)
                    new_order.order_line.filtered(lambda ol: ol.product_uom_qty == 0.0).unlink()
                    new_order.action_confirm()
                    self.update_amz_stock_move_ept(new_order, product_data)
                    orders_to_process |= new_order
        self.cancel_remaining_pickings(should_cancel)
        return amz_order, order_lines, order_data, orders_to_process

    @staticmethod
    def cancel_remaining_pickings(amazon_orders):
        """
            Cancels an existing picking and creates new one.
            :param amazon_orders: list
            :return: None
        """
        for amazon_order in list(set(amazon_orders)):
            if amazon_order.picking_ids:
                amazon_order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel']).action_cancel()
                amazon_order.action_confirm()

    def prepare_amz_update_stock_move_vals(self, order, shipment_vals):
        """
            Prepares stock move values.
            :param order: sale.order
            :param shipment_vals: list
            :return: dict
        """
        return {
            'amazon_shipment_id': ','.join(list(set([val.get('shipment-id') for val in shipment_vals]))),
            'amazon_shipment_item_id': ','.join([val.get('shipment-item-id') for val in shipment_vals]),
            'amazon_order_item_id': ','.join([val.get('amazon-order-item-id') for val in shipment_vals]),
            'amazon_order_reference': order.amz_order_reference,
            'amazon_instance_id': order.amz_instance_id.id,
            'tracking_number': ','.join(list(set([val.get('tracking-number') for val in shipment_vals]))),
            'amz_shipment_report_id': self.id
        }

    def amz_update_stock_move(self, line, shipment_vals):
        """
            Updates stock move.
            :param line: sale.order.line
            :param shipment_vals: list
            :return: None
        """
        move = line.move_ids.filtered(lambda m: m.state not in ['done', 'cancel'] and not m.amazon_shipment_id)
        move = move.filtered(lambda m: m.picking_id.state not in ['done', 'cancel'] and m.picking_id.location_dest_id.usage == 'customer')
        move_vals = self.prepare_amz_update_stock_move_vals(line.order_id, shipment_vals)
        move._action_assign()
        move._set_quantity_done(sum([float(val.get('quantity-shipped', 0.0)) for val in shipment_vals]))
        move.write(move_vals)

    def update_amz_stock_move_ept(self, order, product_data):
        """
            Updates Amazon stock move.
            :param order: sale.order
            :param product_data: dict
            :return: None
        """
        pickings = order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'])
        for move in pickings.move_lines.filtered(lambda m: m.state not in ['done', 'cancel']):
            move._action_assign()
            move._set_quantity_done(move.product_uom_qty)
        order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel']).move_lines._action_done()
        for product_id, ship_data in product_data.items():
            line = order.order_line.filtered(lambda ol: ol.product_id.id == product_id)
            move = line.move_ids.filtered(lambda m: m.state == 'done' and m.picking_id.location_dest_id.usage == 'customer' and not m.amazon_shipment_id)
            move_vals = self.prepare_amz_update_stock_move_vals(line.order_id, ship_data)
            move.write(move_vals)

    @staticmethod
    def should_process_whole_order(product_data, order_lines):
        """
            Decides whether a whole order should be processed at once or not.
            :param product_data: dict
            :param order_lines: sale.order.line
            :return: bool
        """
        flag = True
        order_line_data = {}
        for line in order_lines:
            if line.product_id.id in order_line_data:
                order_line_data.update({line.product_id.id: order_line_data.get(line.product_id.id) + line.product_uom_qty})
            else:
                order_line_data.update({line.product_id.id: line.product_uom_qty})
        shipping_data = {}
        for prod_id, data in product_data.items():
            shipped_qty = sum([float(i.get('quantity-shipped', 0.0)) for i in data])
            if prod_id in shipping_data:
                shipping_data.update({prod_id: shipping_data.get(prod_id) + shipped_qty})
            else:
                shipping_data.update({prod_id: shipped_qty})

        for prod_id, qty in order_line_data.items():
            if not (prod_id in list(shipping_data.keys()) and shipping_data.get(prod_id) == order_line_data.get(prod_id)):
                flag = False
                break
        return flag

    def should_change_warehouse(self, amz_order, product_data):
        """
            Checks whether it should change warehouse of an order or create new order to process remaining order lines.
            :param amz_order: sale.order
            :param product_data: dict
            :return: bool
        """
        lines_without_zero_qty = amz_order.order_line.filtered(lambda ol: ol.product_uom_qty != 0.0)
        return self.should_process_whole_order(product_data, lines_without_zero_qty)

    def get_amz_new_order_name(self, amazon_order, seq):
        """
            Creates new name for new Amazon order.
            :param amazon_order: sale.order
            :param seq: int
            :return: str
        """
        new_name = amazon_order.name + '/' + str(seq)
        if self.env['sale.order'].search([('name', '=', new_name)]):
            seq += 1
            return self.get_amz_new_order_name(amazon_order, seq)
        return new_name

    def get_historical_or_create_new_order(self, amz_order, warehouse, product_data):
        """
            Gets historical order or creates new order.
            :param amz_order: sale.order
            :param warehouse: int
            :param product_data: dict
            :return: tuple
        """
        flag = True
        orders = self.env["sale.order"].search([('amz_order_reference', '=', amz_order.amz_order_reference), ('amz_is_outbound_order', '=', True),
                                                   ('amz_seller_id', '=', self.seller_id.id)])
        historical_order = orders.filtered(lambda o: o.warehouse_id.id == warehouse)
        if historical_order:
            new_order = historical_order
        else:
            if self.should_change_warehouse(amz_order, product_data):
                flag = False
                new_order = amz_order
                new_order.warehouse_id = warehouse
                new_order.onchange_warehouse_id()
            else:
                new_name = self.get_amz_new_order_name(amz_order, 1)
                new_order = amz_order.copy(default={'name': new_name, 'order_line': None, 'warehouse_id': warehouse})
                new_order.onchange_warehouse_id()
        return new_order, flag

    def amz_prepare_outbound_order_line_extra_vals(self, line):
        """
            Prepares extra values for sale order line in order to use them in outbound orders.
            :param line: sale.order.line
            :return: dict
        """
        return {}

    def amazon_check_back_order_ept(self, order):
        """
            Checks for back order.
            :param order: sale.order
            :return: None
        """
        if order.picking_ids._check_backorder():
            picking = order.picking_ids.filtered(lambda x: x.state not in ['done', 'cancel', 'confirmed'])
            if not picking:
                order.picking_ids.filtered(lambda x: x.state == 'confirmed').move_lines._action_assign()
            else:
                self.env['stock.backorder.confirmation'].create({'pick_ids': [(4, p.id) for p in picking]}).process()
                back_order = order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'] and p.backorder_id.id)
                if back_order:
                    back_order.move_lines._action_assign()

    def process_pan_eu_outbound_orders(self, outbound_orders_dict, job):
        """
            Processes outbound orders for PAN EU program enabled sellers.
            @author: Sunil Khatri
            :param outbound_orders_dict: dict
            :param job: common.log.book.ept
            :return: None
        """
        model_id = self.env['ir.model']._get('shipping.report.request.history').id
        sale_order_obj = self.env["sale.order"]
        for order_ref, dict_vals in outbound_orders_dict.items():
            orders_to_process, amz_order = sale_order_obj, self.get_amazon_order(order_ref, job)
            if not amz_order:
                continue
            order_lines = amz_order.order_line.filtered(lambda ol: ol.product_type != 'service')
            if not order_lines:
                msg = 'Skipped an order named {} because order lines with non service type products were not found.'.format(amz_order.name)
                self.env['common.log.lines.ept'].amazon_create_common_log_line_ept(msg, model_id, self.id, job)
                continue
            order_data = {}

            # Prepares outbound orders dictionary warehouse wise.
            amz_order, dict_vals, order_data, order_lines = \
                self.prepare_pan_eu_orders_dict(amz_order, dict_vals, job, order_data, order_lines)

            # Processes prepared dictionary.
            amz_order, order_lines, order_data, orders_to_process = \
                self.process_pan_eu_outbound_dict(amz_order, order_lines, order_data, orders_to_process)

            # Binds Amazon details to orders and then creates invoices as per workflow.
            if orders_to_process:
                orders_to_process.write({'amz_shipment_report_id': self.id})
                self.bind_amazon_data(orders_to_process.order_line, dict_vals, job)
                self.amz_create_invoices_as_per_workflow(orders_to_process, model_id, job)

            # Deletes order lines which have 0 quantity and deletes sale order which has no order line.
            amz_order.order_line.filtered(lambda ol: ol.product_uom_qty == 0.0).unlink()
            if not amz_order.order_line:
                amz_order.action_cancel()
                amz_order.unlink()
            self.env.cr.commit()

    def amz_create_invoices_as_per_workflow(self, orders, model_id, job):
        """
            Creates invoices of sale order as per workflow.
            :param orders: sale.order
            :param model_id: int
            :param job: common.log.book.ept
            :return: None
        """
        for order in orders:
            auto_workflow_process_id = order.auto_workflow_process_id
            if not auto_workflow_process_id:
                auto_workflow_process_id = order.amz_seller_id.fba_auto_workflow_id
                order.auto_workflow_process_id = auto_workflow_process_id and auto_workflow_process_id.id
            try:
                order.validate_and_paid_invoices_ept(auto_workflow_process_id)
            except Exception as ex:
                self.env['common.log.lines.ept'].amazon_create_common_log_line_ept(ex, model_id, self.id, job)

    def bind_amazon_data(self, order_lines, dict_vals, log_rec):
        """
            Binds amazon data to stock picking and stock moves on processed orders.
            :param log_rec:
            :param order_lines: sale.order.line
            :param dict_vals: dict
            :return: bool
        """
        for val in dict_vals:
            shipment_id, fc_warehouse, shipped_qty, sku, ship_item_id = self.get_shipment_details(val)
            amz_product = self.get_amazon_product(order_lines.order_id.amz_instance_id, sku, log_rec)
            if not amz_product:
                continue
            product = amz_product.product_id
            line = order_lines.filtered(lambda ol: ol.product_id.id == product.id and ol.order_id.warehouse_id.id == fc_warehouse)
            move = line.move_ids.filtered(lambda m: m.state == 'done' and shipment_id in m.amazon_shipment_id.split(','))
            move.fulfillment_center_id = val.get('fulfillment_center', '')
            move.filtered(lambda m: m.state not in ['done', 'cancel'])._action_assign()
            carrier_id = False
            if val.get('carrier', ''):
                carrier_id = self.env['sale.order'].get_amz_shipping_method(val.get('carrier', ''), line.order_id.amz_seller_id.shipment_charge_product_id)
            picking = move.picking_id.filtered(lambda p: not p.backorder_id) or move.picking_id
            if not picking.amazon_shipment_id:
                vals = self.prepare_outbound_picking_update_vals_ept(val, carrier_id, val.get('tracking-number', ''))
                picking.write(vals)
            if picking.carrier_tracking_ref:
                if val.get('tracking-number', '') not in picking.carrier_tracking_ref.split(','):
                    picking.carrier_tracking_ref = picking.carrier_tracking_ref + ',' + val.get('tracking-number', '')
            else:
                picking.carrier_tracking_ref = val.get('tracking-number', '')
        return True

    @staticmethod
    def prepare_outbound_picking_update_vals_ept(ship_line, carrier_id, track_num):
        """
            Prepare picking values for outbound orders.
            :param ship_line: dict
            :param carrier_id: int
            :param track_num: str
            :return: dict
        """
        vals = {
            "amazon_shipment_id": ship_line.get('shipment-id', False),
            "is_fba_wh_picking": True,
            "fulfill_center": ship_line.get('fulfillment_center', False),
            "updated_in_amazon": True,
            "carrier_id": carrier_id,
            "carrier_tracking_ref": track_num
        }
        if ship_line.get('estimated-arrival-date', False):
            estimated_arrival = parser.parse(ship_line.get('estimated-arrival-date', '')).astimezone(utc).strftime('%Y-%m-%d %H:%M:%S')
            vals.update({'estimated_arrival_date': estimated_arrival})
        return vals

    def validate_stock_move(self, move, job, order_name):
        """
        Use: Validate the stock move and if getting any warning then create log

        Added by: Sagar Sakaria @Emipro Technologies
        Added on: 21st June, 2021
        :return:
        """
        try:
            move._action_done()
        except Exception as exception:
            log_line_vals = {'message': 'Stock move is not done of order %s Due to %s' % (order_name, exception), 'fulfillment_by': 'FBA'}
            transaction_log_lines = [(0, 0, log_line_vals)]
            job.write({'log_lines': transaction_log_lines})
        return True

    def process_narf_outbound_orders(self, outbound_orders_dict, job):
        """
            Processes outbound orders for NARF enabled sellers.
            
            @author: Sunil Khatri \n
            @creation_date: 01/05/2021 \n

            :param outbound_orders_dict: dict
            :param job: common connector log object
            :return: True
        """
        for order_ref, lines in outbound_orders_dict.items():
            amazon_order = self.get_amazon_outbound_order(order_ref, job)
            if not amazon_order:
                continue
            pickings = amazon_order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'])
            if not pickings:
                continue
            shipment_dict = {}
            for line in lines:
                shipment_dict.update({
                    line.get('shipment-id'): [line] if line.get('shipment-id') not in shipment_dict else
                    shipment_dict.get(line.get('shipment-id')) + [line]
                })
            for ship_id, ship_lines in shipment_dict.items():
                prod_dict, track_list, track_num = {}, [], ''
                pickings = amazon_order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'])
                if not pickings:
                    continue
                for ship_line in ship_lines:
                    if ship_line.get('tracking-number', False) and ship_line.get('tracking-number') not in track_list:
                        track_list.append(ship_line.get('tracking-number'))
                        track_num = ship_line.get('tracking-number') if not track_num else \
                            track_num + ',' + ship_line.get('tracking-number')
                    prod_dict = self.prepare_outbound_product_dict(amazon_order, ship_line, prod_dict, job)
                for product, shipped_qty in prod_dict.items():
                    stock_move_lines = pickings.move_line_ids.filtered(lambda mli: mli.product_id.id == product.id)
                    if not stock_move_lines:
                        stock_moves = pickings.move_lines.filtered(lambda ml: ml.product_id.id == product.id)
                        sml_vals = self.prepare_outbound_stock_move_lines(product, pickings, shipped_qty, stock_moves)
                        stock_move_lines = stock_move_lines.create(sml_vals)
                    else:
                        stock_move_lines.move_id._set_quantity_done(float(shipped_qty))
                    sm_vals = self.prepare_outbound_stock_move_update_values(ship_id, amazon_order, ship_line, track_num)
                    stock_move_lines.move_id.write(sm_vals)
                    carrier_id = False
                    if ship_line.get('carrier', ''):
                        carrier_id = self.env["sale.order"].get_amz_shipping_method(ship_line.get('carrier', ''),
                                                                       amazon_order.amz_seller_id.shipment_charge_product_id)
                    if not pickings.amazon_shipment_id:
                        pick_vals = self.prepare_outbound_picking_update_values(ship_line, carrier_id,
                                                                                  track_num)
                        pickings.write(pick_vals)
                self.amazon_fba_shipment_report_workflow(amazon_order, job)
        return True

    @staticmethod
    def prepare_outbound_picking_update_values(ship_line, carrier_id, track_num):
        """
            Prepares values to update outbound orders details in picking.

            :param ship_line: dict
            :param carrier_id: int
            :param track_num: str
            :return: dict
        """
        vals = {
            "amazon_shipment_id": ship_line.get("shipment-id"),
            "is_fba_wh_picking": True,
            "fulfill_center": ship_line.get("fulfillment_center"),
            "updated_in_amazon": True,
            "carrier_id": carrier_id,
            "carrier_tracking_ref": track_num
        }
        if ship_line.get('estimated-arrival-date', False):
            estimated_arrival = parser.parse(ship_line.get('estimated-arrival-date')).astimezone(
                utc).strftime('%Y-%m-%d %H:%M:%S')
            vals.update({'estimated_arrival_date': estimated_arrival})
        return vals

    def prepare_outbound_stock_move_update_values(self, ship_id, amazon_order, ship_line, track_num):
        """
            Prepares amazon order values to write in stock moves.

            :param ship_id: int
            :param amazon_order: sale.order object
            :param ship_line: dict
            :param track_num: str
            :return: dict
        """
        return {
            "amazon_shipment_id": ship_id,
            "amazon_instance_id": amazon_order.amz_instance_id.id,
            "amazon_order_reference": ship_line.get('merchant-order-id'),
            "amazon_order_item_id": ship_line.get("amazon-order-item-id"),
            "amazon_shipment_item_id": ship_line.get("shipment-item-id"),
            "tracking_number": track_num,
            "fulfillment_center_id": ship_line.get("fulfillment_center"),
            "amz_shipment_report_id": self.id
        }

    @staticmethod
    def prepare_outbound_stock_move_lines(product, picking, shipped_qty, stock_move):
        """
            Prepares values for outbound stock move lines.

            :param product: product.product object
            :param picking: stock.picking object
            :param shipped_qty: str
            :param stock_move: stock.move object
            :return: dict
        """
        return {
            'product_id': product.id,
            'product_uom_id': product.uom_id.id,
            'picking_id': picking.id,
            'qty_done': float(shipped_qty) or 0,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
            'move_id': stock_move.id
        }

    def prepare_outbound_product_dict(self, amazon_order, ship_line, prod_dict, job):
        """
            @author: Sunil Khatri \n
            @creation_date: 01/05/2021 \n

            :param amazon_order: sale order object
            :param ship_line: dict
            :param prod_dict: dict
            :param job: common log book object
            :return: product dict
        """
        amazon_product_obj = self.env["amazon.product.ept"]
        model_id = self.env['ir.model']._get('shipping.report.request.history').id
        shipped_qty = float(ship_line.get("quantity-shipped", 0.0))
        product_sku = ship_line.get("sku", False)
        amazon_product = amazon_product_obj.search_amazon_product(amazon_order.amz_instance_id.id,
                                                                  product_sku, "FBA")
        if not amazon_product:
            message = "Amazon product {0} not found for instance {1}.".format(
                product_sku, amazon_order.amz_instance_id.name)
            self.env['common.log.lines.ept'].create({
                'message': message,
                'model_id': model_id,
                'res_id': self.id,
                'order_ref': amazon_order.amz_order_reference,
                'fulfillment_by': 'FBA',
                'log_line_id': job.id or False
            })
        else:
            product = amazon_product.product_id
            prod_dict.update({product: shipped_qty if product not in prod_dict else
                            prod_dict.get(product) + shipped_qty})

            self.env['shipping.report.order.history'].create({
                'instance_id': amazon_order.amz_instance_id.id,
                'amazon_order_ref': ship_line.get('amazon-order-id'),
                'order_line_ref': ship_line.get('amazon-order-item-id'),
                'shipment_id': ship_line.get('shipment-id'),
                'shipment_line_id': ship_line.get('shipment-item-id')
            })
        return prod_dict

    def get_amazon_outbound_order(self, order_reference, job):
        """
            @author: Sunil Khatri \n
            @creation_date : 01/05/2021 \n

            :param order_reference: str
            :param job: common connector log object
            :return: Sale order object
        """
        model_id = self.env['ir.model']._get('shipping.report.request.history').id
        amazon_order = self.env["sale.order"].search([("amz_order_reference", "=", order_reference),
                                            ("amz_is_outbound_order", "=", True),
                                            ('amz_seller_id', '=', self.seller_id.id)])
        if not amazon_order:
            fields = ['message', 'model_id', 'res_id', 'order_ref', 'fulfillment_by', 'log_line_id']
            values = ["Order {} not found.".format(order_reference),
                      model_id, self.id, order_reference, 'FBA', job.id or False]
            self.env['common.log.lines.ept'].create({item[0]: item[1] for item in list(zip(fields, values))})
            return amazon_order
        if amazon_order.filtered(lambda o: o.state in ["draft", "sent"]):
            amazon_order.action_confirm()
        return amazon_order

    def request_and_process_b2b_order_response_ept(self, order_details_dict_list, b2b_order_list, job):
        """
        Added by twinkalc on 16 March 2021
        Request and prepare b2b order dict
        """
        order_obj = self.env['sale.order']
        if not b2b_order_list:
            return {}

        kwargs = self.prepare_amazon_request_report_kwargs(self.seller_id)
        kwargs.update({'emipro_api': 'get_order_v13'})
        for x in range(0, len(b2b_order_list), 50):
            sale_orders_list = b2b_order_list[x:x + 50]
            amz_b2b_order_dict = {}
            kwargs.update({'sale_order_list': sale_orders_list})
            response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
            result = []
            if response.get('result'):
                result = [response.get('result')]
                time.sleep(4)

            for wrapper_obj in result:
                orders = []
                if not isinstance(wrapper_obj.get('Orders', {}).get('Order', []), list):
                    orders.append(wrapper_obj.get('Orders', {}).get('Order', {}))
                else:
                    orders = wrapper_obj.get('Orders', {}).get('Order', [])
                for order in orders:
                    amazon_order_ref = order.get('AmazonOrderId', {}).get('value', False)
                    if not amazon_order_ref:
                        continue
                    vat, vat_country_code =  order_obj.get_amazon_tax_registration_details(order)
                    amz_b2b_order_dict.update({amazon_order_ref: {
                        'IsBusinessOrder': order.get('IsBusinessOrder',{}),
                        'IsPrime': order.get('IsPrime', {}),
                        'vat-number': vat,
                        'vat-country': vat_country_code}})
            self.process_fba_shipment_orders(order_details_dict_list, amz_b2b_order_dict, job, sale_orders_list)
        return True

    @api.model
    def process_outbound_orders(self, outbound_order_data, job):
        """
        Processes the outbound shipment data from shipping report as of Multi Channel Sale order.
        @author: Maulik Barad on Date 23-Jan-2019.
        @param outbound_order_rows: Data of outbound orders.
        @param job: Record of common log book.
        """
        order_obj = self.env["sale.order"]
        amazon_product_obj = self.env["amazon.product.ept"]
        for order_ref, lines in outbound_order_data.items():
            available_orders = remain_order = order_obj
            amazon_order = order_obj.search(
                [("amz_order_reference", "=", order_ref), ("amz_is_outbound_order", "=", True)])
            if not amazon_order:
                log_message = {"message": "Order %s not found in ERP." % (order_ref)}
                job.write({"log_lines": [(0, 0, log_message)]})
                continue

            amazon_order = amazon_order.filtered(lambda x: x.state == "draft")
            if not amazon_order:
                log_message = {"message": "Order %s is already updated in ERP." % (order_ref)}
                job.write({"log_lines": [(0, 0, log_message)]})
                continue

            all_lines = amazon_order.order_line.filtered(lambda x: x.product_id.type == "product")
            for line in lines:
                fulfillment_warehouse_id = line.get("warehouse")
                shipped_qty = float(line.get("quantity-shipped"))
                product_sku = line.get("sku", False)
                amazon_product = amazon_product_obj.search_amazon_product(amazon_order.amz_instance_id.id,
                                                                          product_sku, "FBA")
                if not amazon_product:
                    log_message = {"message": "Amazon Product[%s] not found for Instance[%s] in ERP." % (
                        product_sku, amazon_order.amz_instance_id.name)}
                    job.write({"log_lines": [(0, 0, log_message)]})
                    continue
                product = amazon_product.product_id
                existing_order_line = amazon_order.order_line.filtered(lambda x: x.product_id.id == product.id)
                if amazon_order.warehouse_id.id == fulfillment_warehouse_id:
                    if existing_order_line.product_uom_qty != shipped_qty:
                        new_quantity = existing_order_line.product_uom_qty - shipped_qty
                        if remain_order:
                            existing_order_line.copy(default={'order_id': remain_order.id,
                                                              'product_uom_qty': new_quantity})
                        else:
                            remain_order = self.split_order(
                                {(amazon_order, fulfillment_warehouse_id): {existing_order_line: new_quantity}})
                        existing_order_line.product_uom_qty = shipped_qty

                    existing_order_line.amazon_order_item_id = line.get("amazon-order-item-id")
                    available_orders |= amazon_order
                else:
                    splitted_order = order_obj.browse()
                    for order in available_orders:
                        if order.warehouse_id.id == fulfillment_warehouse_id:
                            splitted_order = order
                            break

                    if len(all_lines) == 1 and existing_order_line.product_uom_qty == shipped_qty:
                        amazon_order.warehouse_id = fulfillment_warehouse_id
                        existing_order_line.amazon_order_item_id = line.get("amazon-order-item-id")
                        available_orders |= amazon_order

                    elif len(all_lines) > 1:
                        if splitted_order:
                            new_order_line = existing_order_line.copy(default={'order_id': splitted_order.id,
                                                                               'product_uom_qty': shipped_qty})
                        else:
                            new_order = self.split_order({(amazon_order, fulfillment_warehouse_id):
                                                              {existing_order_line: shipped_qty}})
                            new_order_line = new_order.order_line.filtered(lambda x: x.product_id.id == product.id)
                            available_orders |= new_order

                        new_order_line.amazon_order_item_id = line.get("amazon-order-item-id")
                        existing_order_line.product_uom_qty -= shipped_qty

                        if existing_order_line.product_uom_qty:
                            if remain_order:
                                existing_order_line.copy(default={'order_id': remain_order.id,
                                                                  'product_uom_qty': existing_order_line.product_uom_qty})
                            else:
                                remain_order = self.split_order({(amazon_order, fulfillment_warehouse_id): {
                                    existing_order_line: existing_order_line.product_uom_qty}})
                            existing_order_line.product_uom_qty = 0

                    elif len(all_lines) == 1 and existing_order_line.product_uom_qty != shipped_qty:
                        new_quantity = existing_order_line.product_uom_qty - shipped_qty
                        amazon_order.warehouse_id = fulfillment_warehouse_id

                        if remain_order:
                            existing_order_line.copy(default={'order_id': remain_order.id,
                                                              'product_uom_qty': new_quantity})
                        else:
                            remain_order = self.split_order(
                                {(amazon_order, fulfillment_warehouse_id): {existing_order_line: new_quantity}})
                        existing_order_line.product_uom_qty = shipped_qty
                        existing_order_line.amazon_order_item_id = line.get("amazon-order-item-id")
                        available_orders |= amazon_order

                if existing_order_line.product_uom_qty == 0:
                    existing_order_line.unlink()
            if not amazon_order.order_line:
                available_orders -= amazon_order
                amazon_order.unlink()
            if available_orders:
                available_orders.action_confirm()
                self.attach_amazon_data(available_orders.order_line, lines)
                self.amazon_fba_shipment_report_workflow(available_orders, job)
        return True

    def attach_amazon_data(self, order_lines, order_line_data):
        """
        Match order line with data and attach all amazon order and shipment data with stock picking
        and moves.
        @author: Maulik Barad on Date 27-Jan-2019.
        @param order_lines: All order lines.
        @param order_line_data: Order line and shipment data.
        """
        for data in order_line_data:
            order_line = order_lines.filtered(
                lambda x: x.amazon_order_item_id == data.get("amazon-order-item-id") and x.product_uom_qty == float(
                    data.get("quantity-shipped")) and x.order_id.warehouse_id.id == data.get("warehouse"))
            move = order_line.move_ids.filtered(lambda x: x.state in ["confirmed", "assigned"])
            move.write({
                "amazon_shipment_id": data.get("shipment-id"),
                "amazon_instance_id": order_line.order_id.amz_instance_id.id,
                "amazon_order_reference": data.get('merchant-order-id'),
                "amazon_order_item_id": data.get("amazon-order-item-id"),
                "amazon_shipment_item_id": data.get("shipment-item-id"),
                "tracking_number": data.get("tracking-number"),
                "fulfillment_center_id": data.get("fulfillment_center"),
                "amz_shipment_report_id": self.id
            })
            move._action_assign()
            move._set_quantity_done(float(data.get("quantity-shipped")))

            picking = move.picking_id
            if not picking.amazon_shipment_id:
                picking.write({
                    "amazon_shipment_id": data.get("shipment-id"),
                    "is_fba_wh_picking": True,
                    "fulfill_center": data.get("fulfillment_center"),
                    "updated_in_amazon": True
                })
        return True

    def prepare_move_data_ept(self, amazon_order, line):
        """
        Prepare Stock Move data for FBA Process
        @author: Keyur Kanani
        :param amazon_order: sale.order()
        :param line: csv line dictionary
        :return: {}
        """
        return {
            'amazon_shipment_id': line.get('shipment-id'),
            'amazon_instance_id': amazon_order.amz_instance_id.id,
            'amazon_order_reference': line.get('amazon-order-id'),
            'amazon_order_item_id': line.get('amazon-order-item-id').lstrip('0'),
            'amazon_shipment_item_id': line.get('shipment-item-id'),
            'tracking_number': line.get('tracking-number'),
            'fulfillment_center_id': line.get('fulfillment_center'),
            'amz_shipment_report_id': self.id,
            'product_uom_qty': line.get('quantity-shipped')
        }

    @api.model
    def copy_amazon_order(self, amazon_order, warehouse):
        """
        Duplicate the amazon Orders
        @author: Keyur Kanani
        :param amazon_order: sale.order()
        :param warehouse: int
        :return: sale.order()
        """

        if not amazon_order.amz_instance_id.seller_id.is_default_odoo_sequence_in_sales_order_fba:
            new_name = self.get_order_sequence(amazon_order, 1)
            new_sale_order = amazon_order.copy(default={'name': new_name,
                                                        'order_line': None,
                                                        'warehouse_id': warehouse})
        else:
            new_sale_order = amazon_order.copy(default={'order_line': None,
                                                        'warehouse_id': warehouse})
        new_sale_order.onchange_warehouse_id()
        return new_sale_order

    @api.model
    def split_order(self, split_order_line_dict):
        """
        Split Amazon Order
        @author: Keyur Kanani
        :param split_order_line_dict: {}
        :return:
        """
        order_obj = self.env['sale.order']
        new_orders = order_obj.browse()
        for order, lines in split_order_line_dict.items():
            order_record = order[0]
            warehouse = order[1]
            new_amazon_order = self.copy_amazon_order(order_record, warehouse)
            for line, shipped_qty in lines.items():
                line.copy(default={'order_id': new_amazon_order.id,
                                   'product_uom_qty': shipped_qty})
                #                 line.write({'product_uom_qty': (line.product_uom_qty - shipped_qty)})
                new_orders += new_amazon_order
        return new_orders

    @api.model
    def get_order_sequence(self, amazon_order, order_sequence):
        """
        Get Order sequence according to seller configurations
        @author: Keyur Kanani
        :param amazon_order: sale.order()
        :param order_sequence:
        :return:
        """
        order_obj = self.env['sale.order']
        new_name = "%s%s" % (
            amazon_order.amz_instance_id.seller_id.order_prefix or '',
            amazon_order.amz_order_reference)
        new_name = new_name + '/' + str(order_sequence)
        if order_obj.search([('name', '=', new_name)]):
            order_sequence = order_sequence + 1
            return self.get_order_sequence(amazon_order, order_sequence)
        else:
            return new_name

    def process_fba_shipment_orders(self, order_details_dict_list, amz_b2b_order_dict, job, sale_orders_list):
        """
        Create Sale Orders, order lines and Shipment lines, giftwrap etc..
        Create and Done Stock Move.
        @author: Keyur Kanani
        :param order_details_dict_list: {}
        :return boolean: True
        """
        sale_order_obj = self.env['sale.order']
        sale_order_line_obj = self.env['sale.order.line']
        amz_instance_obj = self.env['amazon.instance.ept']
        stock_location_obj = self.env['stock.location']
        module_obj = self.env['ir.module.module']
        transaction_log_lines = []
        pending_orders_dict = {}
        partner_dict = {}
        product_details = {}
        commit_flag = 1
        country_dict = {}
        state_dict = {}
        vat_module = module_obj.sudo().search([('name', '=', 'base_vat'), ('state', '=', 'installed')])
        customers_location = stock_location_obj.search([('usage', '=', 'customer'),
                                                        '|',('company_id', '=', self.seller_id.company_id.id),
                                                            ('company_id', '=', False)], limit=1)
        for order_ref, lines in order_details_dict_list.items():
            if order_ref not in sale_orders_list:
                continue
            amz_order_list = []

            skip_order, product_details = self.prepare_amazon_products(lines, product_details, job)
            if skip_order:
                log_line_vals = {
                    'order_ref': order_ref,
                    'fulfillment_by': 'FBA',
                    'message': 'Skipped Amazon order %s because of products mismatch' % (order_ref)}
                transaction_log_lines.append((0, 0, log_line_vals))
                continue
            b2b_order_vals = amz_b2b_order_dict.get(order_ref, {})
            for order_line in lines:
                order_line.update(b2b_order_vals)
                instance = amz_instance_obj.browse(order_line.get('instance_id'))
                # # If pending order then unlink that order and create new order
                pending_order = pending_orders_dict.get((order_ref, instance.id))
                if not pending_order:
                    sale_order = sale_order_obj.search([('amz_order_reference', '=', order_ref),
                                                        ('amz_instance_id', '=', instance.id),
                                                        ('amz_fulfillment_by', '=', 'FBA'), ('state', '=', 'draft'),
                                                        ('is_fba_pending_order', '=', True)])
                    if sale_order:
                        pending_orders_dict.update({(order_ref, instance.id): sale_order.ids})
                        sale_order.unlink()
                # Search or create customer
                order_line.update({'check_vat_ept': True if vat_module else False})
                partner_dict, country_dict, state_dict = self.search_or_create_partner(order_line, instance,
                                                                                       partner_dict, country_dict,
                                                                                       state_dict)
                amazon_order = sale_order_obj.create_amazon_shipping_report_sale_order(order_line, partner_dict,
                                                                                       self.id)
                # Create Sale order lines
                so_lines = sale_order_line_obj.create_amazon_sale_order_line(amazon_order, order_line, product_details)
                move_data_dict = self.prepare_move_data_ept(amazon_order, order_line)
                so_line = so_lines.filtered(lambda l: l.product_id.type != 'service')
                self.amazon_fba_stock_move(so_line, customers_location, move_data_dict)
                if amazon_order not in amz_order_list:
                    amz_order_list.append(amazon_order)
            #Process Shipment Report workflow for shipped orders by Amazon
            self.amazon_fba_shipment_report_workflow(amz_order_list, job)
            if commit_flag == 10:
                self.env.cr.commit()
                commit_flag = 0
            commit_flag += 1
        if transaction_log_lines:
            job.write({'log_lines': transaction_log_lines})
        return True

    def amazon_fba_shipment_report_workflow(self, amz_order_list, job):
        """
        The function is used for create Invoices and Process Stock Move done.
        @author: Keyur Kanani
        :param order: sale.order()
        :return:
        """
        stock_move_obj = self.env['stock.move']
        for order in amz_order_list:
            fba_auto_workflow_id = order.amz_seller_id.fba_auto_workflow_id
            stock_moves = stock_move_obj.search(
                [('sale_line_id', 'in', order.order_line.ids),
                 ('amazon_instance_id', '=', order.amz_instance_id.id)])
            for move in stock_moves:
                """
                Two case for done stock move:

                1) if stock move product tracking is lot or serial and
                   stock move line set lot serial number and that set lot serial number
                   stock move line reserved quantity sum is equal to stock move quantity
                   then done that move
                   
                2) if stock move product tracking is none then done that move
                """
                self.validate_stock_move(move, job, order.name)

            order.write({'state': 'sale'})
            if fba_auto_workflow_id.create_invoice:
                # For Update Invoices in Amazon, we have to create Invoices as per Shipment id
                shipment_ids = {}
                for move in order.order_line.move_ids:
                    if move.amazon_shipment_id in shipment_ids:
                        shipment_ids.get(move.amazon_shipment_id).append(move.amazon_shipment_item_id)
                    else:
                        shipment_ids.update({move.amazon_shipment_id: [move.amazon_shipment_item_id]})
                for shipment, shipment_item in list(shipment_ids.items()):
                    to_invoice = order.order_line.filtered(lambda l: l.qty_to_invoice != 0.0)
                    if to_invoice:
                        invoices = order.with_context({'shipment_item_ids': shipment_item})._create_invoices()
                        invoice = invoices.filtered(lambda l: l.line_ids)
                        if invoice:
                            order.validate_invoice_ept(invoice)
                            if fba_auto_workflow_id.register_payment:
                                order.paid_invoice_ept(invoice)
                        else:
                            for inv in invoices:
                                if not inv.line_ids:
                                    inv.unlink()
        return True

    def amazon_fba_stock_move(self, order_line, customers_location, move_vals):
        """
        Create Stock Move according to MRP module and bom products and also for simple product variant.
        @author: Keyur Kanani
        :param amazon_order: sale.order()
        :param customers_location: stock.location()
        :param move_vals:
        :return:
        """

        module_obj = self.env['ir.module.module']
        stock_move_obj = self.env['stock.move']
        mrp_module = module_obj.sudo().search([('name', '=', 'mrp'), ('state', '=', 'installed')])
        if mrp_module:
            bom_lines = self.amz_shipment_get_set_product_ept(order_line.product_id)
            if bom_lines:
                for bom_line in bom_lines:
                    stock_move_vals = self.prepare_stock_move_vals(order_line, customers_location, move_vals)
                    stock_move_vals.update({'product_id': bom_line[0].product_id.id,
                                            'bom_line_id': bom_line[0].id,
                                            'product_uom_qty': bom_line[1].get('qty') * order_line.product_uom_qty})
                    stock_move = stock_move_obj.create(stock_move_vals)
                    stock_move._action_assign()
                    stock_move._set_quantity_done(stock_move.product_uom_qty)
            else:
                stock_move_vals = self.prepare_stock_move_vals(order_line, customers_location, move_vals)
                stock_move = stock_move_obj.create(stock_move_vals)
                stock_move._action_assign()
                stock_move._set_quantity_done(stock_move.product_uom_qty)
        else:
            stock_move_vals = self.prepare_stock_move_vals(order_line, customers_location, move_vals)
            stock_move = stock_move_obj.create(stock_move_vals)
            stock_move._action_assign()
            stock_move._set_quantity_done(stock_move.product_uom_qty)
        return True

    def amz_shipment_get_set_product_ept(self, product):
        """
        Find BOM for phantom type only if Bill of Material type is Make to Order
        then for shipment report there are no logic to create Manufacturer Order.
        Author: Keyur Kanani
        :param product:
        :return:
        """
        try:
            bom_obj = self.env['mrp.bom']
            bom_point = bom_obj.sudo()._bom_find(product=product, company_id=self.company_id.id, bom_type='phantom')
            lines = []
            if bom_point:
                from_uom = product.uom_id
                to_uom = bom_point.product_uom_id
                factor = from_uom._compute_quantity(1, to_uom) / bom_point.product_qty
                bom, lines = bom_point.explode(product, factor, picking_type=bom_point.picking_type_id)
            return lines
        except:
            return {}

    def prepare_stock_move_vals(self, order_line, customers_location, move_vals):
        """
        Prepare stock move data for create stock move while validating sale order
        @author: Keyur kanani
        :param order_line:
        :param customers_location:
        :param move_vals:
        :return:
        """
        return {
            'name': _('Amazon move : %s') % order_line.order_id.name,
            'company_id': self.company_id.id,
            'product_id': order_line.product_id.id,
            'product_uom_qty': move_vals.get('product_uom_qty', False) or order_line.product_uom_qty,
            'product_uom': order_line.product_uom.id,
            'location_id': order_line.order_id.warehouse_id.lot_stock_id.id,
            'location_dest_id': customers_location.id,
            'state': 'confirmed',
            'sale_line_id': order_line.id,
            'seller_id': self.seller_id.id,
            'amazon_shipment_id': move_vals.get('amazon_shipment_id'),
            'amazon_instance_id': move_vals.get('amazon_instance_id'),
            'amazon_order_reference': move_vals.get('amazon_order_reference'),
            'amazon_order_item_id': move_vals.get('amazon_order_item_id'),
            'amazon_shipment_item_id': move_vals.get('amazon_shipment_item_id'),
            'tracking_number': move_vals.get('tracking_number'),
            'fulfillment_center_id': move_vals.get('fulfillment_center_id'),
            'amz_shipment_report_id': move_vals.get('amz_shipment_report_id')
        }

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
    #         'country_code': row.get('bill-country', False),
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

    @staticmethod
    def prepare_ship_partner_vals(row, instance):
        """
        Prepare Shipment Partner values
        @author: Keyur kanani
        :param row: {}
        :param instance: amazon.instance.ept()
        :return: {}
        """
        ship_address2 = row.get('ship-address-2') if row.get('ship-address-2') else ''
        ship_address3 = row.get('ship-address-3') if row.get('ship-address-3') else ''
        street2 = "%s %s" % (ship_address2, ship_address3)
        partner_vals = {
            'street': row.get('ship-address-1', False),
            'street2': street2,
            'city': row.get('ship-city', False),
            'phone': row.get('ship-phone-number', False),
            'email': row.get('buyer-email', False),
            'zip': row.get('ship-postal-code', False),
            'lang': instance.lang_id and instance.lang_id.code,
            'company_id': instance.company_id.id,
            'is_amz_customer': True,
        }
        if instance.amazon_property_account_payable_id:
            partner_vals.update({'property_account_payable_id': instance.amazon_property_account_payable_id.id})
        if instance.amazon_property_account_receivable_id:
            partner_vals.update({'property_account_receivable_id': instance.amazon_property_account_receivable_id.id})
        return partner_vals

    def search_or_create_partner(self, row, instance, partner_dict, country_dict, state_dict):
        """
        Search existing partner from order lines, if not exist then create New partner and
        if shipping partner is different from invoice partner then create new partner for shipment
        @author: Keyur Kanani
        :param row: {}
        :param instance:amazon.instance.ept()
        :param partner_dict: {}
        :return: {}
        """
        ship_address2 = row.get('ship-address-2') if row.get('ship-address-2') else ''
        ship_address3 = row.get('ship-address-3') if row.get('ship-address-3') else ''
        res_partner_obj = self.env['res.partner']
        buyer_name = row.get('buyer-name')
        recipient_name = row.get('recipient-name')
        vat = row.get('vat-number', '')
        vat_country = row.get('vat-country', '') or row.get('CountryCode', '')
        country_obj = country_dict.get(row.get('ship-country'))
        is_update_via_query = False

        if not country_obj:
            country_obj = self.env['res.country'].search(
                ['|', ('code', '=', row.get('ship-country')), ('name', '=', row.get('ship-country'))],
                limit=1)
            country_dict.update({row.get('ship-country'): country_obj})
        if recipient_name == 'CONFIDENTIAL':
            partner = res_partner_obj.with_context(is_amazon_partner=True).search(
                [('email', '=', row.get('buyer-email')), ('name', '=', row.get('buyer-name')),
                 ('country_id', '=', country_obj.id)], limit=1)
            if not partner:
                partner_vals = {}
                if instance.amazon_property_account_payable_id:
                    partner_vals.update(
                        {'property_account_payable_id': instance.amazon_property_account_payable_id.id})
                if instance.amazon_property_account_receivable_id:
                    partner_vals.update(
                        {'property_account_receivable_id': instance.amazon_property_account_receivable_id.id})
                partner = res_partner_obj.with_context(tracking_disable=True).create({
                    'name': buyer_name,
                    'country_id': country_obj.id,
                    'type': 'invoice',
                    'lang': instance.lang_id and instance.lang_id.code,
                    'is_amz_customer': True,
                    **partner_vals
                })
            return {'invoice_partner': partner.id, 'shipping_partner': partner.id}, country_dict, state_dict

        ship_vals = self.prepare_ship_partner_vals(row, instance)
        state = state_dict.get(row.get('ship-state'), False)
        if not state and country_obj and row.get('ship-state') != '--':
            state = res_partner_obj.create_order_update_state(country_obj.code, row.get('ship-state'),
                                                              ship_vals.get('zip'), country_obj)
            state_dict.update({row.get('ship-state'): state})
        ship_vals.update(
            {'state_id': state and state.id or False, 'country_id': country_obj and country_obj.id or False})

        street2 = "%s %s" % (ship_address2, ship_address3)

        if vat:
            if row.get('check_vat_ept', False):
                if vat_country != country_obj.code and not vat[:2].isalpha():
                    vat = vat_country + vat
                check_vat = res_partner_obj.check_amz_vat_validation_ept(vat, country_obj, vat_country, instance)
                if check_vat:
                    ship_vals.update({'vat': vat})
                else:
                    is_update_via_query = True
            else:
                ship_vals.update({'vat': vat})

        if not row.get('buyer-email'):
            partner = res_partner_obj.search(
                [('name', '=', buyer_name),
                 ('city', '=', ship_vals.get('city')),
                 ('state_id', '=', ship_vals.get('state_id')),
                 ('country_id', '=', ship_vals.get('country_id')),
                 '|', ('company_id', '=', False), ('company_id', '=', instance.company_id.id)], limit=1)
        else:
            partner = res_partner_obj.with_context(is_amazon_partner=True).search(
                [('email', '=', row.get('buyer-email')), '|', ('company_id', '=', False),
                 ('company_id', '=', instance.company_id.id)], limit=1)
        if not partner:
            partnervals = {'name': buyer_name, 'type': 'invoice',  **ship_vals}
            partner = res_partner_obj.create(partnervals)
            partner_dict.update({'invoice_partner': partner.id})
            invoice_partner = partner
        elif (buyer_name and partner.name != buyer_name):
            partner.is_company = True
            invoice_partner = res_partner_obj.with_context(tracking_disable=True).create({
                'parent_id': partner.id,
                'name': buyer_name,
                'type': 'invoice',
                **ship_vals
            })
        else:
            invoice_partner = partner

        delivery = invoice_partner if (invoice_partner.name == recipient_name) else None
        if not delivery:
            delivery = res_partner_obj.with_context(is_amazon_partner=True).search(
                [('name', '=', recipient_name), ('street', '=', ship_vals.get('street')),
                 '|', ('street2', '=', False), ('street2', '=', street2), ('zip', '=', ship_vals.get('zip')),
                 ('city', '=', ship_vals.get('city')), ('country_id', '=', country_obj.id if country_obj else False),
                 ('state_id', '=', state.id if state else False),
                 '|', ('company_id', '=', False), ('company_id', '=', instance.company_id.id)], limit=1)
            if not delivery:
                invoice_partner.is_company = True
                delivery = res_partner_obj.with_context(tracking_disable=True).create({
                    'name': recipient_name,
                    'type': 'delivery',
                    'parent_id': invoice_partner.id,
                    'is_amz_customer': True,
                    **ship_vals,
                })
        if is_update_via_query:
            invoice_partner.message_post(body=_("<b>VAT NUmber [%s] is invalid!</b>" % str(vat)))
            if invoice_partner != delivery:
                delivery.message_post(body=_("<b>VAT NUmber [%s] is invalid!</b>" % str(vat)))
        return {'invoice_partner': invoice_partner.id, 'shipping_partner': delivery.id}, country_dict, state_dict

    def get_warehouse(self, fulfillment_center_id, instance):
        """
        Get Amazon fulfillment center and FBA warehouse id from current instance
        @author: Keyur Kanani
        :param fulfillment_center_id:
        :param instance: amazon.instance.ept()
        :return: fulfillment_center, warehouse
        """
        fulfillment_center_obj = self.env['amazon.fulfillment.center']
        fulfillment_center = fulfillment_center_obj.search([('center_code', '=', fulfillment_center_id),
                                                            ('seller_id', '=', instance.seller_id.id)])
        fulfillment_center = fulfillment_center and fulfillment_center[0]
        warehouse = fulfillment_center and fulfillment_center.warehouse_id or instance.fba_warehouse_id or instance.warehouse_id or False
        return fulfillment_center, warehouse

    @staticmethod
    def prepare_amazon_sale_order_line_values(row, order_details_dict_list):
        """
        Prepare Sale Order lines vals for amazon orders
        @author: Keyur Kanani
        :param row:{}
        :return:{}
        """
        if row.get('merchant-order-id', False):
            if order_details_dict_list.get(row.get('merchant-order-id', False)):
                order_details_dict_list.get(row.get('merchant-order-id', False)).append(row)
            else:
                order_details_dict_list.update({row.get('merchant-order-id', False): [row]})
        else:
            if order_details_dict_list.get(row.get('amazon-order-id', False)):
                order_details_dict_list.get(row.get('amazon-order-id', False)).append(row)
            else:
                order_details_dict_list.update({row.get('amazon-order-id', False): [row]})
        return order_details_dict_list

    def prepare_amazon_products(self, lines, product_dict, job):
        """
        Prepare Amazon Product values
        @author: Keyur Kanani
        :param row: {}
        :param instance: amazon.instanace.ept()
        :param product_dict: {}
        :return: {boolean, product{}}
        """
        amazon_product_obj = self.env['amazon.product.ept']
        odoo_product_obj = self.env['product.product']
        amz_instance_obj = self.env['amazon.instance.ept']
        transaction_log_lines = []
        skip_order = False
        for row in lines:
            seller_sku = row.get('sku').strip()
            instance = amz_instance_obj.browse(row.get('instance_id'))
            odoo_product = product_dict.get((seller_sku, instance.id))
            if odoo_product:
                continue

            amazon_product = amazon_product_obj.search_amazon_product(instance.id, seller_sku, 'FBA')
            if not amazon_product:
                odoo_product = amazon_product_obj.search_product(seller_sku)
                """
                    If odoo product founds and amazon product not found then no need to
                    check anything and create new amazon product and create log for that
                    , if odoo product not found then go to check configuration which
                    action has to be taken for that.
    
                    There are following situations managed by code.
                    In any situation log that event and action.
    
                    1). Amazon product and odoo product not found
                        => Check seller configuration if allow to create new product
                        then create product.
                        => Enter log details with action.
                    2). Amazon product not found but odoo product is there.
                        => Created amazon product with log and action.
                """
                if odoo_product:
                    log_line_vals = {'message': 'Odoo Product is already exists. System have ' \
                                                'created new Amazon Product %s for %s instance' % (
                                                    seller_sku, instance.name),
                                     'fulfillment_by': 'FBA'}
                    transaction_log_lines.append((0, 0, log_line_vals))
                elif not instance.seller_id.create_new_product:
                    skip_order = True
                    log_line_vals = {'message': 'Product %s not found for %s instance' % (seller_sku, instance.name),
                                     'fulfillment_by': 'FBA'}
                    transaction_log_lines.append((0, 0, log_line_vals))
                else:
                    # #Create Odoo Product
                    erp_prod_vals = {
                        'name': row.get('product-name'),
                        'default_code': seller_sku,
                        'type': 'product',
                        'purchase_ok': True,
                        'sale_ok': True,
                    }
                    odoo_product = odoo_product_obj.create(erp_prod_vals)
                    log_line_vals = {'message': 'System have created new Odoo Product %s for %s instance' % (
                        seller_sku, instance.name), 'fulfillment_by': 'FBA'}
                    transaction_log_lines.append((0, 0, log_line_vals))
                if not skip_order:
                    sku = seller_sku or (odoo_product and odoo_product[0].default_code) or False
                    # #Prepare Product Values
                    prod_vals = self.prepare_amazon_prod_vals(instance, row, sku, odoo_product)
                    # #Create Amazon Product
                    amazon_product_obj.create(prod_vals)
                if odoo_product:
                    product_dict.update({(seller_sku, instance.id): odoo_product})
            else:
                product_dict.update({(seller_sku, instance.id): amazon_product.product_id})
        # ##Create log transaction_log_lines
        if transaction_log_lines:
            job.write({'log_lines': transaction_log_lines})
        return skip_order, product_dict

    @staticmethod
    def prepare_amazon_prod_vals(instance, order_line, sku, odoo_product):
        """
        Prepare Amazon Product Values
        @author: Keyur Kanani
        :param instance: amazon.instance.ept()
        :param order_line: {}
        :param sku: string
        :param odoo_product: product.product()
        :return: {}
        """
        prod_vals = {}
        prod_vals.update({
            'name': order_line.get('product-name', False),
            'instance_id': instance.id,
            'product_asin': order_line.get('ASIN', False),
            'seller_sku': sku,
            'product_id': odoo_product and odoo_product.id or False,
            'exported_to_amazon': True, 'fulfillment_by': 'FBA'
        })
        return prod_vals

    @api.model
    def auto_import_shipment_report(self, args):
        """
        Import Shipment Reports Automatically as per scheduler run time
        :param args: dict{}
        :return: Boolean
        """
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env['amazon.seller.ept'].browse(int(seller_id))
            if seller.shipping_report_last_sync_on:
                start_date = seller.shipping_report_last_sync_on - timedelta(hours=10)
            else:
                start_date = datetime.now() - timedelta(days=30)
            start_date = start_date + timedelta(days=seller.shipping_report_days * -1 or -3)
            end_date = datetime.now()

            report_type = '_GET_AMAZON_FULFILLED_SHIPMENTS_DATA_'
            if not seller.is_another_soft_create_fba_shipment:
                if not self.search([('start_date', '=', start_date),
                                    ('end_date', '=', end_date),
                                    ('seller_id', '=', seller_id), ('report_type', '=', report_type)]):
                    shipment_report = self.create({'report_type': report_type,
                                                   'seller_id': seller_id,
                                                   'state': 'draft',
                                                   'start_date': start_date,
                                                   'end_date': end_date,
                                                   'requested_date': time.strftime("%Y-%m-%d %H:%M:%S")
                                                   })
                    shipment_report.with_context(is_auto_process=True).request_report()
            else:
                date_start = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                date_end = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                list_of_wrapper = self.get_reports_from_other_softwares(seller, report_type, date_start, date_end)
                for reports in list_of_wrapper:
                    for report in reports.get('ReportRequestInfo', {}):
                        report_id = report.get('GeneratedReportId', {}).get('value')
                        request_id = report.get('ReportRequestId', {}).get('value')
                        if not self.search([('report_id', '=', report_id),
                                            ('report_request_id', '=', request_id),
                                            ('report_type', '=', report_type)]):
                            start = parser.parse(str(report.get('StartDate', {}).get('value', ''))).astimezone(
                                utc).strftime('%Y-%m-%d %H:%M:%S')
                            end = parser.parse(str(report.get('EndDate', {}).get('value', ''))).astimezone(
                                utc).strftime('%Y-%m-%d %H:%M:%S')
                            self.create({
                                'seller_id': seller_id,
                                'state': report.get('ReportProcessingStatus', {}).get('value'),
                                'start_date': datetime.strptime(start, '%Y-%m-%d %H:%M:%S'),
                                'end_date': datetime.strptime(end, '%Y-%m-%d %H:%M:%S'),
                                'report_type': report.get('ReportType', {}).get('value'),
                                'report_id': report.get('GeneratedReportId', {}).get('value'),
                                'report_request_id': report.get('ReportRequestId', {}).get('value'),
                                'requested_date': time.strftime("%Y-%m-%d %H:%M:%S")
                            })
            seller.write({'shipping_report_last_sync_on': end_date.strftime("%Y-%m-%d %H:%M:%S")})

        return True

    def auto_process_shipment_report(self, args={}):
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env['amazon.seller.ept'].browse(seller_id)
            ship_reports = self.search([('seller_id', '=', seller.id),
                                        ('state', 'in', ['_SUBMITTED_', '_IN_PROGRESS_', '_DONE_'])])
            for report in ship_reports:
                if report.state != '_DONE_':
                    report.get_report_request_list()
                if report.report_id and report.state == '_DONE_' and not report.attachment_id:
                    report.with_context(is_auto_process=True).get_report()
                if report.attachment_id:
                    report.with_context(is_auto_process=True).process_shipment_file()
                self._cr.commit()
        return True

    def get_reports_from_other_softwares(self, seller, report_type, start_date, end_date):
        kwargs = self.prepare_amazon_request_report_kwargs(seller)
        kwargs.update({'emipro_api': 'get_shipping_or_inventory_report_v13',
                       'report_type': report_type,
                       'start_date': start_date,
                       'end_date': end_date})
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if not response.get('reason'):
            list_of_wrapper = response.get('result')
        else:
            raise Warning(response.get('reason'))
        return list_of_wrapper

    def get_missing_fulfillment_center(self, attachment_id):
        """
        All Fulfillment Center from attachment file and find in ERP
        If Fulfillment Center doesn't exist in ERP then it will return in list
        @:param - attachment_id - shipping report attachment
        @:return - unavailable_fulfillment_center - return missing fulfillment center from ERP
        @author: Deval Jagad (09/01/2020)
        """
        fulfillment_center_obj = self.env['amazon.fulfillment.center']
        unavailable_fulfillment_center = []
        log = self.amz_search_or_create_logs_ept(response={})
        imp_file = self.decode_amazon_encrypted_attachments_data(attachment_id, log)
        reader = csv.DictReader(imp_file, delimiter='\t')
        fulfillment_centers = [row.get('fulfillment-center-id') for row in reader]
        fulfillment_center_list = fulfillment_centers and list(set(fulfillment_centers))
        seller_id = self.seller_id.id

        for fulfillment_center in fulfillment_center_list:
            amz_fulfillment_center_id = fulfillment_center_obj.search(
                [('center_code', '=', fulfillment_center),
                 ('seller_id', '=', seller_id)])
            if not amz_fulfillment_center_id:
                unavailable_fulfillment_center.append(fulfillment_center)
        return unavailable_fulfillment_center

    def configure_missing_fulfillment_center(self):
        """
        Open wizard with load missing fulfillment center from ERP
        @author: Deval Jagad (07/01/2020)
        """
        view = self.env.ref('amazon_ept.view_configure_shipment_report_fulfillment_center_ept')
        context = dict(self._context)
        country_ids = self.seller_id.amz_warehouse_ids.mapped('partner_id').mapped('country_id')
        context.update({'shipment_report_id': self.id, 'country_ids': country_ids.ids})

        return {
            'name': _('Amazon Shipment Report - Configure Missing Fulfillment Center'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'shipment.report.configure.fulfillment.center.ept',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    def decode_amazon_encrypted_attachments_data(self, attachment_id, job):
        if self.is_encrypted_attachment:
            dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
            req = {
                'dbuuid': dbuuid,
                'report_id': self.report_id,
                'datas': attachment_id.datas.decode(),
                'amz_report_type': 'shipment_report'}
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
