import time
from dateutil import parser
import pytz
from datetime import datetime, timedelta
import base64
import csv
from io import StringIO
from odoo import models, fields, api, _
from odoo.exceptions import Warning
from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT

utc = pytz.utc


class AmazonLiveStockReportEpt(models.Model):
    _name = "amazon.fba.live.stock.report.ept"
    _description = "Amazon Live Stock Report"
    _inherit = ['mail.thread']
    _order = 'id desc'

    @api.depends('seller_id')
    def get_company(self):
        for record in self:
            company_id = record.seller_id and record.seller_id.company_id.id or False
            if not company_id:
                company_id = self.env.company.id
            record.company_id = company_id

    @api.model
    def create(self, vals):
        try:
            sequence = self.env.ref('amazon_ept.seq_import_live_stock_report_job')
            if sequence:
                report_name = sequence.next_by_id()
            else:
                report_name = '/'
        except:
            report_name = '/'
        vals.update({'name': report_name})
        return super(AmazonLiveStockReportEpt, self).create(vals)

    def list_of_inventory(self):
        action = {
            'domain': "[('id', 'in', " + str(self.inventory_ids.ids) + " )]",
            'name': 'FBA Live Stock Inventory',
            'view_mode': 'tree,form',
            'res_model': 'stock.inventory',
            'type': 'ir.actions.act_window',
        }
        return action

    def get_inventory_count(self):
        for record in self:
            record.inventory_count = len(record.inventory_ids.ids)

    name = fields.Char(size=256, string='Name')
    state = fields.Selection(
        [('draft', 'Draft'),
         ('_SUBMITTED_', 'SUBMITTED'),
         ('_IN_PROGRESS_', 'IN_PROGRESS'),
         ('_CANCELLED_', 'CANCELLED'),
         ('_DONE_', 'DONE'),
         ('_DONE_NO_DATA_', 'DONE_NO_DATA'),
         ('processed', 'PROCESSED')],
        string='Report Status', default='draft',
        help="This Field relocates state of fba live inventory process.")
    seller_id = fields.Many2one('amazon.seller.ept',
                                string='Seller',
                                copy=False,
                                help="Select Seller id from you wanted to get Shipping report")
    attachment_id = fields.Many2one('ir.attachment',
                                    string="Attachment",
                                    help="This Field relocates attachment id.")
    report_id = fields.Char('Report ID',
                            readonly='1',
                            help="This Field relocates report id.")
    report_type = fields.Char(size=256,
                              string='Report Type',
                              help='This Field relocates report type.')
    report_request_id = fields.Char('Report Request ID',
                                    readonly='1',
                                    help="This Field relocates report request id of amazon.")
    start_date = fields.Datetime('Start Date',
                                 help="Report Start Date")
    end_date = fields.Datetime('End Date',
                               help="Report End Date")
    requested_date = fields.Datetime('Requested Date',
                                     default=time.strftime("%Y-%m-%d %H:%M:%S"),
                                     help="Report Requested Date")
    report_date = fields.Date('Report Date')
    inventory_ids = fields.One2many('stock.inventory',
                                    'fba_live_stock_report_id',
                                    string='Inventory',
                                    help="This Field relocates inventory ids.")
    user_id = fields.Many2one('res.users',
                              string="Requested User",
                              help="Track which odoo user has requested report")
    company_id = fields.Many2one('res.company',
                                 string="Company",
                                 copy=False,
                                 compute="get_company",
                                 store=True,
                                 help="This Field relocates amazon company")
    amz_instance_id = fields.Many2one('amazon.instance.ept',
                                      string="Instance",
                                      help="This Field relocates amazon instance.")
    #is_pan_european = fields.Boolean(string='Is Pan European', related="seller_id.is_pan_european",readonly=True,help="This Field relocates is pan euroean.")

    amazon_program =fields.Selection(related="seller_id.amazon_program")
    inventory_count = fields.Integer("Inventory Count",
                                     compute="get_inventory_count",
                                     help="This Field relocates Inventory count.")
    log_count = fields.Integer(compute="get_log_count", string="Log Count")

    def unlink(self):
        """
        This Method if report is processed then raise warning.
        """
        for report in self:
            if report.state == 'processed':
                raise Warning(_('You cannot delete processed report.'))
        return super(AmazonLiveStockReportEpt, self).unlink()

    def list_of_logs(self):
        model_id = self.env['ir.model']._get('amazon.fba.live.stock.report.ept').id
        action = {
            'domain': "[('res_id', '=', " + str(self.id) + " ), ('model_id', '=', "+ str(model_id)
                      +")]",
            'name': 'MisMatch Logs',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'common.log.book.ept',
            'type': 'ir.actions.act_window',
        }
        return action

    def get_log_count(self):
        common_log_book_obj = self.env['common.log.book.ept']
        model_id = self.env['ir.model']._get('amazon.fba.live.stock.report.ept').id
        self.log_count = common_log_book_obj.search_count(
            [('model_id', '=', model_id), ('res_id', '=', self.id)])

    @api.model
    def auto_import_amazon_fba_live_stock_report(self, args={}):
        """
        Import amazon fba live inventory reports.
        If Non European Seller import report instance wise
        If European Seller:
            PAN EU: Import report Seller wise
            EFN: Import Report Seller Wise
            MCI: Import Report Instance wise
            CEP: Import Report Seller Wise
        @author: Keyur Kanani

        Updated by : twinkalc / 6 jan 2021
        Updated code to process if amazon program in Pan EU and uk instance is found than
        request live inventory report for UK else for all the seller marketplace

        :param args:
        :return:
        """
        seller_id = args.get('seller_id', False)
        uk_instance_id = args.get('uk_instance_id', False)
        seller = self.env['amazon.seller.ept'].browse(seller_id)
        if seller:
            if seller.inventory_report_last_sync_on:
                start_date = seller.inventory_report_last_sync_on
                start_date = start_date + timedelta(days=seller.live_inv_adjustment_report_days * -1 or -3)
            else:
                start_date = datetime.now() + timedelta(days=seller.live_inv_adjustment_report_days * -1 or -3)
            start_date = start_date.strftime("%Y-%m-%d %H:%M:%S")
            date_end = datetime.now()
            date_end = date_end.strftime("%Y-%m-%d %H:%M:%S")

            if seller.is_another_soft_create_fba_inventory:
                if not start_date or not date_end:
                    raise Warning('Please select Date Range.')
                vals = {'start_date':start_date,
                        'end_date':date_end,
                        'seller_id':seller}
                if args.get('instance_id', False) or uk_instance_id:
                    instance_id = self.env['amazon.instance.ept'].browse(args.get('instance_id') or uk_instance_id)
                    vals.update({'us_region_instance_id': instance_id})
                return self.get_inventory_report(vals)
            else:
                if seller.amazon_program in ('pan_eu','cep'):
                    if uk_instance_id:
                        fba_live_stock_report_uk = self.create({'seller_id': seller.id,
                                                                'amz_instance_id': uk_instance_id,
                                                                'report_type': '_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_'})
                        fba_live_stock_report_uk.request_report()
                    else:
                        fba_live_stock_report = self.create(
                            {'seller_id':seller.id,
                             'report_type':'_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_'})
                        fba_live_stock_report.request_report()
                elif not seller.is_european_region and not seller.amz_fba_us_program == 'narf':
                    if args.get('instance_id', False):
                        fba_live_stock_report = self.create(
                            {'seller_id':seller.id, 'report_date':datetime.now(),
                             'amz_instance_id':args.get('instance_id'),
                             'report_type':'_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_'})
                        fba_live_stock_report.request_report()
                    else:
                        for instance in seller.instance_ids:
                            fba_live_stock_report = self.create(
                                    {'seller_id':seller.id, 'report_date':datetime.now(),
                                     'amz_instance_id':instance.id,
                                     'report_type':'_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_'})
                            fba_live_stock_report.request_report()
                elif seller.amazon_program == 'efn' or seller.amz_fba_us_program == 'narf':
                    fba_live_stock_report = self.create(
                            {'seller_id':seller.id,'start_date':start_date,
                             'end_date':date_end,
                             'report_type':'_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_'})
                    fba_live_stock_report.request_report()
                elif seller.amazon_program in ('mci','efn+mci'):
                    if args.get('instance_id', False):
                        fba_live_stock_report = self.create(
                            {'seller_id':seller.id, 'start_date':start_date,
                             'end_date':date_end, 'amz_instance_id':args.get('instance_id'),
                             'report_type':'_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_'})
                        fba_live_stock_report.request_report()
                    else:
                        for instance in seller.instance_ids:
                            fba_live_stock_report = self.create(
                                    {'seller_id':seller.id, 'start_date':start_date,
                                     'end_date':date_end, 'amz_instance_id':instance.id,
                                     'report_type':'_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_'})
                            fba_live_stock_report.request_report()

        return True

    def get_inventory_report(self, vals):
        amazon_process_job_log_obj = self.env['common.log.book.ept']
        model_id = self.env['ir.model']._get('amazon.fba.live.stock.report.ept').id
        amazon_instance = self.env['amazon.instance.ept']
        job = False
        inv_report_ids = []
        start_date = vals.get('start_date')
        end_date = vals.get('end_date')
        seller = vals.get('seller_id')
        #instance_obj = vals.get('instance_id')
        instance = vals.get('us_region_instance_id', False)

        if start_date and end_date:
            start_date = datetime.strptime(str(start_date), '%Y-%m-%d %H:%M:%S')
            end_date = datetime.strptime(str(end_date), '%Y-%m-%d %H:%M:%S')
        elif self.inventory_report_last_sync_on:
            start_date = self.inventory_report_last_sync_on
            # start_date = datetime.strptime(str(start_date), '%Y-%m-%d %H:%M:%S')
            end_date = datetime.strptime(str(end_date), '%Y-%m-%d %H:%M:%S')
        else:
            start_date = datetime.now() + timedelta(days=seller.live_inv_adjustment_report_days * -1 or -3)
            start_date = datetime.strptime(str(start_date), '%Y-%m-%d %H:%M:%S')
            date_end = datetime.now()
            end_date = date_end.strftime("%Y-%m-%d %H:%M:%S")
        job = amazon_process_job_log_obj.create({
            'module': 'amazon_ept',
            'type': 'import',
            'active': True,
            'model_id': model_id,
            'res_id': self.id,
            'log_lines': [(0, 0, {'message': 'Auto Live Stock Inventory Report Process '})]
        })
        #if seller.is_another_soft_create_fba_inventory:
        if seller.amazon_program in ('pan_eu','cep') or not seller.is_european_region:
            report_type='_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_'
            inv_report_ids = self.get_live_inventory_report(report_type, inv_report_ids,
                                                            start_date, end_date,
                                                            job, seller,seller.amazon_program, instance)

        else:
            report_type='_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_'
            start_date = (datetime.today().date() - timedelta(days=1)).strftime(
                    '%Y-%m-%d 00:00:00')
            end_date = (datetime.today().date() - timedelta(days=1)).strftime(
                    '%Y-%m-%d 23:59:59')

            inv_report_ids = self.get_live_inventory_report(report_type, inv_report_ids,
                                                            start_date, end_date,
                                                            job, seller, seller.amazon_program, instance)
        if inv_report_ids:
            action = self.env.ref('amazon_ept.action_live_stock_report_ept', False)
            result = action and action.read()[0] or {}

            if len(inv_report_ids) > 1:
                result['domain'] = "[('id','in',[" + ','.join(map(str, inv_report_ids)) + "])]"
            else:
                res = self.env.ref('amazon_ept.amazon_live_stock_report_form_view_ept', False)
                result['views'] = [(res and res.id or False, 'form')]
                result['res_id'] = inv_report_ids and inv_report_ids[0] or False
            return result

    def get_live_inventory_report(self, report_type, inv_report_ids, start_date, end_date, job,
                                  seller,amazon_program, instance_id=False):
        list_of_wrapper = []
        instances = instance_id if instance_id else seller.instance_ids
        merchant_id = seller.merchant_id or False
        auth_token = seller.auth_token or False

        if not seller.is_european_region:
            account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
            dbuuid = self.env['ir.config_parameter'].sudo(
            ).get_param('database.uuid')
            con_start_date, con_end_date = self.report_start_and_end_date_cron(start_date,
                                                                               end_date)

            kwargs = {'merchant_id': merchant_id,
                      'auth_token': auth_token or False,
                      'app_name':'amazon_ept',
                      'account_token':account.account_token,
                      'emipro_api':'get_shipping_or_inventory_report_by_marketplaces',
                      'dbuuid':dbuuid,
                      'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                                seller.country_id.code,
                      'start_date':con_start_date,
                      'end_date':con_end_date,
                      'report_type':report_type,
                      'marketplaceids': instances.mapped('market_place_id')}

            response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs,
                                   timeout=1000)
            if response.get('reason'):
                if self._context.get('is_auto_process'):
                    job.write({'log_lines':[(0, 0, {'message':response.get('reason')})]})
                else:
                    raise Warning(response.get('reason'))
            else:
                list_of_wrapper = response.get('result')
            latest_report = []
            for result in list_of_wrapper:
                report_exist = False
                reports = []
                if not isinstance(result.get('ReportRequestInfo', []), list):
                    reports.append(result.get('ReportRequestInfo', []))
                else:
                    reports = result.get('ReportRequestInfo', [])
                    reports.reverse()

                for report_info in reports:
                    if not latest_report and report_info.get('ReportProcessingStatus', {}).get('value') == '_DONE_':
                        latest_report.append(report_info)
                    elif latest_report and latest_report[0].get('EndDate', {}).get('value') < report_info.get('EndDate', {}).get(
                            'value') and report_info.get('ReportProcessingStatus', {}).get('value') == '_DONE_':
                        latest_report = [report_info]
            for report in latest_report:
                amz_start_date = parser.parse(str(report.get('StartDate', {}).get('value', ''))).astimezone(
                    utc).strftime('%Y-%m-%d %H:%M:%S')
                amz_end_date = parser.parse(str(report.get('EndDate', {}).get('value', ''))).astimezone(utc).strftime(
                    '%Y-%m-%d %H:%M:%S')
                submited_date = parser.parse(str(report.get('SubmittedDate', {}).get('value', ''))).astimezone(
                    utc).strftime(
                    '%Y-%m-%d %H:%M:%S')
                report_id = report.get('GeneratedReportId', {}).get('value', '')
                request_id = report.get('ReportRequestId', {}).get('value', '')
                report_type = report.get('ReportType', {}).get('value', '')
                state = report.get('ReportProcessingStatus', {}).get('value', '')
                report_exist = self.search(
                        ['|', ('report_request_id', '=', request_id),
                         ('report_id', '=', report_id), ('report_type', '=', report_type)])
                if report_exist:
                    report_exist = report_exist[0]
                    inv_report_ids.append(report_exist.id)
                    continue
                vals = {
                    'report_type':report_type,
                    'report_request_id':request_id,
                    'report_id':report_id,
                    'start_date':amz_start_date,
                    'end_date':amz_end_date,
                    'requested_date':submited_date,
                    'state':state,
                    'seller_id': seller.id,
                    'user_id':self._uid,
                }
                if instance_id:
                    vals.update({'amz_instance_id': instances.id})
                inv_report_id = self.create(vals)
                inv_report_ids.append(inv_report_id.id)
        if amazon_program in ('pan_eu','cep','efn','mci','mci+efn'):
            account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
            dbuuid = self.env['ir.config_parameter'].sudo(
            ).get_param('database.uuid')
            con_start_date, con_end_date = self.report_start_and_end_date_cron(start_date, end_date)
            if amazon_program == 'pan_eu' and not instance_id:
                instances = instances.filtered(lambda x: not x.market_place_id == 'A1F83G8C2ARO7P')
            kwargs = {'merchant_id':seller.merchant_id and str(seller.merchant_id) or False,
                      'auth_token':seller.auth_token and str(seller.auth_token) or False,
                      'app_name':'amazon_ept',
                      'account_token':account.account_token,
                      'emipro_api':'get_shipping_or_inventory_report_by_marketplaces',
                      'dbuuid':dbuuid,
                      'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                                seller.country_id.code,
                      'start_date':con_start_date,
                      'end_date':con_end_date,
                      'report_type':report_type,
                      'marketplaceids': instances.mapped('market_place_id')
                      }
            response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
            if response.get('reason'):
                if self._context.get('is_auto_process'):
                    job.write({'log_lines':[(0, 0, {'message':response.get('reason')})]})
                else:
                    raise Warning(response.get('reason'))
            else:
                list_of_wrapper = response.get('result')
            latest_report = []
            for result in list_of_wrapper:
                report_exist = False
                reports = []
                if not isinstance(result.get('ReportRequestInfo', []), list):
                    reports.append(result.get('ReportRequestInfo', []))
                else:
                    reports = result.get('ReportRequestInfo', [])
                    reports.reverse()

                for report_info in reports:
                    if not latest_report and report_info.get('ReportProcessingStatus', {}).get('value') == '_DONE_':
                        latest_report.append(report_info)
                    elif latest_report and latest_report[0].get('EndDate', {}).get('value') < report_info.get('EndDate', {}).get(
                            'value') and report_info.get('ReportProcessingStatus', {}).get('value') == '_DONE_':
                        latest_report = [report_info]
            for report in latest_report:
                amz_start_date = parser.parse(str(report.get('StartDate', {}).get('value', ''))).astimezone(
                    utc).strftime('%Y-%m-%d %H:%M:%S')
                amz_end_date = parser.parse(str(report.get('EndDate', {}).get('value', ''))).astimezone(utc).strftime(
                    '%Y-%m-%d %H:%M:%S')
                submited_date = parser.parse(str(report.get('SubmittedDate', {}).get('value', ''))).astimezone(
                    utc).strftime('%Y-%m-%d %H:%M:%S')
                report_id = report.get('GeneratedReportId', {}).get('value', '')
                request_id = report.get('ReportRequestId', {}).get('value', '')
                report_type = report.get('ReportType', {}).get('value', '')
                state = report.get('ReportProcessingStatus', {}).get('value', '')
                report_exist = self.search(
                    ['|', ('report_request_id', '=', request_id),
                     ('report_id', '=', report_id), ('report_type', '=', report_type)])
                if report_exist:
                    report_exist = report_exist[0]
                    inv_report_ids.append(report_exist.id)
                    continue
                vals = {
                    'report_type': report_type,
                    'report_request_id': request_id,
                    'report_id': report_id,
                    'start_date': amz_start_date,
                    'end_date': amz_end_date,
                    'requested_date': submited_date,
                    'state': state,
                    'seller_id': seller.id,
                    'user_id': self._uid,
                }
                if instance_id:
                    vals.update({'amz_instance_id': instances.id})
                inv_report_id = self.create(vals)
                inv_report_ids.append(inv_report_id.id)
        if inv_report_ids:
            seller.write({'inventory_report_last_sync_on': end_date})
        return inv_report_ids

    def prepare_vals(self, vals):
        inventory_report = self.create(
            {'report_type': vals.get('report_type'),
             'seller_id': vals.get('seller_id'),
             'state': vals.get('state'),
             'amz_instance_id': vals.get('amz_instance_id'),
             'report_date': vals.get('report_date')
             })
        return inventory_report

    def report_start_and_end_date_cron(self, start_date, end_date):
        """
        Prepare start date and end Date for request reports
        :return: start_date and end_date
        """
        # start_date, end_date = self.start_date, self.end_date
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

    @api.model
    def auto_process_amazon_fba_live_stock_report(self, args={}):
        seller_id = args.get('seller_id', False)
        seller = self.env['amazon.seller.ept'].browse(seller_id)
        if seller:
            fba_live_stock_report = self.search([('seller_id', '=', seller.id),
                                                 ('state', 'in', ['_SUBMITTED_', '_IN_PROGRESS_']),
                                                 ])
            fba_live_stock_report.get_report_request_list_via_cron(seller)

            reports = self.search([('seller_id', '=', seller.id),
                                   ('state', 'in', ['_DONE_', '_SUBMITTED_', '_IN_PROGRESS_']),
                                   ('report_id', '!=', False)
                                   ])
            for report in reports:
                if not report.attachment_id:
                    report.get_report()
                report.with_context(is_auto_process=True).process_fba_live_stock_report()
                report.set_fulfillment_channel_sku()
                self._cr.commit()
        return True

    def get_report_request_list_via_cron(self, seller):
        if not seller:
            raise Warning(_('Please select Seller'))

        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo(
        ).get_param('database.uuid')

        request_ids = [report.report_request_id for report in self]
        report_info_records = {report.report_request_id: report for report in self}
        if not request_ids:
            return True

        kwargs = {'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
                  'auth_token': seller.auth_token and str(seller.auth_token) or False,
                  'app_name': 'amazon_ept',
                  'account_token': account.account_token,
                  'emipro_api': 'get_report_request_list_v13',
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                             seller.country_id.code,
                  'request_ids': request_ids, }

        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(response.get('reason'))
        else:
            list_of_wrapper = response.get('result')

        for result in list_of_wrapper:
            self.update_report_history_via_cron(result, report_info_records)

        return True

    @api.model
    def update_report_history_via_cron(self, request_result, report_info_records):
        report_info = request_result.get('ReportInfo', {})
        if isinstance(request_result.get('ReportInfo', []), list):
            report_info = request_result.get('ReportInfo', [])
        else:
            report_info.append(request_result.get('ReportInfo', {}))
        report_request_info = []
        if isinstance(request_result.get('ReportRequestInfo', []), list):
            report_request_info = request_result.get('ReportRequestInfo', [])
        else:
            report_request_info.append(request_result.get('ReportRequestInfo', {}))
        for info in report_request_info:
            request_id = str(info.get('ReportRequestId', {}).get('value', ''))
            report_state = info.get('ReportProcessingStatus', {}).get('value', '_SUBMITTED_')
            report_id = info.get('GeneratedReportId', {}).get('value', False)
            report_record = report_info_records.get(request_id)
            vals = {}
            if report_state:
                vals.update({'state': report_state})
            if report_id:
                vals.update({'report_id': report_id})
            report_record and report_record.write(vals)
        return True

    @api.constrains('start_date', 'end_date')
    def _check_duration(self):
        """
        This Method check date duration,
        :return: This Method return Boolean(True/False)
        """
        if self.start_date and self.end_date < self.start_date:
            raise Warning('Error!\nThe start date must be precede its end date.')
        return True

    """@api.model
    def default_get(self, fields):
      
        res = super(AmazonLiveStockReportEpt, self).default_get(fields)
        if not fields:
            return res
        res.update({'report_type': '_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_'})
        #res.update({'report_type':'_GET_FBA_FULFILLMENT_CURRENT_INVENTORY_DATA_'})

        #res.update({'report_type':'_GET_AFN_INVENTORY_DATA_BY_COUNTRY_'})

        return res"""

    def request_report(self):
        """
        Request _GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_ Report
                from Amazon for specific date range.
        :return: This Method return Boolean(True/False).
        """
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        amazon_instance = self.env['amazon.instance.ept']

        seller, report_type = self.seller_id, self.report_type
        if not seller:
            raise Warning(_('Please select Seller'))


        start_date, end_date = self.report_start_and_end_date()

        if self.amz_instance_id:
            marketplaceids = self.amz_instance_id.mapped('market_place_id')
        else:
            if seller.amazon_program in ('pan_eu', 'cep'):
                instances = amazon_instance.search([('seller_id', '=', seller.id), ('market_place_id', '!=',
                                                                                    'A1F83G8C2ARO7P')])
            else:
                instances = amazon_instance.search([('seller_id', '=', seller.id)])
            marketplaceids = tuple(map(lambda x: x.market_place_id, instances))

        kwargs = {'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
                  'auth_token': seller.auth_token and str(seller.auth_token) or False,
                  'app_name': 'amazon_ept',
                  'account_token': account.account_token,
                  'emipro_api': 'request_report_v13',
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                             seller.country_id.code,
                  'report_type': report_type,
                  'marketplace_ids': marketplaceids,
                  'start_date': start_date,
                  'end_date': end_date,
                  }
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(_(response.get('reason')))
        else:
            result = response.get('result')
            self.update_report_history(result)

        return True

    def report_start_and_end_date(self):
        """
        Prepare start date and end Date for request reports
        :return: start_date and end_date
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

    @api.model
    def update_report_history(self, request_result):
        """
        This Method relocates update Report History in odoo.
        :param request_result: This arguments relocates request result.
        :return: This Method return Boolean(True/False).
        """
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
            self.get_report_request_list()
        vals = {}
        if not self.report_request_id and request_id:
            vals.update({'report_request_id': request_id})
        if report_state:
            vals.update({'state': report_state})
        if report_id:
            vals.update({'report_id': report_id})
        self.write(vals)
        return True

    def get_report_request_list(self):
        """
        This Method relocates get report list from amazon.
        :return: This Method return boolean(True/False).
        """
        self.ensure_one()
        seller = self.seller_id
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
                  'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                             seller.country_id.code,
                  'request_ids': (self.report_request_id,)}

        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(_(response.get('reason')))
        else:
            list_of_wrapper = response.get('result')

        for result in list_of_wrapper:
            self.update_report_history(result)

        return True

    def get_report(self):
        """
        This Method relocates get live inventory report as an attachment in amazon fba live stock report ept form view.
        :return: This Method return boolean(True/False).
        """
        self.ensure_one()
        seller = self.seller_id
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo(
        ).get_param('database.uuid')

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
                  'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                             seller.country_id.code,
                  'report_id': self.report_id,
                  }
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(_(response.get('reason')))
        else:
            result = response.get('result')

        result = result.encode()
        result = base64.b64encode(result)
        file_name = "Fba_Live_report_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'

        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'datas': result,
            'res_model': 'mail.compose.message',
            'type': 'binary'
        })
        self.message_post(body=_("<b>Live Inventory Report Downloaded</b>"),
                          attachment_ids=attachment.ids)
        self.write({'attachment_id': attachment.id})

        return True

    def download_report(self):
        """
        This Method relocates download amazon fba live stock  report.
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

    def process_fba_live_stock_report(self):
        """
        This Method relocates processed fba live stock reports.
        This Method prepare sellable line dict, unsellable line dict and
            generate inventory based on sellable line dict, unsellable line.
        :return:
        """
        self.ensure_one()
        ir_cron_obj = self.env['ir.cron']
        if not self._context.get('is_auto_process', False):
            ir_cron_obj.with_context({'raise_warning': True}).find_running_schedulers(
                'ir_cron_process_fba_live_stock_report_seller_', self.seller_id.id)
        if not self.attachment_id:
            raise Warning(_("There is no any report are attached with this record."))
        imp_file = StringIO(base64.decodebytes(self.attachment_id.datas).decode())
        reader = csv.DictReader(imp_file, delimiter='\t')
        amazon_process_job_log_obj = self.env['common.log.book.ept']
        model_id = self.env['ir.model']._get('amazon.fba.live.stock.report.ept').id
        job = amazon_process_job_log_obj.search(
            [('model_id', '=', model_id),
             ('res_id', '=', self.id)])
        if not job:
            job = amazon_process_job_log_obj.create({
                'module': 'amazon_ept',
                'type': 'import',
                'active': True,
                'model_id': model_id,
                'res_id': self.id,
                'log_lines': [(0, 0, {'message': 'Live Stock Inventory Report Process '})]
            })
        if self.report_type=='_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_':
            sellable_line_dict, unsellable_line_dict = \
                self.fill_dictionary_from_file_by_instance(reader, job)

            if self.amz_instance_id:
                amz_warehouse = self.amz_instance_id.fba_warehouse_id or False
            else:
                fba_warehouse_ids = self.seller_id.amz_warehouse_ids.filtered(
                    lambda l: l.is_fba_warehouse)
                amz_warehouse = fba_warehouse_ids[0] if fba_warehouse_ids else False

            if amz_warehouse:
                self.create_stock_inventory_from_amazon_live_report(sellable_line_dict,
                                                                    unsellable_line_dict,
                                                                    amz_warehouse, self.id,
                                                                    seller=self.seller_id,
                                                                    job=job)  # inv_mismatch_details_sellable_list,inv_mismatch_details_unsellable_list,

        else:
            if self.amazon_program == 'efn' or self.seller_id.amz_fba_us_program == 'narf':
                amz_warehouse = self.amz_instance_id.fba_warehouse_id if self.amz_instance_id else self.seller_id.amz_warehouse_ids
                sellable_line_dict, unsellable_line_dict = self.fill_dict_from_the_file(reader, job)
                if amz_warehouse:
                    self.create_stock_inventory_from_amazon_live_report(sellable_line_dict,
                                                                        unsellable_line_dict,
                                                                        amz_warehouse, self.id,
                                                                        seller=self.seller_id,
                                                                        job=job)  # inv_mismatch_details_sellable_list,inv_mismatch_details_unsellable_list,
                self.write({'state': 'processed'})
            if self.amazon_program in ('mci', 'efn+mci'):
                sellable_line_dict, unsellable_line_dict = self.fill_dict_from_the_file(reader, job)
                amz_warehouse = self.seller_id.amz_warehouse_ids or False
                if amz_warehouse:
                    self.create_stock_inventory_from_amazon_live_report_for_diff_wh(sellable_line_dict,
                                                                        unsellable_line_dict,
                                                                        amz_warehouse, self.id,
                                                                        seller=self.seller_id,
                                                                        job=job)

        self.write({'state':'processed'})
        self.set_fulfillment_channel_sku()


    def fill_dict_from_the_file(self,reader,job):
        amazon_instnace_obj = self.env['amazon.instance.ept']
        amazon_product_obj = self.env['amazon.product.ept']
        product_obj = self.env['product.product']

        sellable_line_dict = {}
        unsellable_line_dict = {}
        instance_ids = amazon_instnace_obj.search([('seller_id', '=', self.seller_id.id)]).ids
        for row in reader:
            seller_sku = row.get('sku')
            dispotion=row.get('detailed-disposition')
            qty=row.get('quantity')
            fulfillment_center = row.get('fulfillment-center-id')
            country =row.get('country')
            if not seller_sku:
                continue
            if self.amz_instance_id:
                domain = [('seller_sku', '=', seller_sku),
                          ('instance_id', '=', self.amz_instance_id.id)]
            else:
                domain = [('seller_sku', '=', seller_sku),
                          ('instance_id', 'in', instance_ids)]
            amazon_product = amazon_product_obj.search(domain, limit=1)
            odoo_product = amazon_product.product_id if amazon_product else False
            if not odoo_product:
                odoo_product = product_obj.search([('default_code', '=', seller_sku)], limit=1)
                if not odoo_product:
                    message = "Product not found for seller sku %s" % (seller_sku)
                    job.write({'log_lines': [(0, 0, {'message': message})]})
                    continue

            if self.amazon_program == 'efn' or self.seller_id.amz_fba_us_program == 'narf':
                if dispotion == 'SELLABLE':
                    if sellable_line_dict.get(odoo_product):
                        sellable_line_dict.update({odoo_product:float(sellable_line_dict.get(
                                odoo_product))+float(qty)})
                    else:
                        sellable_line_dict.update(
                                {odoo_product:float(qty)})
                else:
                    if unsellable_line_dict.get(odoo_product):
                        unsellable_line_dict.update({odoo_product:float(unsellable_line_dict.get(
                                odoo_product))+float(qty)})
                    else:
                        unsellable_line_dict.update({odoo_product:float(qty)})
            if self.amazon_program in ('mci'+'efn+mci'):
                if not country:
                    continue
                if dispotion == 'SELLABLE':
                    warehouse=False
                    warehouse = self.seller_id.amz_warehouse_ids.filtered(lambda
                                                                  r:r.partner_id.country_id.code==country)
                    if not warehouse:
                        amazon_fulfillment_center = self.env['amazon.fulfillment.center'].search([(
                            'center_code','=',fulfillment_center),('seller_id','=',
                                                                   self.seller_id.id)])
                        if amazon_fulfillment_center:
                            warehouse=amazon_fulfillment_center.warehouse_id
                    if not warehouse:
                        continue
                    warehouse=warehouse.id
                    if sellable_line_dict.get((odoo_product,warehouse)):
                        sellable_line_dict.update({(odoo_product,warehouse):float(sellable_line_dict.get(
                                (odoo_product,warehouse))) + float(qty)})
                    else:
                        sellable_line_dict.update({(odoo_product,warehouse):float(qty)})
                else:
                    if unsellable_line_dict.get((odoo_product,warehouse)):
                        unsellable_line_dict.update({(odoo_product,warehouse):float(
                        unsellable_line_dict.get((odoo_product,warehouse)))+float(qty)})

                    else:
                        unsellable_line_dict.update({(odoo_product,warehouse):float(qty)})

        return sellable_line_dict, unsellable_line_dict

    def fill_dictionary_from_file_by_instance(self, reader, job):
        """
        This method is used to prepare sellable product qty dict and unsellable product qty dict
        as per the instance selected in report.
        This qty will be passed to create stock inventory adjustment report.
        :param reader: This Arguments relocates report of amazon fba live inventory data.
        :param job: This Arguments relocates job log of amazon fba live inventory.
        :return: This Method prepare and return sellable line dict, unsellable line dict.
        """
        amazon_instnace_obj = self.env['amazon.instance.ept']
        amazon_product_obj = self.env['amazon.product.ept']

        sellable_line_dict = {}
        unsellable_line_dict = {}
        instance_ids = amazon_instnace_obj.search([('seller_id', '=', self.seller_id.id)]).ids
        for row in reader:
            seller_sku = row.get('sku') or row.get('seller-sku')
            afn_listing = row.get('afn-listing-exists')
            odoo_product = False
            if afn_listing == '':
                continue
            if not seller_sku:
                continue
            if self.amz_instance_id:
                domain = [('seller_sku', '=', seller_sku),
                          ('instance_id', '=', self.amz_instance_id.id)]
            else:
                domain = [('seller_sku', '=', seller_sku),
                          ('instance_id', 'in', instance_ids)]

            amazon_product = amazon_product_obj.search(domain, limit=1)
            if not amazon_product:
                product_asin = row.get('asin')
                if self.amz_instance_id:
                    domain = [('product_asin', '=', product_asin),
                              ('instance_id', '=', self.amz_instance_id.id)]
                else:
                    domain = [('product_asin', '=', product_asin),
                              ('instance_id', 'in', instance_ids)]
                amazon_product = amazon_product_obj.search(domain, limit=1)
                if not amazon_product:
                    message = "Product not found for seller sku %s" % (seller_sku)
                    job.write({'log_lines': [(0, 0, {'message': message})]})
                    continue

            if amazon_product:
                odoo_product = amazon_product.product_id
                sellable_qty = sellable_line_dict.get(odoo_product, 0.0)
                if self.seller_id.amz_is_reserved_qty_included_inventory_report:
                    sellable_line_dict.update(
                        {odoo_product: sellable_qty + float(row.get('afn-fulfillable-quantity', 0.0)) + float(
                            row.get('afn-reserved-quantity', 0.0))})
                else:
                    sellable_line_dict.update(
                        {odoo_product: sellable_qty + float(row.get('afn-fulfillable-quantity', 0.0))})

                unsellable_qty = unsellable_line_dict.get(odoo_product, 0.0)
                unsellable_line_dict.update(
                    {odoo_product: unsellable_qty + float(row.get('afn-unsellable-quantity', 0.0))})
        return sellable_line_dict, unsellable_line_dict

    def create_fba_live_stock_report_with_diff(self,line_dict, location_ids, inventory_name,
                                     inventory_report_id,
                                      amazon_company,job,unsellable_location_id=False):
        inventory_line_list = []
        product_ids = []
        sellable_products = []
        if unsellable_location_id:
            prod_qty=0
            for product, product_qty in line_dict.items():
                prod=product[0]
                country=product[1]
                prod_qty=prod_qty+product_qty
            amazon_warehouse_location=unsellable_location_id.id
            theoretical_qty_dict = self._get_theoretical_qty(prod, prod_qty,
                                                             amazon_warehouse_location)

            for product_line in theoretical_qty_dict:
                inventory_line_list.append((0, 0, product_line))
                product_ids.append(product_line['product_id'])
        else:
            for product, product_qty in line_dict.items():
                prod=product[0]
                warehouse_id=product[1]
                #if prod.id in sellable_products:
                    #continue
                #else:

                #if amazon_warehouse:
                warehouse=self.env['stock.warehouse'].browse(warehouse_id)
                amazon_warehouse_location = warehouse.lot_stock_id.id
                #sellable_products.append(prod.id)
                if not amazon_warehouse_location:
                    continue
                theoretical_qty_dict = self._get_theoretical_qty(prod, product_qty,
                                                                 amazon_warehouse_location)

                for product_line in theoretical_qty_dict:
                    inventory_line_list.append((0, 0, product_line))
                    product_ids.append(product_line['product_id'])

        return {
            'name':inventory_name,
            'fba_live_stock_report_id':inventory_report_id,
            'location_ids':[(6, 0, location_ids or False)],
            'date':time.strftime("%Y-%m-%d %H:%M:%S"),
            'company_id':amazon_company,
            'line_ids':inventory_line_list,
            'product_ids':[(6, 0, product_ids)]
        }

    def create_fba_live_stock_report(self, line_dict, location_ids, inventory_name,
                                     inventory_report_id,
                                     amazon_warehouse_location, amazon_company):

        """
        This Method relocates prepare inventory dictionary.
        :param line_dict: This Arguments relocates sellable line dict, unsellable line dict.
        :param amz_warehouse_ids: This Arguments relocates amazon warehouse ids list.
        :param inventory_name: This Arguments relocates inventory name.
        :param inventory_report_id: This Arguments relocates inventory report id.
        :param amazon_warehouse_location: This Arguments relocates amazon warehouse location.o
        :param amazon_company: This Arguments relocates amazon company based on amazon warehouse.
        :return: This Method prepare and return inventory dictionary.
        """
        inventory_line_list = []
        product_ids = []
        sellable_products = []
        for product, product_qty in line_dict.items():
            if product.id in sellable_products:
                continue
            sellable_products.append(product.id)
            theoretical_qty_dict = self._get_theoretical_qty(product, product_qty,
                                                             amazon_warehouse_location)

            for product_line in theoretical_qty_dict:
                inventory_line_list.append((0, 0, product_line))
                product_ids.append(product_line['product_id'])

        return {
            'name': inventory_name,
            'fba_live_stock_report_id': inventory_report_id,
            'location_ids': [(6, 0, location_ids or False)],
            'date': time.strftime("%Y-%m-%d %H:%M:%S"),
            'company_id': amazon_company,
            'line_ids': inventory_line_list,
            'product_ids': [(6, 0, product_ids)]
        }

    def start_inventory(self, inventory, seller, job):
        """
        This Method relocates start inventory and done inventory.
        :param inventory: This Arguments relocates created inventory object.
        :param seller: This Arguments relocates fba report seller.
        :param job: This Arguments relocates job log of amazon fba live inventory.
        """
        if inventory:
            try:
                inventory.action_start()
                if seller.validate_stock_inventory_for_report:
                    inventory._action_done()
            except Exception as exception:
                message = 'Error found while creating inventory %s.' % (str(exception))
                job.write({'log_lines': [(0, 0, {'message': message})]})

    def create_stock_inventory_from_amazon_live_report_for_diff_wh(self,sellable_line_dict,
                                                       unsellable_line_dict, amz_warehouse,
                                                       inventory_report_id, seller=False,
                                                       job=''):
        amazon_live_stock_report_obj = self.env['amazon.fba.live.stock.report.ept']
        stock_inventory = self.env['stock.inventory']
        inventory_report = amazon_live_stock_report_obj.browse(inventory_report_id)
        amazon_company=amz_warehouse[0].company_id.id or False
        if sellable_line_dict:
            name = inventory_report.name or "INV-HIST"
            inventory_name = 'Sellable_%s' % name
            location_ids = amz_warehouse.mapped('lot_stock_id').ids
            inventory_vals = self.create_fba_live_stock_report_with_diff(sellable_line_dict,
                                                                    location_ids,
                                                               inventory_name,
                                                               inventory_report_id,
                                                               amazon_company,job,
                                                            )
            inventory = stock_inventory.create(inventory_vals)
            self.start_inventory(inventory, seller, job)

        unsellable_location_id=self.seller_id.amz_warehouse_ids.mapped('unsellable_location_id')
        if not unsellable_location_id:
            if not unsellable_location_id:
                message = 'unsellable location not found for seller %s.' % (self.seller_id.name)
                job.write({'log_lines':[(0, 0, {'message':message})]})
        else:
            if unsellable_line_dict:
                name = inventory_report.name or "INV-HIST"
                unsellable_inventory_name = 'Unsellable_%s' % name
                #location_ids = amz_warehouse.mapped('lot_stock_id').ids
                location_ids = amz_warehouse.mapped('unsellable_location_id').ids

                unsellable_inventory_vals = self.create_fba_live_stock_report_with_diff(unsellable_line_dict,
                                                                              location_ids,
                                                                              unsellable_inventory_name,
                                                                              inventory_report_id,
                                                                              amazon_company,job,
                                                                              unsellable_location_id=unsellable_location_id)
                unsellable_inventory = stock_inventory.create(unsellable_inventory_vals)
                self.start_inventory(unsellable_inventory, seller, job)

        if not job:
            job.unlink()
        else:
            message = 'Inventory adjustment process has been completed open log to view products which are not processed due to any reason.'
            job.write({'log_lines': [(0, 0, {'message': message})]})
        return True

    def create_stock_inventory_from_amazon_live_report(self, sellable_line_dict,
                                                       unsellable_line_dict, amz_warehouse,
                                                       inventory_report_id, seller=False,
                                                       job=''):
        """
        This Method relocates create stock inventory from amazon live report.
        This Method prepare inventory dictionary and create inventory.
        :param sellable_line_dict: This Arguments relocates sellable line dict.
        :param unsellable_line_dict: This Arguments relocates unsellable line dict.
        :param amz_warehouse:  This Arguments relocates amazon warehouse based on seller.
        :param inventory_report_id: This Arguments relocates inventory report id.
        :param seller: This Arguments relocates fba report seller.
        :param job: This Arguments relocates job log of amazon fba live inventory.
        :return: This Method return boolean (True/False).
        """
        amazon_live_stock_report_obj = self.env['amazon.fba.live.stock.report.ept']
        stock_inventory = self.env['stock.inventory']
        inventory_report = amazon_live_stock_report_obj.browse(inventory_report_id)
        amazon_company = amz_warehouse.company_id and amz_warehouse.company_id.id or False

        if sellable_line_dict:
            name = inventory_report.name or "INV-HIST"
            inventory_name = 'Sellable_%s' % name
            location_ids = amz_warehouse.lot_stock_id.ids
            amazon_warehouse_location = amz_warehouse.lot_stock_id.id
            inventory_vals = self.create_fba_live_stock_report(sellable_line_dict, location_ids, inventory_name,
                                                               inventory_report_id, amazon_warehouse_location,
                                                               amazon_company)
            inventory = stock_inventory.create(inventory_vals)
            self.start_inventory(inventory, seller, job)

        if not amz_warehouse.unsellable_location_id:
            message = 'unsellable location not found for warehouse %s.' % (amz_warehouse.name)
            job.write({'log_lines': [(0, 0, {'message': message})]})
        else:
            if unsellable_line_dict:
                name = inventory_report.name or "INV-HIST"
                unsellable_inventory_name = 'Unsellable_%s' % name

                amz_warehouse_ids = amz_warehouse.unsellable_location_id.ids
                amazon_warehouse_location = amz_warehouse.unsellable_location_id.id
                unsellable_inventory_vals = self.create_fba_live_stock_report(unsellable_line_dict, amz_warehouse_ids,
                                                                              unsellable_inventory_name,
                                                                              inventory_report_id,
                                                                              amazon_warehouse_location, amazon_company)
                unsellable_inventory = stock_inventory.create(unsellable_inventory_vals)
                self.start_inventory(unsellable_inventory, seller, job)
        if not job:
            job.unlink()
        else:
            message = 'Inventory adjustment process has been completed open log to view products which are not processed due to any reason.'
            job.write({'log_lines': [(0, 0, {'message': message})]})
        return True

    def _get_theoretical_qty(self, product, file_qty, location):
        """
        This Method relocates get theoretical qty based on product,file_qty and location.
        :param product: This Arguments relocates product of amazon.
        :param file_qty: This Arguments relocates file quantity of amazon.
        :param location: This Arguments relocates location of amazon.
        :return: This Method return theoretical inventory line.
        """
        location_obj = self.env['stock.location']
        locations = location_obj.search([('id', 'child_of', [location])])
        domain = ' location_id in %s and product_id = %s'
        args = (tuple(locations.ids), (product.id,))
        vals = []
        flag = True
        self._cr.execute('''
           SELECT product_id, sum(quantity) as product_qty, location_id, lot_id as prod_lot_id, package_id, owner_id as partner_id
           FROM stock_quant WHERE''' + domain + '''
           GROUP BY product_id, location_id, lot_id, package_id, partner_id''', args)

        for product_line in self._cr.dictfetchall():
            for key, value in product_line.items():
                if not value:
                    product_line[key] = False
            product_line['inventory_id'] = self.id
            product_line['theoretical_qty'] = product_line['product_qty']
            if flag:
                product_line['product_qty'] = file_qty
                flag = False
            else:
                product_line['product_qty'] = 0.0
            if product_line['product_id']:
                product_line['product_uom_id'] = product.uom_id.id
            vals.append(product_line)

        if not vals:
            if file_qty > 0.0:
                vals.append({'product_id': product.id,
                             'inventory_id': self.id,
                             'theoretical_qty': 0.0,
                             'location_id': location,
                             'product_qty': file_qty,
                             'product_uom_id': product.uom_id.id,
                             })

        return vals

    def set_fulfillment_channel_sku(self):
        """
        This Method relocates set fulfillment channel sku.
        :return: This Method return boolean(True/False).
        """
        self.ensure_one()
        if not self.attachment_id:
            raise Warning(_("There is no any report are attached with this record."))
        amazon_product_ept_obj = self.env['amazon.product.ept']
        imp_file = StringIO(base64.decodebytes(self.attachment_id.datas).decode())
        reader = csv.DictReader(imp_file, delimiter='\t')
        for row in reader:
            seller_sku = row.get('sku', False)
            fulfillment_channel_sku = row.get('fnsku', False)

            amazon_product = amazon_product_ept_obj.search(
                [('seller_sku', '=', seller_sku), ('fulfillment_by', '=', 'FBA')])
            for product in amazon_product:
                if not product.fulfillment_channel_sku:
                    product.update({'fulfillment_channel_sku': fulfillment_channel_sku})
        return True
