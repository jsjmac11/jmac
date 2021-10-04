
import base64
import csv
import time
from collections import defaultdict
from datetime import datetime, timedelta
from io import StringIO

from odoo import models, fields, api, _
from odoo.exceptions import Warning

from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT

import  logging
_logger = logging.getLogger(__name__)


class SettlementReportEpt(models.Model):
    _name = "settlement.report.ept"
    _order = 'id desc'
    _inherit = ['mail.thread']
    _description = "Settlement Report"

    @api.depends('seller_id')
    def get_company(self):
        for record in self:
            company_id = record.seller_id and record.seller_id.company_id.id or False
            if not company_id:
                company_id = self.env.company.id
            record.company_id = company_id

    def _get_invoiced(self):
        self.invoice_count = len(self.reimbursement_invoice_ids.ids)

    def check_statement_status(self):
        if not self.statement_id.all_lines_reconciled or not self.statement_id.line_ids and self.statement_id.state != 'open':
            is_ready_for_validate = False
        else:
            is_ready_for_validate = True
        self.is_ready_for_validate = is_ready_for_validate

    def _check_fee_exist(self):
        for record in self:
            is_fee = False
            unavailable_amazon_code = []
            state = record.state
            if state in ['imported', 'partially_processed', '_DONE_']:
                amazon_code_list = record.statement_id.line_ids.filtered(
                    lambda x: x.amazon_code != False and not x.journal_entry_ids).mapped(
                    'amazon_code')
                statement_amazon_code = amazon_code_list and list(set(amazon_code_list))
                transaction_amazon_code_list = record.seller_id.transaction_line_ids.filtered(
                    lambda x: x.amazon_code != False).mapped('amazon_code')
                missing_account_id_list = record.seller_id.transaction_line_ids.filtered(lambda l: not l.account_id).mapped('amazon_code')
                transaction_amazon_code = transaction_amazon_code_list and list(set(transaction_amazon_code_list))
                unavailable_amazon_code = [code for code in statement_amazon_code if
                                           code not in transaction_amazon_code or
                                           code in missing_account_id_list]

                if unavailable_amazon_code:
                    is_fee = True
            record.is_fees = is_fee

    name = fields.Char(size=256, string='Name', default='XML Settlement Report')
    attachment_id = fields.Many2one('ir.attachment', string="Attachment")
    statement_id = fields.Many2one('account.bank.statement', string="Bank Statement")
    seller_id = fields.Many2one('amazon.seller.ept', string='Seller', copy=False)
    instance_id = fields.Many2one('amazon.instance.ept', string="Instance")
    currency_id = fields.Many2one('res.currency', string="Currency")
    user_id = fields.Many2one('res.users', string="Requested User")
    company_id = fields.Many2one('res.company', string="Company", copy=False, compute="get_company",
                                 store=True)
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    is_ready_for_validate = fields.Boolean("Is Ready for Validate ?", compute="check_statement_status")
    already_processed_report_id = fields.Many2one("settlement.report.ept",
                                                  string="Already Processed Report")
    reimbursement_invoice_ids = fields.Many2many("account.move",
                                                 'amazon_rembursement_invoice_rel', 'report_id',
                                                 'invoice_id', string="Reimbursement Invoice")
    invoice_count = fields.Integer(string='Invoice Count', compute='_get_invoiced', readonly=True)

    report_id = fields.Char(size=256, string='Report ID')
    report_type = fields.Char(size=256, string='Report Type')
    report_request_id = fields.Char(size=256, string='Report Request ID')
    requested_date = fields.Datetime('Requested Date', default=time.strftime("%Y-%m-%d %H:%M:%S"))
    state = fields.Selection(
        [('draft', 'Draft'), ('_SUBMITTED_', 'SUBMITTED'), ('_IN_PROGRESS_', 'IN_PROGRESS'),
         ('_CANCELLED_', 'CANCELLED'), ('_DONE_', 'DONE'),
         ('_DONE_NO_DATA_', 'DONE_NO_DATA'), ('processed', 'PROCESSED'),
         ('imported', 'Imported'), ('duplicate', 'Duplicate'),
         ('partially_processed', 'Partially Processed'), ('confirm', 'Validated')
         ],
        string='Report Status', default='draft')
    is_fees = fields.Boolean(string="Is Fee", compute='_check_fee_exist', store=False)
    all_lines_reconciled = fields.Boolean(string="Is All Lines Reconciled?",
                                          related="statement_id.all_lines_reconciled",
                                          store=False)

    def list_of_reimbursement_invoices(self):
        invoices = self.reimbursement_invoice_ids
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoices.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def unlink(self):
        """
        Added by Udit
        This method will not delete settlement reports which are in 'processed' state.
        """
        for report in self:
            if report.state == 'processed':
                raise Warning(_('You cannot delete processed report.'))
        return super(SettlementReportEpt, self).unlink()

    def validate_statement(self):
        self.statement_id.check_confirm_bank()
        if self.state != 'confirm':
            self.write({'state': 'confirm'})
        return True

    def get_settlement_refund_dict_ept(self, row, key, product_id, create_or_update_refund_dict):
        """
        Added by twinkalc on 28 sep, 2020,
        @param : row - contain the settlement report vals
        @param : key - key if refund dict.
        @param : product_id - refund dict product
        This method will prepare the refund dict based on that create refund invoice in ERP.
        """
        principal = 0
        tax = 0
        if str(row.get('amount-description', '').lower().find('tax')) != '-1':
            tax = float(row.get('amount').replace(',', '.')) or 0
        else:
            principal = float(row.get('amount').replace(',', '.')) or 0
        amount = [principal, tax]

        if not create_or_update_refund_dict.get(key):
            create_or_update_refund_dict.update({key: {product_id: amount}})
        else:
            existing_amount = create_or_update_refund_dict.get(key).get(
                    product_id, [0.0, 0.0])
            principle = existing_amount[0] + amount[0]
            tax = existing_amount[1] + amount[1]
            amount = [principle, tax]
            create_or_update_refund_dict.get(key).update({product_id: amount})

        return create_or_update_refund_dict

    @api.model
    def remaining_order_refund_lines(self):
        """This function is used to get remaining order lines for reconciliation
            @author: Dimpal added on 15/oct/2019
            :Updated by : Kishan Sorani on date 22-Jul-2021
            :MOD : consider ItemPrice and Promotion lines of order for bank statement
                   line reconciliation for refund invoice
        Case 1 : When sale order is imported at that time sale order is in quotation state,
        so after Importing Settlement report it will receive payment line for that invoice,
            system will not reconcile invoice of those orders, because pending quotation.
        """
        sale_order_obj = self.env['sale.order']
        stock_move_obj = self.env['stock.move']
        amazon_product_obj = self.env['amazon.product.ept']
        partner_obj = self.env['res.partner']


        order_statement_lines = self.statement_id.mapped('line_ids').filtered(
            lambda x: not x.is_refund_line and not x.sale_order_id and not x.amazon_code and not x.journal_entry_ids)
        order_names = order_statement_lines.mapped('name')

        order_name_list = []
        for order_name in order_names:
            order_name_list.append(order_name.split("/")[1])

        ## temporary removed from below line => and not x.sale_order_id
        refund_lines = self.statement_id.mapped('line_ids').filtered(
            lambda x: x.is_refund_line and not x.amazon_code and not x.journal_entry_ids and not x.refund_invoice_id)
        refund_names = refund_lines.mapped('name')
        refund_name_list = []
        for refund_name in refund_names:
            if '/' in refund_name:
                refund_name_list.append(refund_name.split("/")[-1])
            else:
                refund_name_list.append(refund_name.replace('Refund_', ''))

        if not order_names and not refund_names:
            return True

        imp_file = StringIO(base64.b64decode(self.attachment_id.datas).decode())
        content = imp_file.read()
        delimiter = ('\t', csv.Sniffer().sniff(content.splitlines()[0]).delimiter)[bool(content)]
        settlement_reader = csv.DictReader(content.splitlines(), delimiter=delimiter)
        order_dict = {}
        product_dict = {}
        create_or_update_refund_dict = {}
        for row in settlement_reader:
            if row.get('amount-description', '').__contains__('MarketplaceFacilitator') or \
                    row.get('amount-description', '').__contains__('LowValueGoods') or \
                    row.get('amount-type', '') == 'ItemFees':
                continue
            order_ref = row.get('order-id')
            adjustment_id = row.get('adjustment-id')

            if order_ref not in order_name_list and order_ref not in refund_name_list:
                continue
            shipment_id = row.get('shipment-id')
            order_item_code = row.get('order-item-code').lstrip('0')
            posted_date = row.get('posted-date')
            fulfllment_by = row.get('fulfillment-id')
            try:
                try:
                    posted_date = datetime.strptime(posted_date, '%d.%m.%Y')
                except Exception:
                    posted_date = datetime.strptime(posted_date, '%Y/%m/%d')
            except Exception:
                posted_date = datetime.strptime(posted_date, '%Y-%m-%d')

            order_ids = order_dict.get((order_ref, shipment_id, order_item_code))
            if not order_ids:
                if fulfllment_by == 'MFN':
                    amz_order = sale_order_obj.search([('amz_order_reference', '=', order_ref),
                                                       ('amz_fulfillment_by', '=', 'FBM'),
                                                       ('state', '!=', 'cancel')])
                else:
                    stock_move = stock_move_obj.search([('amazon_instance_id', '=', self.instance_id.id),
                                                        ('amazon_order_reference', '=', order_ref),
                                                        ('amazon_order_item_id', '=', order_item_code),
                                                        ('state', '=', 'done')])
                    amz_order = stock_move.mapped('sale_line_id').mapped('order_id')

                    order_ids = tuple(amz_order.ids)
                    order_dict.update({(order_ref, shipment_id, order_item_code): order_ids})
            else:
                amz_order = sale_order_obj.browse(order_ids)  ##[0]
            if not amz_order:
                continue
            partner = partner_obj.with_context(is_amazon_partner=True)._find_accounting_partner(amz_order.mapped('partner_id'))

            if order_ref in order_name_list and amz_order and row.get('transaction-type') == 'Order':
                order_line_name = shipment_id + '/' + order_ref
                order_statement_lines.filtered(lambda l: l.name == order_line_name and not l.sale_order_id).write(
                    {'sale_order_id': amz_order.ids[0]})
            elif order_ref in refund_name_list and amz_order and row.get('transaction-type') == 'Refund':
                product_id = product_dict.get(row.get('sku'))
                if not product_id:
                    amazon_product = amazon_product_obj.search(
                            [('seller_sku', '=', row.get('sku')), ('instance_id', '=', self.instance_id.id)], limit=1)
                    product_id = amazon_product.product_id.id
                    product_dict.update({row.get('sku'): amazon_product.product_id.id})
                key = (order_ref, order_ids, posted_date, fulfllment_by, partner.id, adjustment_id)
                create_or_update_refund_dict = self.get_settlement_refund_dict_ept(row, key,
                                                                                   product_id,
                                                                                   create_or_update_refund_dict)

                adjustment_id = (adjustment_id + '/') if adjustment_id else ''
                ref_name = 'Refund_' + adjustment_id + order_ref
                refund_lines.filtered(lambda l: l.name == ref_name and not l.sale_order_id).write(
                    {'sale_order_id': amz_order.ids[0]})
        create_or_update_refund_dict and self.create_refund_invoices(create_or_update_refund_dict, self.statement_id)
        return True

    def reconcile_reimbursement_lines(self, seller, bank_statement, statement_lines, fees_transaction_list):
        transaction_obj = self.env['amazon.transaction.line.ept']
        bank_statement_line_obj = self.env['account.bank.statement.line']

        reimbursement_invoice_ids = self.reimbursement_invoice_ids
        statement_lines = bank_statement_line_obj.browse(statement_lines)
        for line in statement_lines:
            trans_line_id = fees_transaction_list.get(line.amazon_code)
            trans_line = transaction_obj.browse(trans_line_id)
            date_posted = line.date
            invoice_type = 'out_refund' if line.amount < 0.00 else 'out_invoice'
            reimbursement_invoice_amount = abs(line.amount)
            reimbursement_invoice = reimbursement_invoice_ids.filtered( \
                lambda l: l.state in ['draft', 'posted'] and not l.invoice_payment_state == 'paid' and l.invoice_date == date_posted and l.type == invoice_type)
            if len(reimbursement_invoice) > 1:
                reimbursement_invoice = reimbursement_invoice.filtered(lambda l: round(l.amount_total,10) == round(reimbursement_invoice_amount, 10))
                reimbursement_invoice = reimbursement_invoice[0] if reimbursement_invoice else False
            if not reimbursement_invoice:
                reimbursement_invoice = self.create_amazon_reimbursement_invoice(bank_statement, seller, date_posted, invoice_type)
                self.create_amazon_reimbursement_invoice_line(seller, reimbursement_invoice, line.name, reimbursement_invoice_amount, trans_line)
                self.write({'reimbursement_invoice_ids': [(4, reimbursement_invoice.id)]})
            self.reconcile_reimbursement_invoice(reimbursement_invoice, line, bank_statement)
        return True

    def reconcile_orders(self, statement_lines):
        """This function is used to reconcile bank statement which is generated from settlement report
            @author: Dimpal added on 15/oct/2019
        """
        bank_statement = self.statement_id
        account_payment_obj = self.env['account.payment']
        statement_line_obj = self.env['account.bank.statement.line']
        for statement_line_id in statement_lines:
            statement_line = statement_line_obj.browse(statement_line_id)
            order = statement_line.sale_order_id
            try:
                self.check_or_create_invoice_if_not_exist(order)
            except:
                continue
            invoices = order.invoice_ids.filtered(
                lambda record: record.type == 'out_invoice' and record.state in ['posted'])
            if not invoices:
                continue
            if len(invoices) >1:
                reconcile_invoice = invoices.filtered(lambda l: round(l.amount_total,10) == round(statement_line.amount, 10))
                reconcile_invoice = reconcile_invoice.line_ids.filtered(
                        lambda l: l.account_id.user_type_id.type == 'receivable' and not l.reconciled).mapped('move_id')
                if reconcile_invoice:
                    invoices = reconcile_invoice[0]

            paid_invoices = invoices.filtered(lambda record: record.invoice_payment_state == 'paid')
            unpaid_invoices = invoices.filtered(lambda record: record.invoice_payment_state == 'not_paid')

            mv_line_dicts = []
            move_line_total_amount = 0.0
            currency_ids = []
            paid_move_lines = False

            if paid_invoices:
                payment_id = account_payment_obj.search([('invoice_ids', 'in', paid_invoices.ids)])
                paid_move_lines = payment_id.mapped('move_line_ids').filtered(lambda x: x.debit != 0.0)
                for moveline in paid_move_lines:
                    amount = moveline.debit - moveline.credit
                    amount_currency = 0.0
                    if moveline.amount_currency:
                        currency, amount_currency = self.convert_move_amount_currency(
                            bank_statement, moveline, amount, statement_line.date)
                        if currency:
                            currency_ids.append(currency)

                    if amount_currency:
                        amount = amount_currency

                    move_line_total_amount += amount
            if unpaid_invoices:
                move_lines = unpaid_invoices.mapped('line_ids').filtered(
                    lambda l: l.account_id.user_type_id.type == 'receivable' and not l.reconciled)
                for moveline in move_lines:
                    amount = moveline.debit - moveline.credit
                    amount_currency = 0.0
                    if moveline.amount_currency:
                        currency, amount_currency = self.convert_move_amount_currency(
                            bank_statement, moveline, amount, statement_line.date)
                        if currency:
                            currency_ids.append(currency)

                    if amount_currency:
                        amount = amount_currency
                    mv_line_dicts.append({
                        'credit': abs(amount) if amount > 0.0 else 0.0,
                        'name': moveline.move_id.name,
                        'move_line': moveline,
                        'debit': abs(amount) if amount < 0.0 else 0.0
                    })
                    move_line_total_amount += amount

            if round(statement_line.amount, 10) == round(move_line_total_amount, 10) and (
                    not statement_line.currency_id or statement_line.currency_id.id == bank_statement.currency_id.id):
                if currency_ids:
                    currency_ids = list(set(currency_ids))
                    if len(currency_ids) == 1:
                        vals = {'amount_currency': move_line_total_amount}
                        statement_currency = statement_line.journal_id.currency_id and \
                                             statement_line.journal_id.currency_id.id or \
                                             statement_line.company_id.currency_id and \
                                             statement_line.company_id.currency_id.id
                        if not currency_ids[0] == statement_currency:
                            vals.update({'currency_id': currency_ids[0]})
                        statement_line.write(vals)
                statement_line.process_reconciliation(mv_line_dicts, payment_aml_rec=paid_move_lines)

    def reconcile_refunds(self, statement_lines):
        bank_statement = self.statement_id
        account_payment_obj = self.env['account.payment']
        statement_line_obj = self.env['account.bank.statement.line']
        for statement_line_id in statement_lines:
            move_line_total_amount = 0.0
            mv_line_dicts = []
            currency_ids = []
            paid_move_lines = None
            statement_line = statement_line_obj.browse(statement_line_id)
            if statement_line.refund_invoice_id.invoice_payment_state == 'paid':
                payment_id = account_payment_obj.search([('invoice_ids', 'in', statement_line.refund_invoice_id.ids)])
                paid_move_lines = payment_id.mapped('move_line_ids').filtered(lambda x: x.credit != 0.0)
                for moveline in paid_move_lines:
                    amount = moveline.debit - moveline.credit
                    amount_currency = 0.0
                    if moveline.amount_currency:
                        currency, amount_currency = self.convert_move_amount_currency(
                            bank_statement, moveline, amount, statement_line.date)
                        if currency:
                            currency_ids.append(currency)
                    if amount_currency:
                        amount = amount_currency
                    move_line_total_amount += amount
            else:
                unpaid_move_lines = statement_line.refund_invoice_id.mapped('line_ids').filtered(
                    lambda l: l.account_id.user_type_id.type == 'receivable' and not l.reconciled)
                for moveline in unpaid_move_lines:
                    amount = moveline.debit - moveline.credit
                    amount_currency = 0.0
                    if moveline.amount_currency:
                        currency, amount_currency = self.convert_move_amount_currency(
                            bank_statement, moveline, amount, statement_line.date)
                        if currency:
                            currency_ids.append(currency)
                    if amount_currency:
                        amount = amount_currency
                    mv_line_dicts.append({
                        'credit': abs(amount) if amount > 0.0 else 0.0,
                        'name': moveline.move_id.name,
                        'move_line': moveline,
                        'debit': abs(amount) if amount < 0.0 else 0.0
                    })
                    move_line_total_amount += amount
            if round(statement_line.amount, 10) == round(move_line_total_amount, 10) and (
                    not statement_line.currency_id or statement_line.currency_id.id == bank_statement.currency_id.id):
                if currency_ids:
                    currency_ids = list(set(currency_ids))
                    if len(currency_ids) == 1:
                        vals = {'amount_currency': move_line_total_amount}
                        statement_currency = statement_line.journal_id.currency_id and \
                                             statement_line.journal_id.currency_id.id or \
                                             statement_line.company_id.currency_id and \
                                             statement_line.company_id.currency_id.id
                        if not currency_ids[0] == statement_currency:
                            vals.update({'currency_id': currency_ids[0]})
                        statement_line.write(vals)
                statement_line.process_reconciliation(mv_line_dicts, payment_aml_rec=paid_move_lines)
        return True

    def reconcile_remaining_transactions(self):
        """This function is used to reconcile remaining transaction of settlement report
            @author: Dimpal added on 15/oct/2019
        """
        statement_line_obj = self.env['account.bank.statement.line']
        transaction_obj = self.env['amazon.transaction.line.ept']
        account_statement = self.statement_id
        if account_statement.state != 'open':
            return True
        self.remaining_order_refund_lines()
        self._cr.commit()
        fees_transaction_list = {}
        trans_line_ids = transaction_obj.search([('seller_id', '=', self.seller_id.id)])
        for trans_line_id in trans_line_ids:
            transaction_type_id = trans_line_id.transaction_type_id
            if trans_line_id.id in fees_transaction_list:
                fees_transaction_list[transaction_type_id.amazon_code].append(
                    trans_line_id.id)
            else:
                fees_transaction_list.update({transaction_type_id.amazon_code: [trans_line_id.id]})
        statement_lines = self.statement_id.line_ids.filtered(lambda x: not x.journal_entry_ids
                                                                        and x.amazon_code != False).ids
        rei_lines = []
        for x in range(0, len(statement_lines), 10):
            lines = statement_lines[x:x + 10]
            for line_id in lines:
                mv_line_data_list = []
                move_line_list = []
                line = statement_line_obj.browse(line_id)
                trans_line_id = fees_transaction_list.get(line.amazon_code)
                if not trans_line_id:
                    continue
                trans_line = transaction_obj.browse(trans_line_id)
                if trans_line and trans_line[0].transaction_type_id.is_reimbursement:
                    rei_lines.append(line.id)
                    continue
                account_id = trans_line and trans_line[0].account_id.id or self.statement_id.journal_id.default_credit_account_id.id
                if not account_id:
                    continue
                tax_id = trans_line[0].tax_id if trans_line else False
                if tax_id:
                    mv_line_dict = tax_id.json_friendly_compute_all(line.amount, line.currency_id.id)
                    mv_line_tax_list =  mv_line_dict.get('taxes', [])
                    mv_line_tag_ids = mv_line_dict.get('base_tags', [])

                    if mv_line_tax_list:
                        mv_line_data_list.append({'move_line': {'name': line.name, 'amount': line.amount, 'account_id': account_id, 'tag_ids': mv_line_tag_ids}})

                    for move_tax_data in mv_line_tax_list:
                        vat_mv_line = line.name + ' ' + move_tax_data.get('name', 'VAT')
                        vat_amount = move_tax_data.get('amount', 0.0)
                        vat_account_id = move_tax_data.get('account_id', False)
                        vt_line_tag_ids = move_tax_data.get('tag_ids', [])
                        if not vat_account_id:
                            mv_line_data_list =[]
                            break
                        mv_line_data_list.append({'vat_line': {'name': vat_mv_line, 'amount': vat_amount, 'account_id': vat_account_id, 'tag_ids': vt_line_tag_ids}})

                    for line_dict in mv_line_data_list:
                        for key, data_dict in line_dict.items():
                            if data_dict.get('amount') == 0.0:
                                continue
                            move_line_list.append({'name': data_dict.get('name'),
                                                   'account_id': data_dict.get('account_id'),
                                                   'debit': data_dict.get('amount') < 0 and -data_dict.get('amount') or 0.0,
                                                   'credit': data_dict.get('amount') > 0 and data_dict.get('amount') or 0.0,
                                                   'tax_ids': [[6, None, [] if key == 'vat_line' else tax_id.ids]],
                                                   'tag_ids': [[6, None, data_dict.get('tag_ids')]]})
                else:
                    move_line_list.append({
                        'name': line.name,
                        'account_id': account_id,
                        'debit': line.amount < 0 and -line.amount or 0.0,
                        'credit': line.amount > 0 and line.amount or 0.0,
                    })
                line.process_reconciliation(new_aml_dicts=move_line_list)
            self._cr.commit()

        for x in range(0, len(rei_lines), 10):
            lines = rei_lines[x:x + 10]
            self.reconcile_reimbursement_lines(self.seller_id, self.statement_id, lines, fees_transaction_list)
            self._cr.commit()

        statement_lines = self.statement_id.line_ids.filtered(lambda x: x.journal_entry_ids.ids == []
                                                                        and x.amazon_code == False and not x.is_refund_line and x.sale_order_id)
        for x in range(0, len(statement_lines), 10):
            lines = statement_lines[x:x + 10]
            self.reconcile_orders(lines.ids)
            self._cr.commit()

        statement_lines = self.statement_id.line_ids.filtered(lambda x: x.journal_entry_ids.ids == []
                                                                        and x.amazon_code == False and x.is_refund_line and x.refund_invoice_id)
        for x in range(0, len(statement_lines), 10):
            lines = statement_lines[x:x + 10]
            self.reconcile_refunds(lines.ids)
            self._cr.commit()

        if not self.statement_id.line_ids.filtered(lambda x: x.journal_entry_ids.ids == []):
            self.write({'state': 'processed'})
        else:
            self.statement_id.line_ids.filtered(lambda x: x.journal_entry_ids.ids != [])
            if self.state != 'partially_processed':
                self.write({'state': 'partially_processed'})
        return True

    def get_report(self):
        """
        Added by Udit
        This method will get settlement report's attachment data from amazon and attach it with it's
        related settlement report.
        """
        self.ensure_one()
        seller = self.seller_id
        if not seller:
            raise Warning('Please select seller')

        if not self.report_id:
            return True

        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')

        kwargs = self.sudo().prepare_merchant_report_dict(seller, account, dbuuid,
                                                          emipro_api='amazon_settlement_report_v13')
        kwargs.update({'report_id': self.report_id, 'name': self.name})

        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(response.get('reason'))
        else:
            self.prepare_settlement_report_attachments_csv(response)
        return True

    def prepare_settlement_report_attachments_csv(self, response):
        data = response.get('data')
        if data:
            reader = csv.DictReader(data.splitlines(), delimiter='\t')
            start_date = ''
            end_date = ''
            currency_id = False
            marketplace = ''
            for row in reader:
                if marketplace:
                    break
                if not start_date:
                    start_date = self.format_amz_settlement_report_date(row.get('settlement-start-date'))
                if not end_date:
                    end_date = self.format_amz_settlement_report_date(row.get('settlement-end-date'))
                if not currency_id:
                    currency_id = self.env['res.currency'].search([('name', '=', row.get('currency'))])
                if not marketplace:
                    marketplace = row.get('marketplace-name')

            self.prepare_attachments(data, marketplace, start_date, end_date, currency_id)
        return True

    @staticmethod
    def format_amz_settlement_report_date(date):
        """
        Usage of this method is to properly format settlement report dates.
        date will be in this format 21.01.2021 03:09:54 UTC OR 2021-01-21 03:09:53 UTC
        :param date: DateTime in String UTC format
        :return: datetime()
        """
        try:
            try:
                formatted_date = datetime.strptime(date, '%d.%m.%Y %H:%M:%S UTC')
            except Exception:
                formatted_date = datetime.strptime(date, '%Y/%m/%d %H:%M:%S UTC')
        except Exception:
            formatted_date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S UTC')
        return formatted_date

    def prepare_attachments(self, data, marketplace, start_date, end_date, currency_rec):
        """
        Added by Udit
        :param data: Attachment data.
        :param marketplace: Market place.
        :param start_date: Selected start date in specific format.
        :param end_date: Selected end date in specific format.
        :param currency_rec: Currency from amazon.
        :return: This method will create attachments, attach it to settlement report's record and create a log an note.
        """
        instance = self.env['amazon.marketplace.ept'].find_instance(self.seller_id, marketplace)

        data = data.encode('utf-8')
        result = base64.b64encode(data)
        file_name = "Settlement_report_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'datas': result,
            'res_model': 'mail.compose.message',
        })
        self.message_post(body=_("<b>Settlement Report Downloaded</b>"),
                          attachment_ids=attachment.ids)
        self.write({'attachment_id': attachment.id,
                    'start_date': start_date and start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date and end_date.strftime('%Y-%m-%d'),
                    'currency_id': currency_rec and currency_rec[0].id or False,
                    'instance_id': instance and instance[0].id or False
                    })

    def download_report(self):
        """
        Added by Udit
        This method will help you to download settlement report.
        """
        self.ensure_one()
        if self.attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' % (self.attachment_id.id),
                'target': 'self',
            }
        return True

    def prepare_merchant_report_dict(self, seller, account, dbuuid, emipro_api):
        """
        Added by Udit
        :return: This method will prepare merchant' informational dictionary which will
                 passed to  amazon api calling method.
        """

        return {
            'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
            'auth_token': seller.auth_token and str(seller.auth_token) or False,
            'app_name': 'amazon_ept',
            'account_token': account.account_token,
            'emipro_api': emipro_api,
            'dbuuid': dbuuid,
            'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                       seller.country_id.code,
        }

    def process_settlement_report_file(self):
        """
        Process work for fetch data from settlement report,create bank statement and
        statement line
        @author: Deval Jagad (15/11/2019)
        """
        self.ensure_one()
        ir_cron_obj = self.env['ir.cron']
        if not self._context.get('is_auto_process', False):
            ir_cron_obj.with_context({'raise_warning': True}).find_running_schedulers(
                'ir_cron_auto_process_settlement_report_seller_', self.seller_id.id)
        self.check_instance_configuration_and_attachment_file()
        imp_file = StringIO(base64.b64decode(self.attachment_id.datas).decode())
        content = imp_file.read()
        delimiter = ('\t', csv.Sniffer().sniff(content.splitlines()[0]).delimiter)[bool(content)]
        settlement_reader = csv.DictReader(content.splitlines(), delimiter=delimiter)
        journal = self.instance_id.settlement_report_journal_id
        seller = self.seller_id
        bank_statement = False
        settlement_id = ''
        order_list_item_price = {}
        order_list_item_fees = {}

        refund_list_item_price = {}
        create_or_update_refund_dict = {}
        amazon_product_obj = self.env['amazon.product.ept']
        partner_obj = self.env['res.partner']
        amazon_other_transaction_list = {}
        product_dict = {}
        order_dict = {}
        for row in settlement_reader:
            settlement_id = row.get('settlement-id')
            if not bank_statement:
                bank_statement = self.create_settlement_report_bank_statement(row, journal,
                                                                              settlement_id)
                if not bank_statement:
                    break
            if not row.get('transaction-type'):
                continue
            order_ref = row.get('order-id')
            shipment_id = row.get('shipment-id')
            order_item_code = row.get('order-item-code').lstrip('0')
            posted_date = row.get('posted-date')
            fulfllment_by = row.get('fulfillment-id')
            adjustment_id = row.get('adjustment-id')
            try:
                try:
                    posted_date = datetime.strptime(posted_date, '%d.%m.%Y')
                except Exception:
                    posted_date = datetime.strptime(posted_date, '%Y/%m/%d')
            except Exception:
                posted_date = datetime.strptime(posted_date, '%Y-%m-%d')
            amount = float(row.get('amount').replace(',', '.'))
            if row.get('transaction-type') in ['Order', 'Refund']:
                if row.get('amount-description', '').__contains__('MarketplaceFacilitator') or \
                        row.get('amount-description', '').__contains__('LowValueGoods') or \
                        row.get('amount-type', '') == 'ItemFees':
                    order_list_item_fees = self.prepare_order_list_item_fees_ept( \
                            row, settlement_id, amount, posted_date, order_list_item_fees)
                    continue

                amz_order = self.get_settlement_report_amazon_order_ept(row)    
                order_ids = order_dict.get((order_ref, shipment_id, order_item_code))
                if not order_ids:
                    order_ids = tuple(amz_order.ids)
                    order_dict.update({(order_ref, shipment_id, order_item_code): order_ids})

                partner = partner_obj.with_context(is_amazon_partner=True)._find_accounting_partner(amz_order.mapped('partner_id'))

                if row.get('transaction-type') == 'Order':
                    key = (order_ref, order_ids, posted_date, fulfllment_by, partner.id, shipment_id)
                    if not order_list_item_price.get(key):
                        order_list_item_price.update({key: amount})
                    else:
                        existing_amount = order_list_item_price.get(key, 0.0)
                        order_list_item_price.update({key: existing_amount + amount})

                elif row.get('transaction-type') == 'Refund':
                    product_id = product_dict.get(row.get('sku'))
                    if not product_id:
                        amazon_product = amazon_product_obj.search(
                            [('seller_sku', '=', row.get('sku')), ('instance_id', '=', self.instance_id.id)], limit=1)
                        product_id = amazon_product.product_id.id
                        product_dict.update({row.get('sku'): amazon_product.product_id.id})
                    key = (order_ref, order_ids, posted_date, fulfllment_by, partner.id, adjustment_id)
                    if not refund_list_item_price.get(key):
                        refund_list_item_price.update({key: amount})
                    else:
                        existing_amount = refund_list_item_price.get(key, {})
                        refund_list_item_price.update({key: existing_amount + amount})

                    create_or_update_refund_dict = self.get_settlement_refund_dict_ept(row, key,
                                                                                       product_id,
                                                                                       create_or_update_refund_dict)
            else:
                if row.get('amount-type') in ['other-transaction', 'FBA Inventory Reimbursement']:
                    key = (row.get('amount-type'), posted_date, row.get('amount-description'))
                elif row.get('transaction-type') in ['Order_Retrocharge']:
                    key = (row.get('transaction-type'), posted_date, order_ref)
                else:
                    key = (row.get('amount-type'), posted_date, settlement_id)
                existing_amount = amazon_other_transaction_list.get(key, 0.0)
                amazon_other_transaction_list.update({key: existing_amount + amount})

        if not bank_statement:
            return True

        self.make_amazon_fee_entry(bank_statement, order_list_item_fees)

        if amazon_other_transaction_list:
            self.make_amazon_other_transactions(seller, bank_statement, amazon_other_transaction_list)

        if order_list_item_price:
            self.process_settlement_orders(bank_statement, settlement_id, order_list_item_price) or {}

        if refund_list_item_price:
            self.process_settlement_refunds(bank_statement.id, settlement_id, refund_list_item_price)

        # Create manually refund in ERP whose returned not found in the system
        if create_or_update_refund_dict:
            self.create_refund_invoices(create_or_update_refund_dict, bank_statement)

        self.write({'statement_id': bank_statement.id, 'state': 'imported'})
        return True

    def prepare_order_list_item_fees_ept(self, row, settlement_id, amount, posted_date, order_list_item_fees):
        """
        Added by twinkalc on 03 April, 2021,
        @param : row - contain the settlement report vals
        @param : amount - contain the amount of settlement report.
        @param : order_list_item_fees - list of item fees
        This method will prepare the order item list
        """
        key = (settlement_id, posted_date, row.get('amount-description'))
        if not order_list_item_fees.get(key):
            order_list_item_fees.update({key: amount})
        else:
            existing_amount = order_list_item_fees.get(key)
            order_list_item_fees.update({key : existing_amount + amount})
        return order_list_item_fees

    def get_settlement_report_amazon_order_ept(self, row):
        """
        Added by twinkalc on 28 sep, 2020,
        @param : row - contain the settlement report vals
        This method will get the amazon order.
        """

        sale_order_obj = self.env['sale.order']
        stock_move_obj = self.env['stock.move']

        order_ref = row.get('order-id')
        shipment_id = row.get('shipment-id')
        order_item_code = row.get('order-item-code').lstrip('0')
        fulfillment_by = row.get('fulfillment-id')

        if fulfillment_by == 'MFN':
            amz_order = sale_order_obj.search(
                    [('amz_order_reference', '=', order_ref),
                     ('amz_instance_id', '=', self.instance_id.id),
                     ('amz_fulfillment_by', '=', 'FBM'),
                     ('state', '!=', 'cancel')])
        else:
            domain = [
                ('amazon_instance_id', '=', self.instance_id.id),
                ('amazon_order_reference', '=', order_ref),
                ('amazon_order_item_id', '=', order_item_code),
                ('state', '=', 'done')]
            if shipment_id:
                domain.append(('amazon_shipment_id', '=', shipment_id))
            stock_move = stock_move_obj.search(domain)
            amz_order = stock_move.mapped('sale_line_id').mapped('order_id')
        return amz_order

    def check_instance_configuration_and_attachment_file(self):
        """
        This method check in settlement report attachment exist or not
        Also check configuration of instance, Settlement Report Journal and Currency
        @author: Deval Jagad (18/11/2019)
        """
        if not self.attachment_id:
            raise Warning("There is no any report are attached with this record.")

        if not self.instance_id:
            raise Warning("Please select the Instance in report.")
        if not self.instance_id.settlement_report_journal_id:
            raise Warning(
                "You have not configured Settlement report Journal in Instance. "
                "\nPlease configured it first.")
        currency_id = self.instance_id.settlement_report_journal_id.currency_id.id or \
                      self.seller_id.company_id.currency_id.id or False
        if currency_id != self.currency_id.id:
            raise Warning(
                "Report currency and Currency in Instance Journal are different. "
                "\nMake sure Report currency and Instance Journal currency must be same.")

    def check_settlment_report_exist(self, settlement_id):

        """
        Process check bank statement record and settlement record exist or not
        @:param - settlement_id - unique id from csv file
        @author: Deval Jagad (20/11/2019)
        """

        bank_statement_obj = self.env['account.bank.statement']
        bank_statement_exist = bank_statement_obj.search(
            [('settlement_ref', '=', settlement_id)])
        if bank_statement_exist:
            settlement_exist = self.search([('statement_id', '=', bank_statement_exist.id)])
            if settlement_exist and settlement_exist.id == self.id:
                return bank_statement_exist
            if settlement_exist:
                self.write({'already_processed_report_id': settlement_exist.id,
                            'state': 'duplicate'})
            else:
                self.write({'statement_id': bank_statement_exist.id, 'state': 'processed'})
            return bank_statement_exist
        return False

    def create_settlement_report_bank_statement_line(self, total_amount, settlement_id,
                                                     bank_statement, deposit_date):

        """
        Process create and reconcile 'Total amount' bank statement line
        @:param - total amount - total amount of settlement report
        @:param - settlement_id - unique id from csv file
        @:param - bank_statement - account.bank.statement record create for settlement report
        @:param - deposite_date - deposite date of settlement report
        @author: Deval Jagad (16/11/2019)
        """

        if self.instance_id.ending_balance_account_id and float(total_amount) != 0.0:
            bank_statement_line_obj = self.env['account.bank.statement.line']
            bank_line_vals = {
                'name': self.instance_id.ending_balance_description or "Ending Balance Description",
                'ref': settlement_id,
                'partner_id': False,
                'amount': -float(total_amount),
                'statement_id': bank_statement.id,
                'date': deposit_date,
                'amazon_code': self.instance_id.ending_balance_description or "Ending Balance Description",
                'sequence': 1000
            }
            line = bank_statement_line_obj.create(bank_line_vals)
            mv_dicts = {
                'name': self.instance_id.ending_balance_description or "Ending Balance Description",
                'account_id': self.instance_id.ending_balance_account_id.id,
                'credit': 0.0,
                'debit': 0.0,
            }
            if float(total_amount) < 0.0:
                mv_dicts.update({'credit': -float(total_amount)})
            else:
                mv_dicts.update({'debit': float(total_amount)})
            line.process_reconciliation(new_aml_dicts=[mv_dicts])

    def create_settlement_report_bank_statement(self, row, journal, settlement_id):

        """
        Process first check bank statement exist or not
        If not exist then create bank statement and
        create and reconcile 'Total amount' bank statement line
        @:param - row - whole row of csv file
        @:param - journal - configure in Amazon Marketplace
        @:param - settlement_id - unique id from csv file
        @author: Deval Jagad (16/11/2019)
        """
        bank_statement_obj = self.env['account.bank.statement']
        deposit_date = self.format_amz_settlement_report_date(row.get('deposit-date'))
        total_amount = float(row.get('total-amount').replace(',', '.'))
        start_date = self.start_date
        end_date = self.end_date

        bank_statement_exist = self.check_settlment_report_exist(settlement_id)
        if bank_statement_exist:
            return False

        name = '%s %s to %s ' % (self.instance_id.marketplace_id.name, start_date, end_date)
        vals = {
            'settlement_ref': settlement_id,
            'journal_id': journal.id,
            'date': self.end_date,
            'name': name,
            'balance_end_real': total_amount,
        }
        if self.instance_id.ending_balance_account_id:
            vals.update({'balance_end_real': 0.0})
        bank_statement = bank_statement_obj.create(vals)

        self.create_settlement_report_bank_statement_line(total_amount, settlement_id,
                                                          bank_statement, deposit_date)
        return bank_statement

    @api.model
    def convert_move_amount_currency(self, bank_statement, moveline, amount, date):
        """This function is used to convert currency
            @author: Dimpal added on 14/oct/2019
        """
        amount_currency = 0.0
        if moveline.company_id.currency_id.id != bank_statement.currency_id.id:
            amount_currency = moveline.currency_id._convert(moveline.amount_currency,
                                                            bank_statement.currency_id,
                                                            bank_statement.company_id,
                                                            date)
        elif (moveline.move_id and moveline.move_id.currency_id.id != bank_statement.currency_id.id):
            amount_currency = moveline.move_id.currency_id._convert(amount, bank_statement.currency_id,
                                                                       bank_statement.company_id,
                                                                       date)
        currency = moveline.currency_id.id
        return currency, amount_currency

    @api.model
    def process_settlement_refunds(self, bank_statement_id, settlement_id, refunds):
        bank_statement_line_obj = self.env['account.bank.statement.line']
        refund_invoice_dict = defaultdict(dict)
        for order_key, refund_amount in refunds.items():
            orders = order_key[1]
            amz_order = orders[0] if len(orders) > 1 else orders
            partner_id = order_key[4]
            date_posted = order_key[2]

            if not refund_amount:
                continue

            adjustment_id = (order_key[5] + '/') if order_key[5] else ''
            bank_line_vals = {
                'name': 'Refund_' + adjustment_id + order_key[0],
                'ref': settlement_id,
                'partner_id': partner_id,
                'amount': refund_amount,
                'statement_id': bank_statement_id,
                'date': date_posted,
                'is_refund_line': True,
                'sale_order_id': amz_order
            }
            bank_statement_line_obj.create(bank_line_vals)
        return refund_invoice_dict

    def make_amazon_fee_entry(self, bank_statement, fees_type_dict):
        """
        updated by twinkalc on 3rd april 2021
        @:param bank_statement : bank statement
        @:fees_type_dict : to create amazon fees bank statement lines
        records.
        """
        bank_statement_line_obj = self.env['account.bank.statement.line']
        for key, value in fees_type_dict.items():
            if value != 0:
                name = "%s/%s/%s" % (key[0], key[1], key[2])
                bank_line_vals = {
                    'name': name,
                    'ref': bank_statement.settlement_ref,
                    'amount': value,
                    'statement_id': bank_statement.id,
                    'date': key[1],
                    'amazon_code': key[2]}
                bank_statement_line_obj.create(bank_line_vals)
        return True

    def make_amazon_other_transactions(self, seller, bank_statement, other_transactions):
        transaction_obj = self.env['amazon.transaction.line.ept']
        bank_statement_line_obj = self.env['account.bank.statement.line']
        trans_line_ids = transaction_obj.search([('seller_id', '=', seller.id)])

        fees_transaction_list = {trans_line_id.transaction_type_id.amazon_code: trans_line_id.id for trans_line_id in
                                 trans_line_ids}
        bank_line_vals = []
        for transaction, amount in other_transactions.items():
            if amount == 0.00:
                continue
            trans_type = transaction[0]
            trans_id = transaction[2]
            date_posted = transaction[1]
            trans_type = trans_id if trans_type in ['other-transaction', 'FBA Inventory Reimbursement'] else trans_type
            trans_type_line_id = fees_transaction_list.get(trans_type) or fees_transaction_list.get(trans_id)
            trans_line = trans_type_line_id and transaction_obj.browse(trans_type_line_id)  ##[0]
            name = "%s/%s/%s" % (trans_type, trans_id, date_posted)
            if (not trans_line) or (trans_line and not trans_line.transaction_type_id.is_reimbursement):
                bank_line_vals.append({
                    'name': name,
                    'ref': bank_statement.settlement_ref,
                    'amount': amount,
                    'statement_id': bank_statement.id,
                    'date': date_posted,
                    'amazon_code': trans_type
                })
            elif trans_line.transaction_type_id.is_reimbursement:
                name = "%s/%s/%s" % (trans_type, date_posted, 'Reimbursement')
                self.make_amazon_reimbursement_line_entry(bank_statement, date_posted, trans_type,
                                                          {name: amount})
        bank_statement_line_obj.create(bank_line_vals)
        return True

    def create_amazon_reimbursement_invoice_line(self, seller, reimbursement_invoice,
                                                 name='REVERSAL_REIMBURSEMENT', amount=0.0,
                                                 trans_line=False):
        """This function is used to create reimbursement invoice lines
            @author:  Added by Dimpal on 12/oct/2019
        """
        invoice_line_obj = self.env['account.move.line']
        reimbursement_product = seller.reimbursement_product_id
        tax_id = False
        vals = {'product_id': reimbursement_product.id,
                'name': name,
                'move_id': reimbursement_invoice.id,
                'price_unit': amount,
                'quantity': 1,
                'product_uom_id': reimbursement_product.uom_id.id,
                }
        if self.currency_id.id != self.company_id.currency_id.id:
            vals.update({'currency_id': self.currency_id.id})
        new_record = invoice_line_obj.new(vals)
        new_record._onchange_product_id()
        retval = invoice_line_obj._convert_to_write(
            {name: new_record[name] for name in new_record._cache})
        retval.update({'price_unit': amount})
        account_id = trans_line and trans_line.account_id.id or \
                     self.instance_id.settlement_report_journal_id.default_credit_account_id.id or False
        if account_id:
            retval.update({'account_id': account_id})
        if trans_line and trans_line.tax_id:
            tax_id = trans_line.tax_id.id
        retval.update({'tax_ids': [(6, 0, [tax_id] if tax_id else [])]})
        invoice_line_obj.with_context({'check_move_validity': False}).create(retval)
        return True

    def create_amazon_reimbursement_invoice(self, bank_statement, seller, date_posted, invoice_type):
        """This function is used to create reimbursement invoice
            @author:  Added by Dimpal on 12/oct/2019
        """
        invoice_obj = self.env['account.move']
        partner_id = seller.reimbursement_customer_id.id
        fiscal_position_id = seller.reimbursement_customer_id.property_account_position_id.id
        journal_id = seller.sale_journal_id.id
        invoice_vals = {
            'type': invoice_type,
            'ref': bank_statement.name,
            'partner_id': partner_id,
            'journal_id': journal_id,
            'currency_id': self.currency_id.id,
            'amazon_instance_id': self.instance_id.id,
            'fiscal_position_id': fiscal_position_id,
            'company_id': self.company_id.id,
            'user_id': self._uid or False,
            'invoice_date': date_posted,
            'seller_id': seller.id,
        }
        reimbursement_invoice = invoice_obj.create(invoice_vals)
        return reimbursement_invoice

    def make_amazon_reimbursement_line_entry(self, bank_statement, date_posted, trans_type, fees_type_dict):
        """
        Added by twinkalc on 03 Apr, 2021,
        @:param bank_statement : bank statement
        @:param date_posted : statement line date
        @:fees_type_dict : reimbursement line dict
        records.
        """
        bank_statement_line_obj = self.env['account.bank.statement.line']
        bank_line_vals = [{ 'name': fee_type,
                            'ref': bank_statement.settlement_ref,
                            'amount': amount,
                            'statement_id': bank_statement.id,
                            'date': date_posted,
                            'amazon_code': trans_type} for fee_type, amount in fees_type_dict.items() if amount != 0.00]
        statement_line = bank_statement_line_obj.create(bank_line_vals)
        return statement_line

    def process_settlement_orders(self, bank_statement, settlement_id, orders_list):
        """This function is updated by Dimpal on 10/oct/2019"""
        sale_order_obj = self.env['sale.order']
        bank_statement_line_obj = self.env['account.bank.statement.line']
        for order_key, invoice_total in orders_list.items():
            orders = sale_order_obj.browse(order_key[1])
            if order_key[4] != 'MFN':
                search_orders = orders.filtered(lambda l: round(l.amount_total, 10) == round(invoice_total, 10))
                if search_orders:
                    orders = orders[0]
                if len(orders.ids) > 1:
                    amz_order = orders[0]
                else:
                    amz_order = orders
            else:
                amz_order = orders

            date_posted = order_key[2]
            partner_id = order_key[4]

            if invoice_total != 0.0:
                name = "%s/%s" % (order_key[5], order_key[0])
                bank_line_vals = {
                    'name': name,
                    'ref': settlement_id,
                    'partner_id': partner_id,
                    'amount': invoice_total,
                    'statement_id': bank_statement.id,
                    'date': date_posted,
                    'sale_order_id': amz_order.id
                }
                bank_statement_line_obj.create(bank_line_vals)
        return True

    def check_or_create_invoice_if_not_exist(self, amz_order):
        """
        Check If Invoices are remaining to create OR Partially created OR need to create invoices
        :param amz_order: sale.order()
        :return:
        """
        for order in amz_order:
            # default_fba_partner_id is fetched according to seller wise.
            if order.amz_instance_id.seller_id.def_fba_partner_id.id == order.partner_id.id:
                continue

            order_invoices = order.invoice_ids.filtered(lambda l: l.type == 'out_invoice' and l.state not in ('cancel'))
            if not order_invoices:
                self.create_invoice_if_not_exist(order)

            # Confirm All Draft Invoices in Sale Order.
            for invoice in order.invoice_ids:
                if invoice.state == 'draft' and invoice.type == 'out_invoice':
                    invoice.action_post()
        return True

    @staticmethod
    def create_invoice_if_not_exist(order):
        """
        For FBA Orders Invoices must be as per Shipment Id's, Invoice amount must be same as Shipment on sale order.
        So For FBA Orders, Different Invoices are required and For FBM Orders Normal Odoo workflow will work.
        :param order: sale.order()
        """
        try:
            shipment_ids = {}
            #Order is process from Shipping report then create invoices as per shipment id
            if order.amz_fulfillment_by == 'FBA' and order.amz_shipment_report_id:
                for move in order.order_line.move_ids:
                    if move.amazon_shipment_id in shipment_ids:
                        shipment_ids.get(move.amazon_shipment_id).append(move.amazon_shipment_item_id)
                    else:
                        shipment_ids.update({move.amazon_shipment_id: [move.amazon_shipment_item_id]})
                for shipment, shipment_item in list(shipment_ids.items()):
                    to_invoice = order.order_line.filtered(lambda l: l.qty_to_invoice != 0.0)
                    if to_invoice:
                        #The context will used in prepare invoice vals and create invoice as per shipment id.
                        order.with_context({'shipment_item_ids': shipment_item})._create_invoices()
            else:
                #Used for FBM Orders
                order._create_invoices()
        except Exception as ex:
            _logger.error(ex)

    def reconcile_reimbursement_invoice(self, reimbursement_invoices, reimbursement_line,
                                        bank_statement):
        """This function is used to reconcile reimbursement invoice
            @author: Dimpal added on 14/oct/2019
        """
        move_line_obj = self.env['account.move.line']
        for reimbursement_invoice in reimbursement_invoices:
            if reimbursement_invoice.state == 'draft':
                reimbursement_invoice.with_context({'check_move_validity': False})._onchange_invoice_line_ids()
                reimbursement_invoice.with_context({'check_move_validity': False})._recompute_dynamic_lines(
                    recompute_all_taxes=True)
                reimbursement_invoice.action_post()
        account_move_ids = list(map(lambda x: x.id, reimbursement_invoices))
        move_lines = move_line_obj.search([('move_id', 'in', account_move_ids),
                                           ('account_id.user_type_id.type', '=', 'receivable'),
                                           ('reconciled', '=', False)])
        mv_line_dicts = []
        move_line_total_amount = 0.0
        currency_ids = []
        for moveline in move_lines:
            amount = moveline.debit - moveline.credit
            amount_currency = 0.0
            if moveline.amount_currency:
                currency, amount_currency = self.convert_move_amount_currency(bank_statement,
                                                                              moveline, amount,
                                                                              reimbursement_line.date)
                if currency:
                    currency_ids.append(currency)

            if amount_currency:
                amount = amount_currency
            mv_line_dicts.append({
                'credit': abs(amount) if amount > 0.0 else 0.0,
                'name': moveline.move_id.name,
                'move_line': moveline,
                'debit': abs(amount) if amount < 0.0 else 0.0
            })
            move_line_total_amount += amount

        if round(reimbursement_line.amount, 10) == round(move_line_total_amount, 10) and (
                not reimbursement_line.currency_id or reimbursement_line.currency_id.id == bank_statement.currency_id.id):
            if currency_ids:
                currency_ids = list(set(currency_ids))
                if len(currency_ids) == 1:
                    vals = {'amount_currency': move_line_total_amount}
                    statement_currency = reimbursement_line.journal_id.currency_id and \
                                         reimbursement_line.journal_id.currency_id.id or \
                                         reimbursement_line.company_id.currency_id and \
                                         reimbursement_line.company_id.currency_id.id
                    if not currency_ids[0] == statement_currency:
                        vals.update({'currency_id': currency_ids[0]})
                    reimbursement_line.write(vals)
            reimbursement_line.process_reconciliation(mv_line_dicts)
        return True

    @api.model
    def create_refund_invoices(self, refund_list_item_price, bank_statement):
        obj_invoice_line = self.env['account.move.line']
        sale_order_obj = self.env['sale.order']
        obj_invoice = self.env['account.move']
        statement_line_obj = self.env['account.bank.statement.line']

        for order_key, product_amount in refund_list_item_price.items():
            if not order_key[1]:
                continue
            order = sale_order_obj.browse(order_key[1])
            if len(order.ids) > 1:
                order = order[0]
            date_posted = order_key[2]
            product_ids = list(product_amount.keys())
            refund_exist = order.invoice_ids.filtered(lambda l: l.type == 'out_refund' and l.state not in ('cancel'))
            if refund_exist:
                is_refund_line_ids = statement_line_obj.search([('sale_order_id', '=', order.id),
                                                                ('statement_id', '=', bank_statement.id),
                                                                ('is_refund_line', '=', True)])
                reserved_refund_invoice_ids = is_refund_line_ids.mapped('refund_invoice_id').ids
                refund_exist = refund_exist.filtered(lambda l: l.id not in reserved_refund_invoice_ids)
                refund_exist = refund_exist[0] if refund_exist else False
            if not refund_exist:
                invoices = order.invoice_ids.filtered(lambda l: l.type == 'out_invoice' and l.state == 'posted').mapped(
                    'invoice_line_ids').filtered(lambda l: l.product_id.id in product_ids).mapped('move_id')
                if not invoices:
                    try:
                        self.check_or_create_invoice_if_not_exist(order)
                    except Exception as ex:
                        _logger.error(ex)
                        continue
                    invoices = order.invoice_ids.filtered(lambda l: l.type == 'out_invoice' and l.state !='cancel').mapped(
                        'invoice_line_ids').filtered(lambda l: l.product_id.id in product_ids).mapped('move_id')
                if not invoices:
                    continue
                refund_record = obj_invoice.browse()
                refund_obj = self.env['account.move.reversal']
                refund_process = refund_obj.create({
                    'move_id': invoices.ids[0],
                    'reason': 'Refund Process Amazon Settlement Report'
                })
                refund = refund_process.reverse_moves()
                refund_invoice = refund and refund.get('res_id') and refund_record.browse(refund.get('res_id'))
                refund_invoice.write({'date': date_posted})  # , 'origin': order.name})
                extra_invoice_lines = obj_invoice_line.search(
                    [('move_id', '=', refund_invoice.id), ('product_id', 'not in', product_ids)])
                if extra_invoice_lines:
                    extra_invoice_lines.with_context({'check_move_validity':False}).unlink()
                for product_id, amount in product_amount.items():
                    unit_price = abs(amount[0] + amount[1])
                    taxargs = {}
                    invoice_lines = refund_invoice.invoice_line_ids.filtered(lambda x: x.product_id.id == product_id)
                    exact_line = False
                    if len(invoice_lines.ids) > 1:
                        exact_line = refund_invoice.invoice_line_ids.filtered(lambda x: x.product_id.id == product_id)[
                            0]
                        if order.amz_instance_id.is_use_percent_tax:
                            taxargs = self.get_amz_refund_unit_price_ept(exact_line, amount)
                            unit_price = taxargs.get('price_unit')
                        if exact_line:
                            other_lines = refund_invoice.invoice_line_ids.filtered(
                                lambda x: x.product_id.id == product_id and x.id != exact_line.id)
                            other_lines.with_context({'check_move_validity': False}).unlink()
                            exact_line.with_context({'check_move_validity': False}).write(
                                {'quantity': 1, 'price_unit': unit_price, **taxargs})
                    else:
                        if order.amz_instance_id.is_use_percent_tax:
                            taxargs = self.get_amz_refund_unit_price_ept(invoice_lines, amount)
                            unit_price = taxargs.get('price_unit')
                        invoice_lines.with_context({'check_move_validity': False}).write(
                            {'quantity': 1, 'price_unit': unit_price, **taxargs})

                refund_invoice.with_context({'check_move_validity': False})._onchange_invoice_line_ids()
                refund_invoice.with_context({'check_move_validity': False})._recompute_dynamic_lines(
                    recompute_all_taxes=True)
                refund_invoice.action_post()
            else:
                if refund_exist.state == 'draft':
                    refund_exist.with_context({'check_move_validity': False})._onchange_invoice_line_ids()
                    refund_exist.with_context({'check_move_validity': False})._recompute_dynamic_lines(
                        recompute_all_taxes=True)
                    refund_exist.action_post()
                refund_invoice = refund_exist
            lines = statement_line_obj.search([('sale_order_id', '=', order.id), ('refund_invoice_id', '=', False),
                                               ('statement_id', '=', bank_statement.id), ('is_refund_line', '=', True)])
            lines = lines and lines.filtered(lambda l: round(abs(l.amount), 10) == round(refund_invoice.amount_total, 10))
            lines and lines[0].write({'refund_invoice_id': refund_invoice.id})
        return True

    def get_amz_refund_unit_price_ept(self, invoice_line, amount):
        if invoice_line.tax_ids and not invoice_line.tax_ids.price_include:
            unit_price_ept = abs(amount[0])
        else:
            unit_price_ept = abs(amount[0]) + abs(amount[1])
        tax = abs(amount[1])
        item_tax_percent = (tax * 100) / unit_price_ept if unit_price_ept > 0 else 0.00
        return {'line_tax_amount_percent': item_tax_percent, 'price_unit': unit_price_ept}

    def view_bank_statement(self):
        """This function is used to show generated bank statement from process of settlement report
            @author: Dimpal added on 10/oct/2019
        """
        self.ensure_one()
        action = self.env.ref('account.action_bank_statement_tree', False)
        form_view = self.env.ref('account.view_bank_statement_form', False)
        result = action and action.read()[0] or {}
        result['views'] = [(form_view and form_view.id or False, 'form')]
        result['res_id'] = self.statement_id and self.statement_id.id or False
        return result

    def auto_import_settlement_report(self, args={}):
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env['amazon.seller.ept'].browse(seller_id)
            if not seller:
                return True
            if seller.settlement_report_last_sync_on:
                start_date = seller.settlement_report_last_sync_on
            else:
                today = datetime.now()
                earlier = today - timedelta(days=30)
                start_date = earlier.strftime("%Y-%m-%d %H:%M:%S")
            date_end = datetime.now()
            date_end = date_end.strftime("%Y-%m-%d %H:%M:%S")

            vals = {'report_type': '_GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2_',
                    'name': 'Amazon Settlement Reports',
                    'model_obj': self.env['settlement.report.ept'],
                    'sequence': self.env.ref('amazon_ept.seq_import_settlement_report_job'),
                    'tree_id': self.env.ref('amazon_ept.amazon_settlement_report_tree_view_ept'),
                    'form_id': self.env.ref('amazon_ept.amazon_settlement_report_form_view_ept'),
                    'res_model': 'settlement.report.ept',
                    'start_date': start_date,
                    'end_date': date_end
                    }
            report_wiz_rec = self.env['amazon.process.import.export'].create({
                'seller_id': seller_id,
            })
            report_wiz_rec.get_reports(vals)
        return True

    def auto_process_settlement_report(self, args={}):
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env['amazon.seller.ept'].search([('id', '=', seller_id)])
            if not seller:
                return True
            settlement_reports = self.search([('seller_id', '=', seller.id),
                                              ('state', 'in', ['_DONE_', 'imported']),
                                              ('report_id', '!=', False)
                                              ])
            for report in settlement_reports:
                if report.state == 'imported':
                    report.with_context(is_auto_process=True).reconcile_remaining_transactions()
                else:
                    if not report.attachment_id:
                        report.get_report()
                    if report.instance_id and report.attachment_id:
                        report.with_context(is_auto_process=True).process_settlement_report_file()
                        self._cr.commit()
                        report.with_context(is_auto_process=True).reconcile_remaining_transactions()
        return True

    def configure_statement_missing_fees(self):
        """
        This method return the cancel order in amazon wizard.
        :return: Cancel Order Wizard
        """
        view = self.env.ref('amazon_ept.view_configure_settlement_report_fees_ept')
        context = dict(self._context)
        context.update({'settlement_id': self.id, 'seller_id': self.seller_id.id})

        return {
            'name': _('Settlement Report Missing Configure Fees'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'settlement.report.configure.fees.ept',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context
        }
