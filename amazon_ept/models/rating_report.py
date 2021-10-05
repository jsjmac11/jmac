from odoo import models, fields, api, _
from datetime import timedelta
import base64
import csv
from io import StringIO
from odoo.exceptions import Warning
import time
from datetime import datetime
from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT


class RatingReportHistory(models.Model):
    _name = "rating.report.history"
    _description = "Rating Report History"
    _inherit = ['mail.thread']
    _order = 'id desc'

    @api.depends('seller_id')
    def get_company(self):
        for record in self:
            company_id = record.seller_id and record.seller_id.company_id.id or False
            if not company_id:
                company_id = self.env.company.id
            record.company_id = company_id

    def get_rating_count(self):
        rating_obj = self.env['rating.rating']
        self.rating_count = rating_obj.search_count([('amz_rating_report_id', '=', self.id)])

    def get_log_count(self):
        """
        Find all log associated with this report
        :return:
        """
        log_obj = self.env['common.log.book.ept']
        model_id = self.env['ir.model']._get('rating.report.history').id
        self.log_count = log_obj.search_count([('res_id', '=', self.id), ('model_id', '=', model_id)])

    name = fields.Char(size=256, string='Name')
    state = fields.Selection([('draft', 'Draft'), ('_SUBMITTED_', 'SUBMITTED'), ('_IN_PROGRESS_', 'IN_PROGRESS'),
                              ('_CANCELLED_', 'CANCELLED'), ('_DONE_', 'Report Received'),
                              ('_DONE_NO_DATA_', 'DONE_NO_DATA'), ('processed', 'PROCESSED'),
                              ],
                             string='Report Status', default='draft')
    seller_id = fields.Many2one('amazon.seller.ept', string='Seller', copy=False,
                                help="Select Seller id from you wanted to get Rating Report.")
    attachment_id = fields.Many2one('ir.attachment', string="Attachment")
    instance_id = fields.Many2one("amazon.instance.ept", string="Instance")
    report_id = fields.Char('Report ID', readonly='1')
    report_type = fields.Char(size=256, string='Report Type', help="Amazon Report Type")
    report_request_id = fields.Char('Report Request ID', readonly='1')
    start_date = fields.Datetime('Start Date', help="Report Start Date")
    end_date = fields.Datetime('End Date', help="Report End Date")
    requested_date = fields.Datetime('Requested Date', default=time.strftime("%Y-%m-%d %H:%M:%S"),
                                     help="Report Requested Date")
    user_id = fields.Many2one('res.users', string="Requested User", help="Track which odoo user has requested report")
    company_id = fields.Many2one('res.company', string="Company", copy=False, compute="get_company", store=True)
    rating_count = fields.Integer(compute="get_rating_count", string="Rating Count", store=False)
    log_count = fields.Integer(compute="get_log_count", string="Log Count", store=False)
    amz_rating_report_ids = fields.One2many('rating.rating', 'amz_rating_report_id',
                                            string="Ratings")

    @api.onchange('seller_id')
    def on_change_seller_id(self):
        """
        This Method relocates check seller and write start date and end date.
        :return: This Method return updated value.
        """
        if self.seller_id:
            self.start_date = datetime.now() - timedelta(self.seller_id.rating_report_days)
            self.end_date = datetime.now()

    def unlink(self):
        """
        This Method if report is processed then raise warning.
        """
        for report in self:
            if report.state == 'processed':
                raise Warning(_('You cannot delete processed report.'))
        return super(RatingReportHistory, self).unlink()

    @api.model
    def default_get(self, fields):
        res = super(RatingReportHistory, self).default_get(fields)
        if not fields:
            return res
        res.update({'report_type': '_GET_SELLER_FEEDBACK_DATA_'})
        return res

    @api.model
    def create(self, vals):
        try:
            sequence_id = self.env.ref('amazon_ept.seq_rating_report_job').ids
            if sequence_id:
                report_name = self.env['ir.sequence'].get_id(sequence_id[0])
            else:
                report_name = '/'
        except:
            report_name = '/'
        vals.update({'name': report_name})
        return super(RatingReportHistory, self).create(vals)

    #
    def list_of_process_logs(self):
        """
        List All Mismatch Details for Rating Report.
        @author: Tushar Lathiya
        :return:
        """
        model_id = self.env['ir.model']._get('rating.report.history').id
        action = {
            'domain': "[('res_id', '=', " + str(self.id) + "), ('model_id','='," + str(model_id) + ")]",
            'name': 'Rating Report Logs',
            'view_mode': 'tree,form',
            'res_model': 'common.log.book.ept',
            'type': 'ir.actions.act_window',
        }
        return action

    @api.model
    def auto_import_rating_report(self, args={}):
        """
        This Method relocate import rating using crone.
        :param args: This Argument relocate seller id when the crone run in this argument given amazon seller id
        :return: This Method Return Boolean(True).
        """
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env['amazon.seller.ept'].browse(seller_id)
            if seller.rating_report_last_sync_on:
                start_date = seller.rating_report_last_sync_on
                start_date = start_date + timedelta(days=seller.rating_report_days * -1 or -3)

            else:
                start_date = datetime.now() - timedelta(days=30)
                start_date = start_date.strftime("%Y-%m-%d %H:%M:%S")
            date_end = datetime.now()
            date_end = date_end.strftime("%Y-%m-%d %H:%M:%S")
            report_type = '_GET_SELLER_FEEDBACK_DATA_'
            rating_report = self.create({'report_type': report_type,
                                         'seller_id': seller_id,
                                         'start_date': start_date,
                                         'end_date': date_end,
                                         'state': 'draft',
                                         'requested_date': time.strftime("%Y-%m-%d %H:%M:%S")
                                         })
            rating_report.with_context(is_auto_process=True).request_report()
            seller.write({'rating_report_last_sync_on': date_end})
        return True

    @api.model
    def auto_process_rating_report(self, args={}):
        """
        This Method Relocate auto process rating rating using crone.
        :param args: This Argument relocate seller id when the crone run in this argument given amazon seller id
        :return: This Method Return Boolean(True).
        """
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env['amazon.seller.ept'].browse(seller_id)
            rating_report = self.search([('seller_id', '=', seller.id),
                                         ('state', 'in', ['_SUBMITTED_', '_IN_PROGRESS_', '_DONE_'])
                                         ])

            for report in rating_report:
                if report.state != '_DONE_':
                    report.with_context(is_auto_process=True).get_report_request_list()
                if report.report_id and report.state == '_DONE_' and not report.attachment_id:
                    report.with_context(is_auto_process=True).get_report()
                if report.attachment_id:
                    report.with_context(is_auto_process=True).process_rating_report()
                self._cr.commit()
        return True

    def list_of_rating(self):
        """
        This Method relocate list of amazon rating.
        :return:
        """
        rating_obj = self.env['rating.rating']
        records = rating_obj.search([('amz_rating_report_id', '=', self.id)])
        action = {
            'domain': "[('id', 'in', " + str(records.ids) + " )]",
            'name': 'Amazon Rating',
            'view_mode': 'tree,form',
            'res_model': 'rating.rating',
            'type': 'ir.actions.act_window',
        }
        return action

    def request_report(self):
        """
        Request _GET_SELLER_FEEDBACK_DATA_ Report from Amazon for specific date range.
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
                    'log_lines': [(0, 0, {'message': 'Rating Report Process' + response.get('reason')})]
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
                    'log_lines': [(0, 0, {'message': 'Rating Report Process ' + response.get('reason')})]
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
        This Method relocates get rating report as an attachment in rating reports form view.
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
                    'log_lines': [(0, 0, {'message': 'Rating Report Process ' + response.get('reason')})]
                })
            else:
                raise Warning(response.get('reason'))
        else:
            result = response.get('result')

        if result:
            result = result.encode()
            result = base64.b64encode(result)
            file_name = "Rating_report_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'

            attachment = self.env['ir.attachment'].create({
                'name': file_name,
                'datas': result,
                'res_model': 'mail.compose.message',
                'type': 'binary'
            })
            self.message_post(body=_("<b>Rating Report Downloaded</b>"), attachment_ids=attachment.ids)
            self.write({'attachment_id': attachment.id})
            seller.write({'rating_report_last_sync_on': datetime.now()})
        return True

    def download_report(self):
        """
        This Method relocates download amazon rating report.
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

    def process_rating_report(self):
        """
        This Method process rating report.
        :return:This Method return boolean(True/False).
        """
        self.ensure_one()
        ir_cron_obj = self.env['ir.cron']
        if not self._context.get('is_auto_process', False):
            ir_cron_obj.with_context({'raise_warning': True}).find_running_schedulers(
                'ir_cron_process_rating_request_report_seller_', self.seller_id.id)
        amazon_process_job_log_obj = self.env['common.log.book.ept']
        sale_order_obj = self.env['sale.order']
        rating_obj = self.env['rating.rating']
        ir_model = self.env['ir.model']
        if not self.attachment_id:
            raise Warning("There is no any report are attached with this record.")
        if not self.seller_id:
            raise Warning("Seller is not defind for processing report")
        imp_file = StringIO(base64.b64decode(self.attachment_id.datas).decode())
        reader = csv.DictReader(imp_file, delimiter='\t')
        model_id = self.env['ir.model']._get('rating.report.history').id
        ir_model = ir_model.search([('model', '=', 'sale.order')])
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
                'log_lines': [(0, 0, {'message': 'Import Rating Report Process'})]
            })
        for row in reader:
            amz_order_id = row.get('Order ID')
            amz_rating_value = row.get('Rating')
            amz_rating_comment = row.get('Comments')
            amz_your_response = row.get('Your Response')
            amz_rating_date = row.get('Date')
            amz_rating_date = datetime.strptime(amz_rating_date, '%d/%m/%y')
            amazon_sale_order = sale_order_obj.search(
                [('amz_order_reference', '=', amz_order_id),
                 ('amz_instance_id', 'in', self.seller_id.instance_ids.ids)])
            if not amazon_sale_order:
                job.write({'log_lines': [
                    (0, 0, {'message': 'This Order %s does not exist in odoo' % (amz_order_id),
                            'order_ref': amz_order_id})]})
                continue
            amazon_order_rating = rating_obj.search(
                [('res_model', '=', 'sale.order'), ('res_id', '=', amazon_sale_order.id)])
            if not amazon_order_rating:
                rating_obj.create({
                    'rating': float(amz_rating_value) if amz_rating_value is not None else False,
                    'feedback': amz_rating_comment,
                    'res_model_id': ir_model.id,
                    'res_id': amazon_sale_order.id,
                    'consumed': True,
                    'partner_id': amazon_sale_order.partner_id.id,
                    'amz_instance_id': amazon_sale_order.amz_instance_id.id,
                    'amz_fulfillment_by': amazon_sale_order.amz_fulfillment_by,
                    'amz_rating_report_id': self.id,
                    'publisher_comment': amz_your_response,
                    'amz_rating_submitted_date': amz_rating_date
                })
            else:
                job.write({'log_lines': [
                    (0, 0, {'message': 'For This Order %s rating already exist in odoo' % (amz_order_id),
                            'order_ref': amz_order_id})]})
                continue
        self.write({'state': 'processed'})
        return True
