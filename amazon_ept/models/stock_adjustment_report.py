from odoo import models, fields, api, _
from datetime import timedelta, timezone
import base64
import csv
from io import StringIO
import copy
from odoo.exceptions import Warning
import time
from datetime import datetime
from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT


class UnicodeDictWriter(csv.DictWriter):
    def __init__(self, csvfile, fieldnames, *args, **kwargs):
        """Allows to specify an additional keyword argument encoding which
        defaults to "utf-8"
        """
        self.encoding = kwargs.pop('encoding', 'utf-8')
        csv.DictWriter.__init__(self, csvfile, fieldnames, *args, **kwargs)

    def _dict_to_list(self, rowdict):
        rv = csv.DictWriter._dict_to_list(self, rowdict)
        return [(f.encode(self.encoding, 'ignore') if isinstance(f, str) else f) \
                for f in rv]


class StockAdjustmentReportHistory(models.Model):
    _name = "amazon.stock.adjustment.report.history"
    _description = "Stock Adjustment Report"
    _inherit = ['mail.thread']
    _order = 'id desc'

    @api.depends('seller_id')
    def get_company(self):
        for record in self:
            company_id = record.seller_id and record.seller_id.company_id.id or False
            if not company_id:
                company_id = self.env.company.id
            record.company_id = company_id

    def get_pickings(self):
        self.transfer_count = len(self.transfer_picking_ids.ids)

    def get_moves_count(self):
        stock_move_obj = self.env['stock.move']
        self.moves_count = stock_move_obj.search_count([('amz_stock_adjustment_report_id', '=', self.id)])

    def get_log_count(self):
        """
        Find all stock moves associated with this report
        :return:
        """
        log_obj = self.env['common.log.book.ept']
        model_id = self.env['ir.model']._get('amazon.stock.adjustment.report.history').id
        self.log_count = log_obj.search_count([('res_id', '=', self.id),('model_id','=',model_id)])

    name = fields.Char(size=256, string='Name')
    state = fields.Selection([('draft', 'Draft'), ('_SUBMITTED_', 'SUBMITTED'), ('_IN_PROGRESS_', 'IN_PROGRESS'),
                              ('_CANCELLED_', 'CANCELLED'), ('_DONE_', 'Report Received'),
                              ('_DONE_NO_DATA_', 'DONE_NO_DATA'), ('processed', 'PROCESSED'),
                              ('partially_processed', 'Partially Processed')
                              ],
                             string='Report Status', default='draft')
    seller_id = fields.Many2one('amazon.seller.ept', string='Seller', copy=False,
                                help="Select Seller id from you wanted to get Shipping report")
    attachment_id = fields.Many2one('ir.attachment', string="Attachment")
    instance_id = fields.Many2one("amazon.instance.ept", string="Instance")
    transfer_picking_ids = fields.One2many("stock.picking", 'stock_adjustment_report_id', string="Pickings")
    transfer_count = fields.Integer("Transfer Count", compute="get_pickings")
    report_id = fields.Char('Report ID', readonly='1')
    report_type = fields.Char(size=256, string='Report Type', help="Amazon Report Type")
    report_request_id = fields.Char('Report Request ID', readonly='1')
    start_date = fields.Datetime('Start Date', help="Report Start Date")
    end_date = fields.Datetime('End Date', help="Report End Date")
    requested_date = fields.Datetime('Requested Date', default=time.strftime("%Y-%m-%d %H:%M:%S"),
                                     help="Report Requested Date")
    user_id = fields.Many2one('res.users', string="Requested User", help="Track which odoo user has requested report")
    company_id = fields.Many2one('res.company', string="Company", copy=False, compute="get_company", store=True)
    amz_stock_adjustment_report_ids = fields.One2many('stock.move', 'amz_stock_adjustment_report_id',
                                                      string="Stock adjustment move ids")
    moves_count = fields.Integer(compute="get_moves_count", string="Move Count", store=False)
    log_count = fields.Integer(compute="get_log_count", string="Log Count", store=False)

    @api.onchange('seller_id')
    def on_change_seller_id(self):
        """
        This Method relocates check seller and write start date and end date.
        :return: This Method return updated value.
        """
        if self.seller_id:
            self.start_date = datetime.now() - timedelta(self.seller_id.inv_adjustment_report_days)
            self.end_date = datetime.now()

    def unlink(self):
        """
        This Method if report is processed then raise warning.
        """
        for report in self:
            if report.state == 'processed' or report.state == 'partially_processed':
                raise Warning(_('You cannot delete processed report.'))
        return super(StockAdjustmentReportHistory, self).unlink()

    @api.model
    def default_get(self, fields):
        res = super(StockAdjustmentReportHistory, self).default_get(fields)
        if not fields:
            return res
        res.update({'report_type': '_GET_FBA_FULFILLMENT_INVENTORY_ADJUSTMENTS_DATA_'})
        return res

    @api.model
    def create(self, vals):
        try:
            sequence_id = self.env.ref('amazon_ept.seq_inv_adjustment_report_job').ids
            if sequence_id:
                report_name = self.env['ir.sequence'].get_id(sequence_id[0])
            else:
                report_name = '/'
        except:
            report_name = '/'
        vals.update({'name': report_name})
        return super(StockAdjustmentReportHistory, self).create(vals)

    def list_of_process_logs(self):
        """
        List All Mismatch Details for Stock Adjustment Report.
        @author: Keyur Kanani
        :return:
        """
        model_id = self.env['ir.model']._get('amazon.stock.adjustment.report.history').id
        action = {
            'domain': "[('res_id', '=', " + str(self.id) + "), ('model_id','='," + str(model_id) + ")]",
            'name': 'Stock Adjustment Report Logs',
            'view_mode': 'tree,form',
            'res_model': 'common.log.book.ept',
            'type': 'ir.actions.act_window',
        }
        return action

    @api.model
    def auto_import_stock_adjustment_report(self, args={}):
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env['amazon.seller.ept'].browse(seller_id)
            if seller.stock_adjustment_report_last_sync_on:
                start_date = seller.stock_adjustment_report_last_sync_on
                start_date = start_date - timedelta(hours=10)
            else:
                start_date = datetime.now() - timedelta(days=30)
            start_date = start_date + timedelta(days=seller.inv_adjustment_report_days * -1 or -3)
            start_date = start_date.strftime("%Y-%m-%d %H:%M:%S")
            date_end = datetime.now()
            date_end = date_end.strftime("%Y-%m-%d %H:%M:%S")
            inv_report = self.create({
                'seller_id': seller_id,
                'start_date': start_date,
                'end_date': date_end,
                'state': 'draft',
                'requested_date': time.strftime("%Y-%m-%d %H:%M:%S")
            })
            inv_report.with_context(is_auto_process=True).request_report()
            seller.write({'stock_adjustment_report_last_sync_on': date_end})
        return True

    @api.model
    def auto_process_stock_adjustment_report(self, args={}):
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env['amazon.seller.ept'].browse(seller_id)
            inv_reports = self.search([('seller_id', '=', seller.id),
                                       ('state', 'in', ['_SUBMITTED_', '_IN_PROGRESS_'])
                                       ])
            for report in inv_reports:
                report.with_context(is_auto_process=True).get_report_request_list()
            inv_reports = self.search([('seller_id', '=', seller.id),
                                       ('state', 'in', ['_DONE_', '_SUBMITTED_', '_IN_PROGRESS_']),
                                       ('report_id', '!=', False)
                                       ])
            for report in inv_reports:
                if not report.attachment_id:
                    report.with_context(is_auto_process=True).get_report()
                report.with_context(is_auto_process=True).process_stock_adjustment_report()
                self._cr.commit()
        return True

    def list_of_stock_moves(self):
        stock_move_obj = self.env['stock.move']
        records = stock_move_obj.search([('amz_stock_adjustment_report_id', '=', self.id)])
        action = {
            'domain': "[('id', 'in', " + str(records.ids) + " )]",
            'name': 'Amazon FBA Adjustment Stock Move',
            'view_mode': 'tree,form',
            'res_model': 'stock.move',
            'type': 'ir.actions.act_window',
        }
        return action

    def request_report(self):
        """
        Request _GET_FBA_FULFILLMENT_INVENTORY_ADJUSTMENTS_DATA_ Report from Amazon for specific date range.
        :return: Boolean
        """
        common_log_book_obj = self.env['common.log.book.ept']
        shipping_report_obj = self.env['shipping.report.request.history']
        if not self.seller_id:
            raise Warning('Please select Seller')
        start_date, end_date = self.report_start_and_end_date()
        kwargs = shipping_report_obj.prepare_amazon_request_report_kwargs(self.seller_id)
        kwargs.update({
            'emipro_api': 'request_report_v13',
            'report_type': self.report_type,
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
                    'log_lines': [(0, 0, {'message': 'Inventory Adjustment Report Process' + response.get('reason')})]
                })
            else:
                raise Warning(response.get('reason'))
        else:
            result = response.get('result')
            self.update_report_history(result)
        return True

    def report_start_and_end_date(self):
        """
        Prepare Start and End Date for request reports
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

    def get_report_request_list(self):
        """
        This Method relocates get report list from amazon.
        :return: This Method return boolean(True/False).
        """
        self.ensure_one()
        common_log_book_obj = self.env['common.log.book.ept']
        shipping_report_obj = self.env['shipping.report.request.history']
        list_of_wrapper = []
        if not self.seller_id:
            raise Warning('Please select Seller')
        if not self.report_request_id:
            return True
        kwargs = shipping_report_obj.prepare_amazon_request_report_kwargs(self.seller_id)
        kwargs.update({'emipro_api': 'get_report_request_list_v13', 'request_ids': (self.report_request_id,)})
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            if self._context.get('is_auto_process'):
                common_log_book_obj.create({
                    'type': 'import',
                    'module': 'amazon_ept',
                    'active': True,
                    'log_lines': [(0, 0, {'message': 'Inventory Adjustment Report Process ' + response.get('reason')})]
                })
            else:
                raise Warning(response.get('reason'))
        else:
            list_of_wrapper = response.get('result')

        for result in list_of_wrapper:
            self.update_report_history(result)
        return True

    def update_report_history(self, request_result):
        """
        Update Report History in odoo
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

    def get_report(self):
        """
        This Method relocates get stock report as an attachment in stock reports form view.
        :return: This Method return boolean(True/False).
        """
        self.ensure_one()
        common_log_book_obj = self.env['common.log.book.ept']
        shipping_report_obj = self.env['shipping.report.request.history']

        result = {}
        seller = self.seller_id
        if not seller:
            raise Warning('Please select seller')

        if not self.report_id:
            return True

        kwargs = shipping_report_obj.prepare_amazon_request_report_kwargs(self.seller_id)
        kwargs.update({'emipro_api': 'get_report_v13', 'report_id': self.report_id, })
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            if self._context.get('is_auto_process'):
                common_log_book_obj.create({
                    'type': 'import',
                    'module': 'amazon_ept',
                    'active': True,
                    'log_lines': [(0, 0, {'message': 'Stock adjusment Report Process ' + response.get('reason')})]
                })
            else:
                raise Warning(response.get('reason'))
        else:
            result = response.get('result')

        if result:
            result = result.encode()
            result = base64.b64encode(result)
            file_name = "Stock_adjusments_report_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'

            attachment = self.env['ir.attachment'].create({
                'name': file_name,
                'datas': result,
                'res_model': 'mail.compose.message',
                'type': 'binary'
            })
            self.message_post(body=_("<b>Stock adjusment Report Downloaded</b>"), attachment_ids=attachment.ids)
            self.write({'attachment_id': attachment.id})
            seller.write({'stock_adjustment_report_last_sync_on':datetime.now()})

        return True

    def download_report(self):
        """
        This Method relocates download amazon stock adjustment report.
        :return:This Method return boolean(True/False).
        """
        self.ensure_one()
        if self.attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' % (self.attachment_id.id),
                'target': 'self',
            }
        return True

    def process_stock_adjustment_report(self):
        """
        This Method process stock adjustment report.
        :return:This Method return boolean(True/False).
        """
        self.ensure_one()
        ir_cron_obj = self.env['ir.cron']
        if not self._context.get('is_auto_process', False):
            ir_cron_obj.with_context({'raise_warning': True}).find_running_schedulers(
                'ir_cron_process_fba_stock_adjustment_report_seller_', self.seller_id.id)
        amazon_adjustment_reason_code_obj = self.env['amazon.adjustment.reason.code']
        amazon_process_job_log_obj = self.env['common.log.book.ept']
        amazon_stock_adjustment_config_obj = self.env['amazon.stock.adjustment.config']
        if not self.attachment_id:
            raise Warning("There is no any report are attached with this record.")
        if not self.seller_id:
            raise Warning("Seller is not defind for processing report")
        imp_file = StringIO(base64.b64decode(self.attachment_id.datas).decode())
        reader = csv.DictReader(imp_file, delimiter='\t')
        group_wise_lines_list = {}
        job = amazon_process_job_log_obj.search(
            [('model_id', '=', self.env['ir.model']._get('amazon.stock.adjustment.report.history').id),
             ('res_id', '=', self.id)])
        if not job:
            job = amazon_process_job_log_obj.create({
                'module': 'amazon_ept',
                'type': 'import',
                'model_id': self.env['ir.model']._get('amazon.stock.adjustment.report.history').id,
                'res_id': self.id,
                'active': True,
                'log_lines': [(0, 0, {'message': 'Stock adjustment Report Process'})]
            })
        partially_processed = False
        if self.state == 'partially_processed':
            create_log = False
        else:
            create_log = True
        for row in reader:
            if not row.get('reason'):
                continue
            reason = row.get('reason')
            code = amazon_adjustment_reason_code_obj.search([('name', '=', reason), ('group_id', '!=', False)])
            if not code:
                partially_processed = True
                job.write({'log_lines': [
                    (0, 0, {'message': 'Code %s configuration not found for processing' % (reason)})]})
                continue
            if len(code.ids) > 1:
                partially_processed = True
                job.write({'log_lines': [
                    (0, 0, {'message': 'Multiple Code %s configuration found for processing' % (reason)})]})
                continue
            config = amazon_stock_adjustment_config_obj.search(
                [('group_id', '=', code.group_id.id), ('seller_id', '=', self.seller_id.id)])

            if not config:
                partially_processed = True
                job.write({'log_lines': [
                    (0, 0, {'message': 'Seller wise code %s configuration not found for processing' % (code.name)})]})
                continue

            if not config.is_send_email and not config.location_id and not config.group_id.id == self.env.ref('amazon_ept.amazon_damaged_inventory_ept').id:
                partially_processed = True
                message = ''
                if not config.location_id:
                    message = 'Location not configured for stock adjustment config ERP Id %s || group name %s' % (
                        config.id, config.group_id.name)
                job.write({'log_lines': [(0, 0, {'message': message})]})
                continue
            if config in group_wise_lines_list:
                group_wise_lines_list.get(config).append(row)
            else:
                group_wise_lines_list.update({config: [row]})
        if group_wise_lines_list:
            # process_group_wise_lines This Method represent process prepare group wise line.
            partially_processed = self.process_group_wise_lines(group_wise_lines_list, job, partially_processed,
                                                                create_log)
            partially_processed and self.write({'state': 'partially_processed'}) or self.write({'state': 'processed'})
        return True

    def process_group_wise_lines(self, group_of_data, job, partially_processed, create_log):
        """
        This Method represent process group wise lines,
        :param group_of_data: This arguments represent group data of amazon.
        :param job: This arguments represent log job of amazon.
        :param model_id: This arguments represent model id.
        :param partially_processed: This arguments represent state of process (True/False).
        :param create_log: This arguments represent create log (True/False).
        :return: This Method returns the state of adjustment report process.
        """
        for config, lines in group_of_data.items():
            lines.reverse()
            if config.is_send_email:
                # create_email_of_unprocess_lines This Method represents the unprocessed line that creates attachment and sent the attachment to the client.
                self.create_email_of_unprocess_lines(config, lines, job)
                continue
            if config.group_id.is_counter_part_group:
                partially_processed = self.process_counter_part_lines(config, lines, job,
                                                                      partially_processed, create_log)
            else:
                partially_processed = self.process_non_counter_part_lines(config, lines, job,
                                                                          partially_processed, create_log)
        return partially_processed

    def create_email_of_unprocess_lines(self, config, lines, job):
        """
        This Method represents the unprocessed line that creates attachment and sent the attachment to the client.
        :param config: These arguments represent config of group lines.
        :param lines: This arguments represent lines of group data items.
        :param job: This arguments represent log job of amazon.
        :return: This Method returns boolean(True/False).
        """
        template = config.email_template_id
        if template:
            subtype = 'amazon_ept.amazon_stock_adjustment_subtype_ept'
        else:
            subtype = False
        field_names = []
        buff = StringIO()
        for line in lines:
            if not field_names:
                field_names = line.keys()
                csvwriter = UnicodeDictWriter(
                    buff, field_names, delimiter='\t'
                )
                csvwriter.writer.writerow(field_names)
            csvwriter.writerow(line)
        buff.seek(0)
        file_data = buff.read()
        instances = self.seller_id.instance_ids
        amazon_encoding = instances and instances[0].amazon_encodings
        vals = {
            'name': 'inv_unprocessed_lines.csv',
            'datas': base64.b64encode(file_data.encode(amazon_encoding)),
            #'datas_fname': 'inv_unprocessed_lines.csv',
            'type': 'binary',
            'res_model': 'amazon.stock.adjustment.report.history',
        }
        attachment = self.env['ir.attachment'].create(vals)
        subject = template and template.render_template(template.subject, 'amazon.stock.adjustment.report.history',
                                                        self.ids) or ''
        body = template and template.render_template(template.body_html, 'amazon.stock.adjustment.report.history',
                                                     self.ids) or ''
        message_type = template and 'email' or 'notification'
        self.message_post(subject=subject, message_type=message_type, body=body, subtype=subtype,
                          attachment_ids=attachment.ids)
        return True

    def process_counter_part_lines(self, config, lines, job, partially_processed, create_log):
        """
        This Method represents the processed counter part lines.
        :param config: These arguments represent config of group lines.
        :param lines: This arguments represent lines of group data items.
        :param job: This arguments represent log job of amazon.
        :param model_id: This arguments represent model id.
        :param partially_processed: This arguments represent state of process (True/False).
        :param create_log: This arguments represent create log (True/False).
        :return: This Method returns the state of adjustment report process.
        """
        temp_lines = copy.copy(lines)
        fulfillment_center_obj = self.env['amazon.fulfillment.center']
        transaction_item_ids = []
        amazon_adjustment_reason_code_obj = self.env['amazon.adjustment.reason.code']
        stock_move_obj = self.env['stock.move']
        counter_line_list = []
        stock_move_ids = []
        fulfillment_warehouse = {}
        code_dict = {}
        for line in lines:
            if line.get('transaction-item-id') in transaction_item_ids:
                continue
            reason = line.get('reason')

            if line.get('reason') not in code_dict:
                reason_code = amazon_adjustment_reason_code_obj.search(
                    [('name', '=', line.get('reason')), ('group_id', '=', config.group_id.id)])
                code_dict.update({line.get('reason'): reason_code})
            code = code_dict.get(line.get('reason'))
            if not code:
                continue

            counter_part_code = code.counter_part_id.name
            if not counter_part_code:
                continue
            counter_line_list = self.prepare_counter_line_list(line, temp_lines, code.counter_part_id.name,
                                                               transaction_item_ids, counter_line_list, reason,
                                                               create_log, job)
        if counter_line_list:
            for counter_line in counter_line_list:
                line = counter_line[0]
                p_line = counter_line[1]
                sku = line.get('sku')
                product = self.find_amazon_product_for_process_adjustment_line(line, job)
                if not product:
                    # log product not found in odoo
                    job.write({'log_lines': [
                        (0, 0, {'message': 'Product SKU [%s] not found in odoo' % (sku)})]})
                    continue

                p_line_qty = float(p_line.get('quantity', 0.0))
                adjustment_date = p_line.get('adjusted-date', False)
                transaction_item_id = p_line.get('transaction-item-id')
                fulfillment_center_id = p_line.get('fulfillment-center-id')
                p_line_disposition = p_line.get('disposition')
                other_line_disposition = line.get('disposition')
                try:
                    adjustment_date = time.mktime(datetime.strptime(adjustment_date, "%Y-%m-%dT%H:%M:%S%z").timetuple())
                    adjustment_date = datetime.fromtimestamp(adjustment_date)
                except:
                    adjustment_date = adjustment_date[:len(adjustment_date)-3] + adjustment_date[len(adjustment_date)-2:]
                    adjustment_date = time.mktime(datetime.strptime(adjustment_date, "%Y-%m-%dT%H:%M:%S%z").timetuple())
                    adjustment_date = datetime.fromtimestamp(adjustment_date, tz=timezone.utc)
                    adjustment_date = adjustment_date.strftime("%Y-%m-%d %H:%M:%S")

                if fulfillment_center_id not in fulfillment_warehouse:
                    fulfillment_center = fulfillment_center_obj.search(
                        [('center_code', '=', fulfillment_center_id), ('seller_id', '=', self.seller_id.id)], limit=1)
                    fn_warehouse = fulfillment_center and fulfillment_center.warehouse_id or False
                    if not fn_warehouse or ((p_line_disposition != 'SELLABLE' or other_line_disposition != 'SELLABLE')
                                            and not fn_warehouse.unsellable_location_id):
                        partially_processed = True
                        if not fn_warehouse:
                            message = 'Warehouse not found for fulfillment center %s || Product %s' % (
                                fulfillment_center_id, line.get('sku'))
                        else:
                            message = 'Unsellable location not found for Warehouse %s || Product %s' % (
                                fn_warehouse.name, line.get('sku'))
                        job.write({'log_lines': [(0, 0, {'message': 'mismatch' + message})]})
                        continue
                    fulfillment_warehouse.update({fulfillment_center_id: [fn_warehouse, fulfillment_center]})
                warehouse = fulfillment_warehouse.get(fulfillment_center_id, [False])[0]
                fulfillment_center = fulfillment_warehouse.get(fulfillment_center_id, [False])[1]

                if p_line.get('reason') not in code_dict:
                    reason_code = amazon_adjustment_reason_code_obj.search(
                        [('name', '=', p_line.get('reason')), ('group_id', '=', config.group_id.id)])
                    code_dict.update({p_line.get('reason'): reason_code})
                code = code_dict.get(p_line.get('reason'))

                exist_move_domain = [('product_uom_qty', '=', p_line_qty), ('product_id', '=', product.id),
                                     ('adjusted_date', '=', adjustment_date),
                                     ('transaction_item_id', '=', transaction_item_id),
                                     ('fulfillment_center_id', '=', fulfillment_center.id), ('code_id', '=', code.id)
                                     ]

                if p_line_disposition != 'SELLABLE':
                    destination_location_id = warehouse.unsellable_location_id.id
                else:
                    destination_location_id = warehouse.lot_stock_id.id
                if other_line_disposition != 'SELLABLE':
                    source_location_id = warehouse.unsellable_location_id.id
                else:
                    source_location_id = warehouse.lot_stock_id.id

                exist_move_domain += [('location_id', '=', source_location_id),
                                      ('location_dest_id', '=', destination_location_id)]

                exist_stock_move = stock_move_obj.search(exist_move_domain)
                if exist_stock_move:
                    job.write({
                        'log_lines': [(0, 0, {'message': 'Line already processed for Product %s || Code %s-%s' % (
                            product.name or False, p_line.get('reason'), line.get('reason'))})]
                    })
                    continue
                else:
                    vals = {
                        'product_uom_qty': abs(p_line_qty),
                        'product_id': product.id,
                        'product_uom': product.uom_id.id,
                        'state': 'confirmed',
                        'adjusted_date': adjustment_date,
                        'origin': self.name,
                        'name': product.name,
                        'transaction_item_id': transaction_item_id or False,
                        'fulfillment_center_id': fulfillment_center.id,
                        'code_id': code.id,
                        'location_id': source_location_id,
                        'location_dest_id': destination_location_id,
                        'code_description': code.description,
                        'amz_stock_adjustment_report_id': self.id
                    }
                    stock_move = stock_move_obj.create(vals)
                    stock_move_ids.append(stock_move.id)
            self.prepare_stock_move_create(stock_move_ids)
        return partially_processed

    def process_non_counter_part_lines(self, config, lines, job, partially_processed, create_log):
        """
         This Method represents processed non-counterpart lines.
         : param config: These arguments represent the config of group lines.
         : param lines: These arguments represent lines of group data items.
         : param job: These arguments represent the log job of amazon.
         : param model_id: These arguments represent model id.
         : param partially_processed: These arguments represent the state of the process (True/False).
         : param create_log: This arguments represent create log (True/False).
         : return: This Method returns the state of adjustment report process.
         """
        amazon_adjustment_reason_code_obj = self.env['amazon.adjustment.reason.code']
        fulfillment_center_obj = self.env['amazon.fulfillment.center']
        stock_move_ids = []
        stock_move_obj = self.env['stock.move']
        for line in lines:
            sku = line.get('sku')
            product = self.find_amazon_product_for_process_adjustment_line(line, job)
            if not product:
                # log: Product not found
                job.write({
                    'log_lines': [(0, 0, {
                        'message': 'Product Not Found for order %s' % (sku)})]
                })
                continue
            reason = line.get('reason')
            fulfillment_center_id = line.get('fulfillment-center-id')
            p_line_qty = float(line.get('quantity', 0.0))
            disposition = line.get('disposition')
            adjustment_date = line.get('adjusted-date', False)
            transaction_item_id = line.get('transaction-item-id')
            try:
                adjustment_date = time.mktime(datetime.strptime(adjustment_date, "%Y-%m-%dT%H:%M:%S%z").timetuple())
                adjustment_date = datetime.fromtimestamp(adjustment_date)
            except:
                adjustment_date = adjustment_date[:len(adjustment_date)-3] + adjustment_date[len(adjustment_date)-2:]
                adjustment_date = time.mktime(datetime.strptime(adjustment_date, "%Y-%m-%dT%H:%M:%S%z").timetuple())
                adjustment_date = datetime.fromtimestamp(adjustment_date, tz=timezone.utc)
                adjustment_date = adjustment_date.strftime("%Y-%m-%d %H:%M:%S")

            fulfillment_center = fulfillment_center_obj.search(
                [('center_code', '=', fulfillment_center_id), ('seller_id', '=', self.seller_id.id)], limit=1)
            warehouse = fulfillment_center and fulfillment_center.warehouse_id or False
            if not warehouse or (disposition == 'UNSELLABLE' and not warehouse.unsellable_location_id):
                partially_processed = True
                if not warehouse:
                    message = 'Warehouse not found for fulfillment center %s || Product %s' % (
                        fulfillment_center_id, line.get('sku'))
                else:
                    message = 'Unsellable location not found for Warehouse %s' % (warehouse.name)
                job.write({'log_lines': [(0, 0, {'message': 'mismatch' + message})]})
                continue
            code = amazon_adjustment_reason_code_obj.search(
                [('name', '=', reason), ('group_id', '=', config.group_id.id)])
            exist_move_domain = [('product_uom_qty', '=', abs(p_line_qty)), ('product_id', '=', product.id),
                                 ('adjusted_date', '=', adjustment_date),
                                 ('transaction_item_id', '=', transaction_item_id),
                                 ('fulfillment_center_id', '=', fulfillment_center.id), ('code_id', '=', code.id)
                                 ]
            if p_line_qty < 0.0:
                if disposition == 'SELLABLE':
                    destination_location_id = config.location_id.id
                    source_location_id = warehouse.lot_stock_id.id
                else:
                    destination_location_id = config.location_id.id
                    source_location_id = warehouse.unsellable_location_id.id
            else:
                if disposition == 'SELLABLE':
                    source_location_id = config.location_id.id
                    destination_location_id = warehouse.lot_stock_id.id
                else:
                    source_location_id = config.location_id.id
                    destination_location_id = warehouse.unsellable_location_id.id

            exist_move_domain += [('location_id', '=', source_location_id),
                                  ('location_dest_id', '=', destination_location_id)]

            exist_move = stock_move_obj.search(exist_move_domain)
            if exist_move:
                job.write({
                    'log_lines': [(0, 0, {
                        'message': 'Line already processed for Product %s || Code %s' % (product.name, reason)})]
                })
                continue
            else:
                vals={
                    'product_uom_qty': abs(p_line_qty),
                    'product_id': product.id,
                    'product_uom': product.uom_id.id,
                    'state': 'draft',
                    'adjusted_date': adjustment_date,
                    'origin': self.name,
                    'name': product.name,
                    'transaction_item_id': transaction_item_id or False,
                    'fulfillment_center_id': fulfillment_center.id,
                    'code_id': code.id,
                    'location_id': source_location_id,
                    'location_dest_id': destination_location_id,
                    'code_description': code.description,
                    'amz_stock_adjustment_report_id': self.id
                }
                stock_move = stock_move_obj.create(vals)
                stock_move_ids.append(stock_move.id)
        # This Method prepare value for stock move,stock move line and create stock move,stock moveline
        self.prepare_stock_move_create(stock_move_ids)
        return partially_processed

    def prepare_stock_move_create(self, stock_move_ids):
        """
        This Method represents to prepare stock move value and stock move create.
        :param stock_move_ids: This arguments represents stock move ids list.
        :return: This Method returns boolean(True/False).
        """
        stock_move_obj = self.env['stock.move']
        if stock_move_ids:
            stock_moves = stock_move_obj.browse(stock_move_ids)
            for stock_move in stock_moves:
                stock_move._action_confirm()
                stock_move._action_assign()
                stock_move._set_quantity_done(stock_move.product_uom_qty)
                # self.env['stock.move.line'].create(stock_move._prepare_move_line_vals(quantity=remaining_qty, reserved_quant=stock_move.reserved_availability))
                stock_move._action_done()

        return True

    def prepare_counter_line_list(self, line, temp_lines, counter_part_code, transaction_item_ids, counter_line_list,
                                  reason, create_log, job):
        """
        This Method represents to prepare a list of counterpart lines.
        :param line: These arguments represent a line of the amazon product listing.
        :param temp_lines: These arguments represent temp lines of the amazon product listing.
        :param counter_part_code: This arguments represent counter part code.
        :param transaction_item_ids: These arguments represent the transaction item id of amazon.
        :param counter_line_list: These arguments prepare counter line list.
        :param reason: This argument reason of amazon.
        :param create_log: This arguments represent create log (True/False).
        :param job: These arguments represent the log job of amazon.
        :return: This Method return counter line list.
        """
        for temp_line in temp_lines:
            if temp_line.get('reason') == counter_part_code and abs(float(temp_line.get('quantity', 0.0))) == abs(
                    float(line.get('quantity', 0.0))) \
                    and temp_line.get('transaction-item-id') not in transaction_item_ids:
                if line.get('adjusted-date') == temp_line.get('adjusted-date') and line.get(
                        'fnsku') == temp_line.get('fnsku') \
                        and line.get('sku') == temp_line.get('sku') and line.get(
                    'fulfillment-center-id') == temp_line.get('fulfillment-center-id'):

                    transaction_item_ids.append(temp_line.get('transaction-item-id'))
                    counter_line_list.append((line, temp_line))
                    message = """ 
                                Counter Part Combination line ||                                
                                sku : %s || adjustment-date %s || fulfillment-center-id %s || quantity %s ||
                                Code %s - Disposition %s & %s - Disposition %s
                        """ % (line.get('sku'),
                               line.get('adjusted-date'),
                               line.get('fulfillment-center-id'),
                               line.get('quantity', 0.0),
                               reason, line.get('disposition'), temp_line.get('reason'),
                               temp_line.get('disposition')
                               )
                    if create_log:
                        job.write({'log_lines': [(0, 0, {'message': message})]})
                    break
        return counter_line_list

    def find_amazon_product_for_process_adjustment_line(self, line, job):
        """
        This Method represents search amazon product for product adjustment line.
        :param line: These arguments represent the line of amazon.
        :param job: These arguments represent the log job of amazon.
        :return: This Method return product.
        """
        amazon_product_obj = self.env['amazon.product.ept']
        sku = line.get('sku')
        asin = line.get('fnsku')
        amazon_product = amazon_product_obj.search([('seller_sku', '=', sku), ('fulfillment_by', '=', 'FBA')], limit=1)
        if not amazon_product:
            amazon_product = amazon_product_obj.search([('product_asin', '=', asin), ('fulfillment_by', '=', 'FBA')],
                                                       limit=1)
        product = amazon_product and amazon_product.product_id or False
        if not amazon_product and job:
            job.write({'log_lines': [(0, 0, {'message': 'Product  not found for SKU %s & ASIN %s' % (sku, asin)})]})
        return product
