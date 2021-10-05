from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta

class GlobalCronConfiguration(models.TransientModel):
    _name = "global.cron.configuration"
    _description = "Amazon Global Cron Configuration"

    def _get_amazon_seller(self):
        return self.env.context.get('amz_seller_id', False)

    def _get_amazon_selling(self):
        return self.env.context.get('amazon_selling', False)

    amz_seller_id = fields.Many2one(
        'amazon.seller.ept', string='Amazon Seller', default=_get_amazon_seller, readonly=True)
    amazon_selling = fields.Selection([('FBA', 'FBA'),
                                       ('FBM', 'FBM'),
                                       ('Both', 'FBA & FBM')],
                                      'Amazon Selling', default=_get_amazon_selling, readonly=True)
    # Global settlement report
    amz_settlement_report_auto_create = fields.Boolean("Auto Request Settlement Report ?",
                                                       default=False)
    amz_settlement_report_create_next_execution = fields.Datetime(
        'Settlement Report Create Next Execution', help='Next execution time')
    amz_settlement_report_create_interval_number = fields.Integer(
        'Settlement Report Create Interval Number', help="Repeat every x.")
    amz_settlement_report_create_interval_type = fields.Selection([('hours', 'Hours'), ('days', 'Days')],
                                                                  'Settlement Report Create Interval Unit')
    amz_settlement_report_create_user_id = fields.Many2one("res.users",
                                                           string="Settlement Report Create User")

    # Global Auto send invoice mail
    amz_auto_send_invoice = fields.Boolean(
        "Auto Send Invoice Via Email ?", default=False)
    amz_auto_send_invoice_next_execution = fields.Datetime('Auto Send Invoice Next Execution',
                                                           help='Next execution time')
    amz_auto_send_invoice_interval_number = fields.Integer('Auto Send Invoice Interval Number',
                                                           help="Repeat every x.")
    amz_auto_send_invoice_process_interval_type = fields.Selection([('hours', 'Hours'),
                                                                    ('days', 'Days')],
                                                                   'Auto Send Invoice Interval Unit')
    amz_auto_send_invoice_user_id = fields.Many2one("res.users", string="Auto Send Invoice User")
    amz_instance_invoice_tmpl_id = fields.Many2one("mail.template", string="Invoice Template",
                                                   default=False)
    # auto send refund
    amz_auto_send_refund = fields.Boolean("Auto Send Refund Via Email ?", default=False)
    amz_auto_send_refund_next_execution = fields.Datetime('Auto Send Refund Next Execution',
                                                          help='Next execution time')
    amz_auto_send_refund_interval_number = fields.Integer('Auto Send Refund Interval Number',
                                                          help="Repeat every x.")
    amz_auto_send_refund_process_interval_type = fields.Selection([('hours', 'Hours'), ('days', 'Days')],
                                                                  'Auto Send Refund Process Interval Unit')
    amz_auto_send_refund_user_id = fields.Many2one(
        "res.users", string="Auto Send Refund User")
    amz_instance_refund_tmpl_id = fields.Many2one("mail.template", string="Refund Template",
                                                  default=False)


    # Rating Report
    amz_auto_import_rating_report = fields.Boolean(
        string='Auto Request Rating Report ?')
    amz_rating_report_import_next_execution = fields.Datetime(
        'Import Rating Report Next Execution', help='Next execution time')
    amz_rating_report_import_interval_number = fields.Integer(
        'Import Rating Report Interval Number', help="Repeat every x.")
    amz_rating_report_import_interval_type = fields.Selection([('hours', 'Hours'), ('days', 'Days')],
                                                              'Import Rating Report Interval Unit')
    amz_rating_report_import_user_id = fields.Many2one("res.users",
                                                       string="Import Rating Report User")

    # Process and download Rating report
    amz_auto_process_rating_report = fields.Boolean(
        string='Download and Process Rating?')
    amz_rating_process_report_next_execution = fields.Datetime(
        'Process Rating Next Execution', help='Next execution time')
    amz_rating_process_report_interval_number = fields.Integer(
        'Process Rating Interval Number', help="Repeat every x.")
    amz_rating_process_report_interval_type = fields.Selection([('hours', 'Hours'),
                                                                ('days', 'Days')],
                                                               'Process Rating Interval Unit')
    amz_rating_process_report_user_id = fields.Many2one("res.users",
                                                        string="Process Rating User")

    #vcs tax report import
    amz_auto_import_vcs_tax_report = fields.Boolean(string='Auto Request VCS Tax Report?')
    amz_vcs_report_import_next_execution = fields.Datetime( 'Import VCS Tax Report Next Execution',
                                                            help='Next execution time')
    amz_vcs_report_import_interval_number = fields.Integer(
            'Import VCS Tax Report Interval Number', help="Repeat every x.")
    amz_vcs_report_import_interval_type = fields.Selection([('hours', 'Hours'), ('days', 'Days')],
                                                            'Import VCS Tax Report Interval Unit')
    amz_vcs_report_import_user_id = fields.Many2one("res.users",
                                                     string="Import VCS Tax Report User")

    #vcs tax report process
    amz_auto_process_vcs_tax_report = fields.Boolean(
            string='Download and Process VCS Tax Report ?')
    amz_vcs_report_process_next_execution = fields.Datetime(
            'Process VCS Tax Report Next Execution', help='Next execution time')
    amz_vcs_report_process_interval_number = fields.Integer(
            'Process VCS Tax Report Interval Number', help="Repeat every x.")
    amz_vcs_report_process_interval_type = fields.Selection([('hours', 'Hours'), ('days', 'Days')],
                                                             'Process VCS Tax Report Interval Unit')
    amz_vcs_report_process_user_id = fields.Many2one("res.users",
                                                      string="Process VCS Tax Report User")

    #Invoice Upload Process
    amz_auto_upload_tax_invoices = fields.Boolean(
        string='Auto Upload invoices from Odoo to Amazon ?')
    amz_auto_upload_tax_invoices_next_execution = fields.Datetime(
        'Upload Invoices Next Execution', help='Next execution time')
    amz_auto_upload_tax_invoices_interval_number = fields.Integer(
        'Upload Invoices Interval Number', help="Repeat every x.")
    amz_auto_upload_tax_invoices_interval_type = fields.Selection([('hours', 'Hours'), ('days', 'Days')],
                                                            'Upload Invoices Time Interval Unit')
    amz_auto_upload_tax_invoices_user_id = fields.Many2one("res.users",
                                                     string="Amazon Invoices Upload User")

    @api.onchange("amz_seller_id")
    def onchange_amazon_seller_id(self):
        amz_seller = self.amz_seller_id
        self.update_amz_settlement_report_cron_field(amz_seller)
        self.update_amz_invoice_cron_field(amz_seller)
        self.update_amz_refund_via_cron_field(amz_seller)
        self.update_amz_rating_report_cron_field(amz_seller)
        self.update_amz_return_report_process_cron_field(amz_seller)
        self.update_amz_vcs_report_cron_field(amz_seller)
        self.update_amz_vcs_report_process_cron_field(amz_seller)
        self.update_invoices_to_amazon_cron_field(amz_seller)

    def update_invoices_to_amazon_cron_field(self, amz_seller):
        try:
            amz_invoice_upload_cron_exist = amz_seller and self.env.ref(
                    'amazon_ept.ir_cron_auto_process_upload_invoices_to_amazon_seller_%d'%(amz_seller.id))
        except:
            amz_invoice_upload_cron_exist = False
        if amz_invoice_upload_cron_exist:
            self.amz_auto_upload_tax_invoices = amz_invoice_upload_cron_exist.active or False
            self.amz_auto_upload_tax_invoices_interval_number = amz_invoice_upload_cron_exist.interval_number or False
            self.amz_auto_upload_tax_invoices_interval_type = amz_invoice_upload_cron_exist.interval_type or False
            self.amz_auto_upload_tax_invoices_next_execution = amz_invoice_upload_cron_exist.nextcall or False
            self.amz_auto_upload_tax_invoices_user_id = amz_invoice_upload_cron_exist.user_id.id or False

    def update_amz_vcs_report_process_cron_field(self,amz_seller):
        try:
            amz_vcs_cron_process_exist = amz_seller and self.env.ref(
                    'amazon_ept.ir_cron_auto_process_vcs_tax_report_seller_%d'%(amz_seller.id))
        except:
            amz_vcs_cron_process_exist = False
        if amz_vcs_cron_process_exist:
            self.amz_auto_process_vcs_tax_report = amz_vcs_cron_process_exist.active or False
            self.amz_vcs_report_process_interval_number = amz_vcs_cron_process_exist.interval_number or False
            self.amz_vcs_report_process_interval_type = amz_vcs_cron_process_exist.interval_type or False
            self.amz_vcs_report_process_next_execution = amz_vcs_cron_process_exist.nextcall or False
            self.amz_vcs_report_process_user_id = amz_vcs_cron_process_exist.user_id.id or False

    def update_amz_vcs_report_cron_field(self,amz_seller):
        try:
            amz_vcs_cron_exist = amz_seller and self.env.ref(
                    'amazon_ept.ir_cron_auto_import_vcs_tax_report_seller_%d'%(amz_seller.id))
        except:
            amz_vcs_cron_exist = False
        if amz_vcs_cron_exist:
            self.amz_auto_import_vcs_tax_report = amz_vcs_cron_exist.active or False
            self.amz_vcs_report_import_interval_number = amz_vcs_cron_exist.interval_number or False
            self.amz_vcs_report_import_interval_type = amz_vcs_cron_exist.interval_type or False
            self.amz_vcs_report_import_next_execution = amz_vcs_cron_exist.nextcall or False
            self.amz_vcs_report_import_user_id = amz_vcs_cron_exist.user_id.id or False

    def update_amz_settlement_report_cron_field(self, amz_seller):
        try:
            amz_settlement_cron_exist = amz_seller and self.env.ref(
                'amazon_ept.ir_cron_auto_import_settlement_report_seller_%d' % (amz_seller.id))
        except:
            amz_settlement_cron_exist = False
        if amz_settlement_cron_exist:
            self.amz_settlement_report_auto_create = amz_settlement_cron_exist.active or False
            self.amz_settlement_report_create_interval_number = amz_settlement_cron_exist.interval_number or False
            self.amz_settlement_report_create_interval_type = amz_settlement_cron_exist.interval_type or False
            self.amz_settlement_report_create_next_execution = amz_settlement_cron_exist.nextcall or False
            self.amz_settlement_report_create_user_id = amz_settlement_cron_exist.user_id.id or False

    def update_amz_invoice_cron_field(self, amz_seller):
        try:
            amz_invoice_cron_exist = amz_seller and self.env.ref(
                'amazon_ept.ir_cron_send_amazon_invoice_via_email_seller_%d' % (amz_seller.id))
        except:
            amz_invoice_cron_exist = False
        if amz_invoice_cron_exist:
            self.amz_auto_send_invoice = amz_invoice_cron_exist.active or False
            self.amz_auto_send_invoice_interval_number = amz_invoice_cron_exist.interval_number or False
            self.amz_auto_send_invoice_process_interval_type = amz_invoice_cron_exist.interval_type or False
            self.amz_auto_send_invoice_next_execution = amz_invoice_cron_exist.nextcall or False
            self.amz_auto_send_invoice_user_id = amz_invoice_cron_exist.user_id.id or False

    def update_amz_refund_via_cron_field(self, amz_seller):
        try:
            amz_refund_cron_exist = amz_seller and self.env.ref(
                'amazon_ept.ir_cron_send_amazon_refund_via_email_seller_%d' % (amz_seller.id))
        except:
            amz_refund_cron_exist = False
        if amz_refund_cron_exist:
            self.amz_auto_send_refund = amz_refund_cron_exist.active or False
            self.amz_auto_send_refund_interval_number = amz_refund_cron_exist.interval_number or False
            self.amz_auto_send_refund_process_interval_type = amz_refund_cron_exist.interval_type or False
            self.amz_auto_send_refund_next_execution = amz_refund_cron_exist.nextcall or False
            self.amz_auto_send_refund_user_id = amz_refund_cron_exist.user_id.id or False

    def update_amz_rating_report_cron_field(self, amz_seller):
        try:
            amz_check_rating_report_cron_exist = amz_seller and self.env.ref(
                'amazon_ept.ir_cron_rating_request_report_seller_%d' % (amz_seller.id))
        except:
            amz_check_rating_report_cron_exist = False
        if amz_check_rating_report_cron_exist:
            self.amz_auto_import_rating_report = amz_check_rating_report_cron_exist.active or False
            self.amz_rating_report_import_interval_number = amz_check_rating_report_cron_exist.interval_number or False
            self.amz_rating_report_import_interval_type = amz_check_rating_report_cron_exist.interval_type or False
            self.amz_rating_report_import_next_execution = amz_check_rating_report_cron_exist.nextcall or False
            self.amz_rating_report_import_user_id = amz_check_rating_report_cron_exist.user_id.id or False

    def update_amz_return_report_process_cron_field(self, amz_seller):
        try:
            amz_check_rating_process_cron_exist = amz_seller and self.env.ref(
                'amazon_ept.ir_cron_process_rating_request_report_seller_%d' % (amz_seller.id))
        except:
            amz_check_rating_process_cron_exist = False
        if amz_check_rating_process_cron_exist:
            self.amz_auto_process_rating_report = amz_check_rating_process_cron_exist.active or False
            self.amz_rating_process_report_interval_number = amz_check_rating_process_cron_exist.interval_number or False
            self.amz_rating_process_report_interval_type = amz_check_rating_process_cron_exist.interval_type or False
            self.amz_rating_process_report_next_execution = amz_check_rating_process_cron_exist.nextcall or False
            self.amz_rating_process_report_user_id = amz_check_rating_process_cron_exist.user_id.id or False

    def save_cron_configuration(self):
        amazon_seller = self.amz_seller_id
        vals = {}
        self.setup_amz_settlement_report_create_cron(amazon_seller)
        self.send_amz_invoice_via_email_seller_wise(amazon_seller)
        self.send_amz_refund_via_email_seller_wise(amazon_seller)
        self.setup_auto_import_rating_report(amazon_seller)
        self.setup_auto_process_rating_report(amazon_seller)
        self.setup_amz_vcs_tax_report_create_cron(amazon_seller)
        self.setup_amz_vcs_tax_report_process_cron(amazon_seller)
        self.setup_invoice_upload_to_amz_process_cron(amazon_seller)

        vals['settlement_report_auto_create'] = self.amz_settlement_report_auto_create or False
        vals['auto_send_invoice'] = self.amz_auto_send_invoice or False
        vals['auto_send_refund'] = self.amz_auto_send_refund or False
        vals['auto_import_rating_report'] = self.amz_auto_import_rating_report or False
        vals['auto_process_rating_report'] = self.amz_auto_process_rating_report or False
        vals['amz_auto_import_vcs_tax_report'] = self.amz_auto_import_vcs_tax_report or False
        vals['amz_auto_process_vcs_tax_report'] = self.amz_auto_process_vcs_tax_report or False
        vals['amz_auto_upload_tax_invoices'] = self.amz_auto_upload_tax_invoices or False
        amazon_seller.write(vals)

    def setup_invoice_upload_to_amz_process_cron(self, seller):
        if self.amz_auto_upload_tax_invoices:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_auto_process_upload_invoices_to_amazon_seller_%d' % (
                    seller.id), raise_if_not_found=False)
            vals = {'active': True,
                    'interval_number': self.amz_auto_upload_tax_invoices_interval_number,
                    'interval_type': self.amz_auto_upload_tax_invoices_interval_type,
                    'nextcall': self.amz_auto_upload_tax_invoices_next_execution,
                    'user_id': self.amz_auto_upload_tax_invoices_user_id.id,
                    'code': "model.upload_odoo_invoice_to_amazon({'seller_id':%d})" % (seller.id),
                    'amazon_seller_cron_id': seller.id}

            if cron_exist:
                cron_exist.write(vals)
            else:
                cron_exist = self.env.ref('amazon_ept.ir_cron_auto_invoices_upload_to_amazon',
                                          raise_if_not_found=False)
                if not cron_exist:
                    raise Warning(
                        'Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')

                name = 'FBA&FBM-' + seller.name + ' : Invoices Upload to Amazon'
                vals.update({'name': name})
                new_cron = cron_exist.copy(default=vals)
                self.env['ir.model.data'].create({'module': 'amazon_ept',
                                                  'name': 'ir_cron_auto_process_upload_invoices_to_amazon_seller_%d' % (
                                                      seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id': new_cron.id,
                                                  'noupdate': True
                                                  })
        else:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_auto_process_upload_invoices_to_amazon_seller_%d' % (
                    seller.id), raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def setup_amz_vcs_tax_report_process_cron(self,seller):
        if self.amz_auto_process_vcs_tax_report:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_auto_process_vcs_tax_report_seller_%d' % (
                    seller.id),
                raise_if_not_found=False)
            vals = {'active': True,
                    'interval_number': self.amz_vcs_report_process_interval_number,
                    'interval_type': self.amz_vcs_report_process_interval_type,
                    'nextcall': self.amz_vcs_report_process_next_execution,
                    'user_id': self.amz_vcs_report_process_user_id.id,
                    'code': "model.auto_process_vcs_tax_report({'seller_id':%d})" % (seller.id),
                    'amazon_seller_cron_id': seller.id}

            if cron_exist:
                cron_exist.write(vals)
            else:
                cron_exist = self.env.ref('amazon_ept.ir_cron_auto_process_vcs_tax_report',
                                          raise_if_not_found=False)
                if not cron_exist:
                    raise Warning(
                        'Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')

                name = 'FBA&FBM-' + seller.name + ' : Process VCS Tax Report'
                vals.update({'name': name})
                new_cron = cron_exist.copy(default=vals)
                self.env['ir.model.data'].create({'module': 'amazon_ept',
                                                  'name': 'ir_cron_auto_process_vcs_tax_report_seller_%d' % (
                                                      seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id': new_cron.id,
                                                  'noupdate': True
                                                  })
        else:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_auto_process_vcs_tax_report_seller_%d' % (
                    seller.id),
                raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def setup_amz_vcs_tax_report_create_cron(self,seller):
        if self.amz_auto_import_vcs_tax_report:
            cron_exist = self.env.ref(
                    'amazon_ept.ir_cron_auto_import_vcs_tax_report_seller_%d' % (
                        seller.id),
                    raise_if_not_found=False)
            vals = {'active':True,
                    'interval_number':self.amz_vcs_report_import_interval_number,
                    'interval_type':self.amz_vcs_report_import_interval_type,
                    'nextcall':self.amz_vcs_report_import_next_execution,
                    'user_id':self.amz_vcs_report_import_user_id.id,
                    'code':"model.auto_import_vcs_tax_report({'seller_id':%d, 'is_auto_process': True})" % (
                        seller.id), 'amazon_seller_cron_id':seller.id}

            if cron_exist:
                cron_exist.write(vals)
            else:
                cron_exist = self.env.ref('amazon_ept.ir_cron_auto_import_vcs_tax_report',
                                          raise_if_not_found=False)
                if not cron_exist:
                    raise Warning(
                        'Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')

                name = 'FBA&FBM-' + seller.name + ' : Import VCS Tax report Report'
                vals.update({'name': name})
                new_cron = cron_exist.copy(default=vals)
                self.env['ir.model.data'].create({'module': 'amazon_ept',
                                                  'name': 'ir_cron_auto_import_vcs_tax_report_seller_%d' % (
                                                      seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id': new_cron.id,
                                                  'noupdate': True
                                                  })
        else:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_auto_import_vcs_tax_report_seller_%d' % (
                    seller.id),
                raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def setup_amz_settlement_report_create_cron(self, seller):
        if self.amz_settlement_report_auto_create:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_auto_import_settlement_report_seller_%d' % (
                    seller.id),
                raise_if_not_found=False)
            vals = {'active': True,
                    'interval_number': self.amz_settlement_report_create_interval_number,
                    'interval_type': self.amz_settlement_report_create_interval_type,
                    'nextcall': self.amz_settlement_report_create_next_execution,
                    'user_id': self.amz_settlement_report_create_user_id.id,
                    'code': "model.auto_import_settlement_report({'seller_id':%d, 'is_auto_process': True})" % (
                        seller.id), 'amazon_seller_cron_id': seller.id}

            if cron_exist:
                cron_exist.write(vals)
            else:
                cron_exist = self.env.ref('amazon_ept.ir_cron_auto_import_settlement_report',
                                          raise_if_not_found=False)
                if not cron_exist:
                    raise Warning(
                        'Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')

                name = 'FBM-' + seller.name + ' : Import Settlement Report'
                vals.update({'name': name})
                new_cron = cron_exist.copy(default=vals)
                self.env['ir.model.data'].create({'module': 'amazon_ept',
                                                  'name': 'ir_cron_auto_import_settlement_report_seller_%d' % (
                                                      seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id': new_cron.id,
                                                  'noupdate': True
                                                  })
        else:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_auto_import_settlement_report_seller_%d' % (
                    seller.id),
                raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        self.setup_amz_settlement_report_process_cron(seller)
        return True

    def setup_amz_settlement_report_process_cron(self, seller):
        if self.amz_settlement_report_auto_create:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_auto_process_settlement_report_seller_%d' % (
                    seller.id),
                raise_if_not_found=False)
            process_next_execution = self.amz_settlement_report_create_next_execution + relativedelta(minutes=10)
            vals = {'active': True,
                    'interval_number': self.amz_settlement_report_create_interval_number,
                    'interval_type': self.amz_settlement_report_create_interval_type,
                    'nextcall': process_next_execution,
                    'user_id': self.amz_settlement_report_create_user_id.id,
                    'code': "model.auto_process_settlement_report({'seller_id':%d})" % (seller.id),
                    'amazon_seller_cron_id': seller.id}

            if cron_exist:
                cron_exist.write(vals)
            else:
                cron_exist = self.env.ref('amazon_ept.ir_cron_auto_process_settlement_report',
                                          raise_if_not_found=False)
                if not cron_exist:
                    raise Warning(
                        'Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')

                name = 'FBM-' + seller.name + ' : Process Settlement Report'
                vals.update({'name': name})
                new_cron = cron_exist.copy(default=vals)
                self.env['ir.model.data'].create({'module': 'amazon_ept',
                                                  'name': 'ir_cron_auto_process_settlement_report_seller_%d' % (
                                                      seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id': new_cron.id,
                                                  'noupdate': True
                                                  })
        else:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_auto_process_settlement_report_seller_%d' % (
                    seller.id),
                raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def send_amz_invoice_via_email_seller_wise(self, seller):
        if self.amz_auto_send_invoice:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_send_amazon_invoice_via_email_seller_%d' % (
                    seller.id),
                raise_if_not_found=False)
            vals = {'active': True,
                    'interval_number': self.amz_auto_send_invoice_interval_number,
                    'interval_type': self.amz_auto_send_invoice_process_interval_type,
                    'nextcall': self.amz_auto_send_invoice_next_execution,
                    'user_id': self.amz_auto_send_invoice_user_id.id,
                    'code': "model.send_amazon_invoice_via_email({'seller_id':%d})" % (seller.id),
                    'amazon_seller_cron_id': seller.id
                    }
            if cron_exist:
                cron_exist.write(vals)
            else:
                cron_exist = self.env.ref('amazon_ept.ir_cron_send_amazon_invoice_via_email',
                                          raise_if_not_found=False)
                if not cron_exist:
                    raise Warning(
                        'Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')

                name = 'FBM-' + seller.name + ' : Invoice Send By Email'
                vals.update({'name': name})
                new_cron = cron_exist.copy(default=vals)
                self.env['ir.model.data'].create({'module': 'amazon_ept',
                                                  'name': 'ir_cron_send_amazon_invoice_via_email_seller_%d' % (
                                                      seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id': new_cron.id,
                                                  'noupdate': True
                                                  })
        else:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_send_amazon_invoice_via_email_seller_%d' % (
                    seller.id),
                raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def send_amz_refund_via_email_seller_wise(self, seller):
        if self.amz_auto_send_refund:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_send_amazon_refund_via_email_seller_%d' % (
                    seller.id),
                raise_if_not_found=False)
            vals = {'active': True,
                    'interval_number': self.amz_auto_send_refund_interval_number,
                    'interval_type': self.amz_auto_send_refund_process_interval_type,
                    'nextcall': self.amz_auto_send_refund_next_execution,
                    'user_id': self.amz_auto_send_refund_user_id.id,
                    'code': "model.send_amazon_refund_via_email({'seller_id':%d})" % (seller.id),
                    'amazon_seller_cron_id': seller.id
                    }
            if cron_exist:
                cron_exist.write(vals)
            else:
                cron_exist = self.env.ref('amazon_ept.ir_cron_send_amazon_refund_via_email',
                                          raise_if_not_found=False)
                if not cron_exist:
                    raise Warning(
                        'Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')

                name = 'FBM-' + seller.name + ' : refund Send By Email'
                vals.update({'name': name})
                new_cron = cron_exist.copy(default=vals)
                self.env['ir.model.data'].create({'module': 'amazon_ept',
                                                  'name': 'ir_cron_send_amazon_refund_via_email_seller_%d' % (
                                                      seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id': new_cron.id,
                                                  'noupdate': True
                                                  })
        else:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_send_amazon_refund_via_email_seller_%d' % (
                    seller.id),
                raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def setup_auto_import_rating_report(self, amazon_seller):
        if self.amz_auto_import_rating_report:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_rating_request_report_seller_%d' % (
                    amazon_seller.id),
                raise_if_not_found=False)
            vals = {
                'active': True,
                'interval_number': self.amz_rating_report_import_interval_number,
                'interval_type': self.amz_rating_report_import_interval_type,
                'nextcall': self.amz_rating_report_import_next_execution,
                'user_id': self.amz_rating_report_import_user_id.id,
                'code': "model.auto_import_rating_report({'seller_id':%d, 'is_auto_process': True})" % (
                    amazon_seller.id),
                'amazon_seller_cron_id': amazon_seller.id}
            if cron_exist:
                cron_exist.write(vals)
            else:
                import_order_cron = self.env.ref('amazon_ept.ir_cron_rating_request_report',
                                                 raise_if_not_found=False)
                if not import_order_cron:
                    raise Warning(
                        'Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')

                name = 'FBA&FBM-' + amazon_seller.name + ' : Import Amazon Rating Report'
                vals.update({'name': name})
                new_cron = import_order_cron.copy(default=vals)
                self.env['ir.model.data'].create({'module': 'amazon_ept',
                                                  'name': 'ir_cron_rating_request_report_seller_%d' % (
                                                      amazon_seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id': new_cron.id,
                                                  'noupdate': True
                                                  })

        else:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_rating_request_report_seller_%d' % (
                    amazon_seller.id),
                raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def setup_auto_process_rating_report(self, amazon_seller):
        if self.amz_auto_process_rating_report:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_process_rating_request_report_seller_%d' % (
                    amazon_seller.id),
                raise_if_not_found=False)
            vals = {
                'active': True,
                'interval_number': self.amz_rating_process_report_interval_number,
                'interval_type': self.amz_rating_process_report_interval_type,
                'nextcall': self.amz_rating_process_report_next_execution,
                'user_id': self.amz_rating_process_report_user_id.id,
                'code': "model.auto_process_rating_report({'seller_id':%d, 'is_auto_process': True})" % (
                    amazon_seller.id),
                'amazon_seller_cron_id': amazon_seller.id}
            if cron_exist:
                cron_exist.write(vals)
            else:
                import_order_cron = self.env.ref('amazon_ept.ir_cron_process_rating_request_report',
                                                 raise_if_not_found=False)
                if not import_order_cron:
                    raise Warning(
                        'Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')

                name = 'FBA&FBM-' + amazon_seller.name + ' : Process Amazon Rating Report'
                vals.update({'name': name})
                new_cron = import_order_cron.copy(default=vals)
                self.env['ir.model.data'].create({'module': 'amazon_ept',
                                                  'name': 'ir_cron_process_rating_request_report_seller_%d' % (
                                                      amazon_seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id': new_cron.id,
                                                  'noupdate': True
                                                  })

        else:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_process_rating_request_report_seller_%d' % (
                    amazon_seller.id),
                raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True
