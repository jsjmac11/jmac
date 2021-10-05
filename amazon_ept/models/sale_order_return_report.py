from datetime import datetime, timedelta
import time
import base64
import csv
from dateutil import parser
from io import StringIO
from odoo import models, fields, api, _
from odoo.exceptions import Warning
from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT


class SaleOrderReturnReport(models.Model):
    _name = "sale.order.return.report"
    _inherit = ['mail.thread']
    _description = "Customer Return Report"
    _order = 'id desc'

    @api.depends('seller_id')
    def get_company(self):
        """
        Compute method for get company id based on seller id
        @author: Keyur Kanani
        :return:
        """
        for record in self:
            company_id = record.seller_id.company_id.id if record.seller_id else False
            if not company_id:
                company_id = self.env.company.id
            record.company_id = company_id

    def get_total_returns(self):
        """
        Get total number of records which is processed in the current report
        @author: Keyur Kanani
        :return:
        """
        stock_move_obj = self.env['stock.move']
        records = stock_move_obj.search([('amz_return_report_id', '=', self.id)])
        self.return_count = len(records)

    def get_log_count(self):
        common_log_book_obj = self.env['common.log.book.ept']
        model_id = self.env['ir.model']._get('sale.order.return.report').id
        self.log_count = common_log_book_obj.search_count(
            [('model_id', '=', model_id), ('res_id', '=', self.id)])

    name = fields.Char(size=256, string='Name')
    attachment_id = fields.Many2one('ir.attachment', string="Attachment",
                                    help="Attachment Id for Customer Return csv file")
    return_count = fields.Integer(compute="get_total_returns", string="Returns")
    report_request_id = fields.Char(size=256, string='Report Request ID',
                                    help="Report request id to recognise unique request")
    report_id = fields.Char(size=256, string='Report ID',
                            help="Unique Report id for recognise report in Odoo")
    report_type = fields.Char(size=256, string='Report Type', help="Amazon Report Type")
    start_date = fields.Datetime('Start Date', help="Report Start Date")
    end_date = fields.Datetime('End Date', help="Report End Date")
    requested_date = fields.Datetime('Requested Date', default=time.strftime("%Y-%m-%d %H:%M:%S"),
                                     help="Report Requested Date")
    state = fields.Selection(
        [('draft', 'Draft'), ('_SUBMITTED_', 'SUBMITTED'), ('_IN_PROGRESS_', 'IN_PROGRESS'),
         ('_CANCELLED_', 'CANCELLED'), ('_DONE_', 'DONE'),
         ('_DONE_NO_DATA_', 'DONE_NO_DATA'), ('processed', 'PROCESSED'), ('imported', 'Imported'),
         ('partially_processed', 'Partially Processed'), ('closed', 'Closed')
         ],
        string='Report Status', default='draft', help="Report Processing States")
    seller_id = fields.Many2one('amazon.seller.ept', string='Seller', copy=False,
                                help="Select Seller id from you wanted to get Shipping report")
    user_id = fields.Many2one('res.users', string="Requested User", help="Track which odoo user has requested report")
    company_id = fields.Many2one('res.company', string="Company", copy=False, compute="get_company",
                                 store=True)
    log_count = fields.Integer(compute="get_log_count", string="Log Count",
                               help="Count number of created Stock Move")

    def unlink(self):
        """
        This Method if report is processed then raise warning.
        """
        for report in self:
            if report.state == 'processed' or report.state == 'partially_processed':
                raise Warning(_('You cannot delete processed report.'))
        return super(SaleOrderReturnReport, self).unlink()

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

    def list_of_return_orders(self):
        """
        List all Stock Move which is returned in the current report
        @author: Keyur Kanani
        :return:
        """
        stock_move_obj = self.env['stock.move']
        records = stock_move_obj.search([('amz_return_report_id', '=', self.id)])
        action = {
            'domain': "[('id', 'in', " + str(records.ids) + " )]",
            'name': 'Amazon FBA Order Return Stock Move',
            'view_mode': 'tree,form',
            'res_model': 'stock.move',
            'type': 'ir.actions.act_window',
        }
        return action

    def list_of_process_logs(self):
        """
        List of Customer Return Report Log view
        @author: Keyur Kanani
        :return:
        """
        model_id = self.env['ir.model']._get('sale.order.return.report').id
        action = {
            'domain': "[('res_id', '=', " + str(self.id) + "), ('model_id','='," + str(model_id) + ")]",
            'name': 'Customer Return Report Logs',
            'view_mode': 'tree,form',
            'res_model': 'common.log.book.ept',
            'type': 'ir.actions.act_window',
        }
        return action

    def download_customer_return_report(self):
        """
        Download Customer Return Report csv file from Attachments
        @author: Keyur Kanani
        :return:
        """
        self.ensure_one()
        if self.attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' % (self.attachment_id.id),
                'target': 'self',
            }
        return True

    @api.model
    def default_get(self, fields):
        """
        Set _GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA_ to report type.
        @author: Keyur Kanani
        :param fields:
        :return:
        """
        res = super(SaleOrderReturnReport, self).default_get(fields)
        if not fields:
            return res
        res.update({'report_type': '_GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA_'})
        return res

    @api.model
    def create(self, vals):
        """
        Create Sequence of Return Customer Reports
        @author: Keyur Kanani
        :param vals:
        :return:
        """
        try:
            sequence = self.env.ref('amazon_ept.seq_import_customer_return_report_job')
            if sequence:
                report_name = sequence.next_by_id()
            else:
                report_name = '/'
        except:
            report_name = '/'
        vals.update({'name': report_name})
        return super(SaleOrderReturnReport, self).create(vals)

    @api.onchange('seller_id')
    def on_change_seller_id(self):
        """
        Automatically Set Start date and End date on selection of Seller
        @author: Keyur Kanani
        :return:
        """
        if self.seller_id:
            self.start_date = self.seller_id.return_report_last_sync_on or (
                    datetime.now() - timedelta(self.seller_id.shipping_report_days))
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

    def request_customer_return_report(self):
        """
        Request _GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA_ Report from Amazon for specific date range.
        @author: Keyur Kanani
        :return: Boolean
        """

        seller, report_type = self.seller_id, self.report_type
        common_log_book_obj = self.env['common.log.book.ept']
        model_id = self.env['ir.model']._get('sale.order.return.report').id

        if not seller:
            raise Warning(_('Please select Seller'))

        start_date, end_date = self.report_start_and_end_date()
        kwargs = self.prepare_amazon_request_report_kwargs(seller)
        kwargs.update({
            'emipro_api': 'request_report_v13',
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
                    'model_id': model_id,
                    'res_id': self.id,
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
        model_id = self.env['ir.model']._get('sale.order.return.report').id

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
                    'model_id': model_id,
                    'res_id': self.id,
                    'log_lines': [(0, 0,
                                   {'message': 'Customer Return Report Process ' + response.get('reason')}
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
        @author: Keyur Kanani
        :return: Boolean
        """
        self.ensure_one()
        if not self.seller_id:
            raise Warning(_('Please select Seller'))
        if not self.report_request_id:
            return True
        kwargs = self.prepare_amazon_request_report_kwargs(self.seller_id)
        kwargs.update({'emipro_api': 'get_report_request_list_v13', 'request_ids': (self.report_request_id,)})

        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if not response.get('reason'):
            list_of_wrapper = response.get('result')
        else:
            raise Warning(response.get('reason'))
        for result in list_of_wrapper:
            self.update_report_history(result)
        return True

    def get_customer_return_report(self):
        """
        Get Shipment Report as an attachment in Shipping reports form view.
        @author: Keyur Kanani
        :return:
        """
        self.ensure_one()
        model_id = self.env['ir.model']._get('sale.order.return.report').id
        common_log_book_obj = self.env['common.log.book.ept']
        result = {}
        seller = self.seller_id
        if not seller:
            raise Warning(_('Please select seller'))
        if not self.report_id:
            return True
        kwargs = self.prepare_amazon_request_report_kwargs(self.seller_id)
        kwargs.update({'emipro_api': 'get_report_v13', 'report_id': self.report_id, })
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            if self._context.get('is_auto_process'):
                common_log_book_obj.create({
                    'type': 'import',
                    'module': 'amazon_ept',
                    'active': True,
                    'model_id': model_id,
                    'res_id': self.id,
                    'log_lines': [(0, 0, {'message': 'Customer Return Report Process ' + response.get('reason')})]
                })
            else:
                raise Warning(response.get('reason'))
        else:
            result = response.get('result')
        if result:
            result = base64.b64encode(result.encode())
            file_name = "Customer_return_report_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'
            attachment = self.env['ir.attachment'].create({
                'name': file_name,
                'datas': result,
                'res_model': 'mail.compose.message',
                'type': 'binary'
            })
            self.message_post(body=_("<b>Customer Return Report Downloaded</b>"), attachment_ids=attachment.ids)
            self.write({'attachment_id': attachment.id})
        return True

    def process_return_report_file(self):
        """
        Handle Customer return report file, find from data and create dictionary of final processing move records
        Test Cases:https://docs.google.com/spreadsheets/d/12XqQEheGpQ6c-JV3Ma3eY2MkCMGRaYgf0iht36PsZFc/edit?usp=sharing
        @author: Keyur Kanani
        :return:
        """
        self.ensure_one()
        ir_cron_obj = self.env['ir.cron']
        if not self._context.get('is_auto_process', False):
            ir_cron_obj.with_context({'raise_warning': True}).find_running_schedulers(
                'ir_cron_auto_process_customer_return_report_seller_', self.seller_id.id)
        if not self.attachment_id:
            raise Warning(_("There is no any report are attached with this record."))
        model_id = self.env['ir.model']._get('sale.order.return.report').id
        sale_order_line_obj = self.env['sale.order.line']
        sale_order_obj = self.env['sale.order']
        amazon_product_obj = self.env['amazon.product.ept']
        move_obj = self.env['stock.move']
        amazon_process_job_log_obj = self.env['common.log.book.ept']
        fulfillment_warehouse = {}
        remaning_move_qty = {}
        return_move_dict = {}

        imp_file = StringIO(base64.b64decode(self.attachment_id.datas).decode())
        reader = csv.DictReader(imp_file, delimiter='\t')
        job = amazon_process_job_log_obj.search(
            [('model_id', '=', model_id),
             ('res_id', '=', self.id)])
        if not job:
            job = amazon_process_job_log_obj.create({
                'module': 'amazon_ept',
                'type': 'import',
                'model_id': model_id,
                'res_id': self.id,
                'active': True,
                'log_lines': [(0, 0, {'message': 'Started Customer Return order Report Process.'})]
            })
        for line in reader:
            status = line.get('status')
            return_date = datetime.strftime(parser.parse(line.get('return-date')), '%Y-%m-%d %H:%M:%S')
            amazon_order_id = line.get('order-id', '')
            sku = line.get('sku')
            returned_qty = float(line.get('quantity', 0.0))
            disposition = line.get('detailed-disposition')
            reason = line.get('reason')
            fulfillment_center_id = line.get('fulfillment-center-id', '')

            amazon_orders = sale_order_obj.search([('amz_order_reference', '=', amazon_order_id)])
            if not amazon_orders:
                message = 'Order %s Is Skipped due to not found in ERP' % (amazon_order_id)
                job.write({'log_lines': [(0, 0, {'message': message})]})
                continue

            instance_ids = [amazon_order.amz_instance_id.id for amazon_order in amazon_orders]
            amazon_products = amazon_product_obj.search(
                [('seller_sku', '=', sku), ('instance_id', 'in', instance_ids)], limit=1)
            if not amazon_products:
                message = 'Order %s Is Skipped due to Product %s not found in ERP' % (amazon_order_id, sku)
                job.write({'log_lines': [(0, 0, {'message': message})]})
                continue

            amazon_order_lines = sale_order_line_obj.search(
                [('order_id', 'in', amazon_orders.ids),
                 ('product_id', '=', amazon_products.product_id.id)],
                order="id")
            if not amazon_order_lines:
                message = 'Order line %s Is Skipped due to not found in ERP' % (sku)
                job.write({'log_lines': [(0, 0, {'message': message})]})
                continue

            if fulfillment_center_id not in fulfillment_warehouse:
                warehouse = self.get_warehouse(fulfillment_center_id, self.seller_id.id, amazon_orders[0])
                fulfillment_warehouse.update({fulfillment_center_id: warehouse})
            warehouse = fulfillment_warehouse.get(fulfillment_center_id)
            if not warehouse:
                message = 'Order %s Is Skipped due warehouse not found in ERP || Fulfillment center %s ' % (
                    amazon_order_id, fulfillment_center_id)
                job.write({'log_lines': [(0, 0, {'message': message})]})
                continue

            move_lines = move_obj.search([('sale_line_id', 'in', amazon_order_lines.ids),
                                          ('product_id', '=', amazon_order_lines[0].product_id.id),
                                          ('state', '=', 'done')])
            if not move_lines:
                message = 'Move Line is not found for Order %s' % (amazon_order_id)
                job.write({'log_lines': [(0, 0, {'message': message})]})
                move_lines = move_obj.search([('sale_line_id', 'in', amazon_order_lines.ids),
                                              ('sale_line_id.product_id', '=', amazon_order_lines[0].product_id.id),
                                              ('state', '=', 'done')])
            already_processed = False
            for move_line in move_lines:
                if move_line.fba_returned_date and datetime.strftime(parser.parse(return_date), '%Y-%m-%d') == \
                        datetime.strftime(parser.parse(str(move_line.fba_returned_date)), '%Y-%m-%d'):
                    message = 'Skipped because return already processed for Order %s' % (
                        move_line.amazon_order_reference)
                    job.write({'log_lines': [(0, 0, {'message': message})]})
                    already_processed = True
                    break
            if already_processed:
                continue

            exclude_move_ids = []
            for move_id, qty in remaning_move_qty.items():
                if qty <= 0.0:
                    exclude_move_ids.append(move_id)

            move_lines = move_obj.search([('sale_line_id', 'in', amazon_order_lines.ids),
                                          ('product_id', '=', amazon_order_lines[0].product_id.id),
                                          ('state', '=', 'done'), ('id', 'not in', exclude_move_ids)],
                                         order='product_qty desc')
            if not move_lines:
                move_lines = move_obj.search(
                    [('sale_line_id', 'in', amazon_order_lines.ids),
                     ('sale_line_id.product_id', '=', amazon_order_lines[0].product_id.id),
                     ('state', '=', 'done'),
                     ('id', 'not in', exclude_move_ids)], order='product_qty desc')
                if move_lines:
                    return_move_dict, remaning_move_qty = self.process_kit_type_product(
                        amazon_order_lines[0].product_id, move_lines, returned_qty,
                        warehouse, return_date, sku, disposition, reason,
                        return_move_dict, status, fulfillment_center_id,
                        remaning_move_qty)
                    continue
            if not move_lines:
                message = 'Order %s Is Skipped due to delivery move not found either ' \
                          'move have already returned or move missing in the ERP ' % (
                              amazon_order_id)
                job.write({'log_lines': [(0, 0, {'message': message})]})
                continue
            for move in move_lines:
                qty = move.product_qty - sum(move.move_dest_ids.filtered(
                    lambda m: m.state in ['partially_available', 'assigned', 'done']). \
                                             mapped('move_line_ids').mapped('product_qty'))
                if round(qty, 2) <= 0:
                    message = 'Order %s Is Skipped due to not found quant qty from quant history ' % (
                        amazon_order_id),
                    job.write({'log_lines': [(0, 0, {'message': message})]})
                    continue
                if move.id in remaning_move_qty:
                    get_remain_qty = remaning_move_qty.get(move.id)
                else:
                    get_remain_qty = move.product_qty
                remaning_move_qty.update({move.id: get_remain_qty - returned_qty})
                key = (
                    move, warehouse, return_date, sku, disposition, reason, status, fulfillment_center_id)
                if move not in return_move_dict:
                    return_move_dict.update({move: {key: returned_qty}})
                else:
                    qty = return_move_dict.get(move, {}).get(key, 0.0)
                    return_move_dict[move][key] = qty + returned_qty
        if return_move_dict:
            self._create_fba_returns(return_move_dict, job)
        self.write({'state': 'processed'})
        return True

    @api.model
    def _create_fba_returns(self, return_move_dict, job):
        """
        Process Stock Moves from return_move_dict and create returns in the same warehouse
         where shipped or in the reimbursment or in unsellable locations
        @author: Keyur Kanani
        :param return_move_dict: {}
        :param job: common log book
        :return: True
        """
        return_reason_obj = self.env['amazon.return.reason.ept']
        fulfillment_center_obj = self.env['amazon.fulfillment.center']
        reason_record_dict = {}
        fulfillment_center_dict = {}
        for moves, key_qty in return_move_dict.items():
            for key, qty in key_qty.items():
                move, warehouse, return_date, sku, disposition, reason, status, fulfillment_center_id = key
                location_dest_id = False

                if not location_dest_id and disposition == 'SELLABLE':
                    location_dest_id = warehouse.lot_stock_id.id
                else:
                    location_dest_id = warehouse.unsellable_location_id.id

                if reason not in reason_record_dict:
                    reason_record = return_reason_obj.search([('name', '=', reason)], limit=1)
                    if not reason_record:
                        reason_record = return_reason_obj.create({'name': reason})
                    reason_record_dict.update({reason: reason_record.id})

                if fulfillment_center_id not in fulfillment_center_dict:
                    fulfillment_center = fulfillment_center_obj.search(
                        [('center_code', '=', fulfillment_center_id),
                         ('seller_id', '=', self.seller_id.id)])
                    fulfillment_center_dict.update({fulfillment_center_id: fulfillment_center.id})

                move.return_created = True
                new_move = move.copy(default={
                    'product_id': move.product_id.id,
                    'product_uom_qty': qty,
                    'state': 'confirmed',
                    'location_id': move.location_dest_id.id,
                    'location_dest_id': location_dest_id,
                    'warehouse_id': warehouse and warehouse.id,
                    'origin_returned_move_id': move.id,
                    'procure_method': 'make_to_stock',
                    'date': return_date,
                    'to_refund': True,
                    'return_reason_id': reason_record_dict.get(reason, False),
                    'fba_returned_date': return_date,
                    'detailed_disposition': disposition,
                    'status_ept': status,
                    'amz_return_report_id': self.id,
                    'fulfillment_center_id': fulfillment_center_dict.get(fulfillment_center_id, False)
                })

                new_move._action_assign()
                new_move._set_quantity_done(qty)
                # write origin_move_lot_id at new move moveline lot number at return time.
                origin_move_quant_ids = move.move_line_ids.lot_id.quant_ids.filtered(
                    lambda ql: ql.location_id.usage == 'customer' and ql.quantity > 0 and ql.lot_id)
                if origin_move_quant_ids and not new_move.move_line_ids.lot_id:
                    new_move.move_line_ids.write({'lot_id': origin_move_quant_ids[0].lot_id.id})
                new_move._action_done()
        job.write({'log_lines': [(0, 0, {'message': 'Customer Return Process Completed.'})]})
        return True

    @api.model
    def get_warehouse(self, fulfillment_center_id, seller, amazon_order):
        """
        Find Warehouse from fulfillment center and seller id OR order id
        @author: Keyur Kanani
        :param fulfillment_center_id: center_code
        :param seller: seller_id
        :param amazon_order:  sale.order(0
        :return: stock.warehouse()
        """
        fulfillment_center = self.env['amazon.fulfillment.center'].search(
            [('center_code', '=', fulfillment_center_id), ('seller_id', '=', seller)], limit=1)
        warehouse = fulfillment_center and fulfillment_center.warehouse_id or \
                    amazon_order.amz_instance_id and amazon_order.amz_instance_id.fba_warehouse_id \
                    or amazon_order.amz_instance_id.warehouse_id or False
        return warehouse

    def process_kit_type_product(self, sale_line_product, move_lines, returned_qty,
                                 warehouse, return_date, sku, disposition, reason,
                                 return_move_dict, status, fulfillment_center_id,
                                 remaning_move_qty):
        """
        Process BOM product's sale order line, get exploded products for KIT Type Products in order line
        @author: Keyur Kanani
        :param sale_line_product: product.product()
        :param move_lines: stock.move()
        :param returned_qty:
        :param warehouse:
        :param return_date:
        :param sku:
        :param disposition:
        :param reason:
        :param return_move_dict:
        :param status:
        :param fulfillment_center_id:
        :param remaning_move_qty:
        :return:
        """
        picking_object = self.env['stock.picking']
        skip_moves = []
        for move in move_lines:
            if move.product_id.id in skip_moves:
                continue
            if remaning_move_qty.get(move.id) == 0.0:
                continue
            one_set_product_dict = picking_object.get_set_product(sale_line_product)
            if not one_set_product_dict:
                continue
            if returned_qty <= 0:
                continue
            bom_qty = 0.0
            for bom_line, line in one_set_product_dict:
                if bom_line.product_id.id == move.product_id.id:
                    bom_qty = line['qty']
                    break
            if bom_qty == 0.0:
                continue
            key = (move, warehouse, return_date, sku, disposition, reason, status, fulfillment_center_id)
            final_return_qty = returned_qty * bom_qty
            if move.id in remaning_move_qty:
                get_remain_qty = remaning_move_qty.get(move.id)
                if get_remain_qty < final_return_qty:
                    final_return_qty = get_remain_qty
            else:
                get_remain_qty = move.product_uom_qty
            remaning_move_qty.update({move.id: get_remain_qty - final_return_qty})
            if get_remain_qty - final_return_qty == 0.0 or final_return_qty == returned_qty * bom_qty:
                skip_moves.append(move.product_id.id)
            if move not in return_move_dict:
                return_move_dict.update({move: {key: final_return_qty}})
            else:
                qty = return_move_dict.get(move, {}).get(key, 0.0)
                return_move_dict[move][key] = qty + final_return_qty
        return return_move_dict, remaning_move_qty

    @api.model
    def auto_import_return_report(self, args={}):
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env['amazon.seller.ept'].browse(seller_id)
            if seller.return_report_last_sync_on:
                start_date = seller.return_report_last_sync_on
                start_date = start_date + timedelta(days=seller.customer_return_report_days * -1 or -3)
            else:
                today = datetime.now()
                earlier = today - timedelta(days=30)
                start_date = earlier.strftime("%Y-%m-%d %H:%M:%S")
            date_end = datetime.now()
            date_end = date_end.strftime("%Y-%m-%d %H:%M:%S")

            return_report = self.create(
                {'report_type': '_GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA_',
                 'seller_id': seller_id,
                 'start_date': start_date,
                 'end_date': date_end,
                 'state': 'draft',
                 'requested_date': datetime.now()
                 })
            return_report.request_customer_return_report()
            seller.write({'return_report_last_sync_on': date_end})
        return True

    @api.model
    def auto_process_return_order_report(self, args={}):
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env['amazon.seller.ept'].browse(seller_id)
            return_reports = self.search([('seller_id', '=', seller.id),
                                          ('state', 'in', ['_SUBMITTED_', '_IN_PROGRESS_', '_DONE_'])])
            for report in return_reports:
                if report.state != '_DONE_':
                    report.get_report_request_list()
                if report.report_id and report.state == '_DONE_' and not report.attachment_id:
                    report.with_context(is_auto_process=True).get_customer_return_report()
                if report.attachment_id:
                    report.with_context(is_auto_process=True).process_return_report_file()
                self.env.cr.commit()
        return True
