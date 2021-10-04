import time
import base64
import logging
from odoo import fields, models, api, _
from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    amazon_instance_id = fields.Many2one("amazon.instance.ept", "Instances")
    seller_id = fields.Many2one("amazon.seller.ept", "Seller")
    reimbursement_id = fields.Char(string="Reimbursement Id")
    amz_fulfillment_by = fields.Selection(
        [('FBA', 'Amazon Fulfillment Network'), ('FBM', 'Merchant Fullfillment Network')],
        string="Fulfillment By", help="Fulfillment Center by Amazon or Merchant")
    amz_sale_order_id = fields.Many2one("sale.order", string="Amazon Sale Order Id")
    feed_id = fields.Many2one("feed.submission.history", string="Feed Submission Id")
    ship_city = fields.Char(string="Ship City")
    ship_postal_code = fields.Char(string="Ship PostCode")
    ship_state_id = fields.Many2one("res.country.state", string='Ship State')
    ship_country_id = fields.Many2one('res.country', string='Ship Country')
    bill_city = fields.Char(string="Bill City")
    bill_postal_code = fields.Char(string="Bill PostCode")
    bill_state_id = fields.Many2one("res.country.state", string='Bill State')
    bill_country_id = fields.Many2one('res.country', string='Bill Country')
    invoice_url = fields.Char(string="Invoice URL")

    @api.model
    def send_amazon_invoice_via_email(self, args={}):
        instance_obj = self.env['amazon.instance.ept']
        seller_obj = self.env['amazon.seller.ept']
        invoice_obj = self.env['account.move']
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = seller_obj.search([('id', '=', seller_id)])
            if not seller:
                return True

            email_template = self.env.ref('account.email_template_edi_invoice', False)
            instances = instance_obj.search([('seller_id', '=', seller.id)])

            for instance in instances:
                if instance.invoice_tmpl_id:
                    email_template = instance.invoice_tmpl_id
                invoices = invoice_obj.search(
                    [('amazon_instance_id', '=', instance.id), ('state', 'in', ['open', 'paid']),
                     ('sent', '=', False), ('type', '=', 'out_invoice')])
                for invoice in invoices:
                    email_template.send_mail(invoice.id)
                    invoice.write({'sent': True})
        return True

    @api.model
    def send_amazon_refund_via_email(self, args={}):
        instance_obj = self.env['amazon.instance.ept']
        seller_obj = self.env['amazon.seller.ept']
        invoice_obj = self.env['account.move']
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = seller_obj.search([('id', '=', seller_id)])
            if not seller:
                return True
            email_template = self.env.ref('account.email_template_edi_invoice', False)
            instances = instance_obj.search([('seller_id', '=', seller.id)])
            for instance in instances:
                if instance.refund_tmpl_id:
                    email_template = instance.refund_tmpl_id
                invoices = invoice_obj.search(
                    [('amazon_instance_id', '=', instance.id), ('state', 'in', ['open', 'paid']),
                     ('sent', '=', False), ('type', '=', 'out_refund')], limit=1)
                for invoice in invoices:
                    email_template.send_mail(invoice.id)
                    invoice.write({'sent': True})
        return True

    @api.model
    def create(self, vals):
        """
        Check invoice_line_ids if False exist in the line then remove that line from list of invoice_line_ids
        this change is only for FBA Orders.
        @author: Keyur Kanani
        :param vals: invoice line dict
        :return:
        """
        if self._context.get('default_type') == 'out_invoice' and self._context.get('shipment_item_ids'):
            new_lines = []
            for inv_lines in vals.get('invoice_line_ids'):
                if inv_lines[2] != False:
                    new_lines.append(inv_lines)
            vals.update({'invoice_line_ids': new_lines})

        partner = self.env['res.partner'].browse(vals.get('partner_id'))
        if partner.is_amz_customer:
            ship_partner = self.env['res.partner'].browse(vals.get('shipping_partner_id'))
            vals.update({
                'ship_city': ship_partner.city or '',
                'ship_postal_code': ship_partner.zip or '',
                'ship_state_id' : ship_partner.state_id.id if ship_partner.state_id else False,
                'ship_country_id': ship_partner.country_id.id if ship_partner.country_id else False,
                'bill_city' : partner.city or '',
                'bill_postal_code' : partner.zip or '',
                'bill_state_id' : partner.state_id.id if partner.state_id else False,
                'bill_country_id': partner.country_id.id if partner.country_id else False
            })
        return super(AccountMove, self).create(vals)

    def upload_odoo_invoice_to_amazon(self, args):
        seller_obj = self.env['amazon.seller.ept']
        feed_submit_obj = self.env['feed.submission.history']
        seller_id = args.get('seller_id', False)
        if not seller_id:
            _logger.info(_("Seller Id not found in Cron Argument, Please Check Cron Configurations."))
            return True
        seller = seller_obj.browse(seller_id)
        if seller.invoice_upload_policy != 'custom':
            _logger.info(_("Please Verify Invoice Upload Policy Configuration, from Seller Configuration Panel."))
            return True
        instances = seller.instance_ids
        if seller.amz_upload_refund_invoice:
            refund_inv = "and type in ('out_invoice', 'out_refund')"
        else:
            refund_inv = "and type = 'out_invoice'"
        after_req = 0.0
        for instance in instances:
            query = "select id from account_move where amazon_instance_id=%s and invoice_payment_state in ('in_payment','paid') and " \
                    "invoice_sent=False %s" % (instance.id, refund_inv)
            self._cr.execute(query)
            invoice_ids = self._cr.fetchall()
            for invoice_id in invoice_ids:
                invoice = self.browse(invoice_id)
                kwargs = invoice._prepare_amz_invoice_upload_kwargs(instance)
                before_req = time.time()
                diff = int(after_req - before_req)
                if 3 > diff > 0:
                    time.sleep(3 - diff)
                response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
                after_req = time.time()
                if response.get('reason'):
                    _logger.info(_(response.get('reason')))
                else:
                    results = response.get('result')
                    if results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get('value', False):
                        last_feed_submission_id = results.get('FeedSubmissionInfo', {}).get(
                            'FeedSubmissionId', {}).get('value', False)
                        vals = {'feed_result_id': last_feed_submission_id,
                                'feed_submit_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                                'instance_id': instance.id, 'user_id': self._uid,
                                'feed_type': 'upload_invoice',
                                'seller_id': seller_id,
                                'invoice_id' : invoice_id}
                        feed = feed_submit_obj.create(vals)
                        invoice.write({'invoice_sent': True, 'feed_id': feed.id})
                        self.env.cr.commit()
        return True

    def _prepare_amz_invoice_upload_kwargs(self, instance):
        """
        Prepare arguments for submit invoice upload feed
        For Invoice:
        metadata:orderid=XXX-XXXXXXX-XXXXXXX;metadata:totalAmount=3.25;metadata:totalvatamount=1.23;metadata:invoicenumber=INT-3431-XJE3
            OR
        metadata:shippingid=37fjxryfg3;metadata:totalAmount=3.25;metadata:totalvatamount=1.23;metadata:invoicenumber=INT-3431-XJE3
        For Credit Note:
        metadata:shippingid=123456789;metadata:totalAmount=3.25;metadata:totalvatamount=1.23;metadata:invoicenumber=INT-3431-XJE3;
        metadata:documenttype=CreditNote;metadata:transactionid=amzn:crow:429491192ksjfhe39sk
        @author: KK
        :param instance: amazon.instance.ept()
        :return: feed values dict{}
        """
        report_obj = self.env['ir.actions.report']
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        metadata = "metadata:orderid={};metadata:totalAmount={};metadata:totalvatamount={};metadata:invoicenumber={};" \
                   "metadata:documenttype={}".format(self.amz_sale_order_id.amz_order_reference, self.amount_total,
                                                     self.amount_tax, self.name,
                                                     'Invoice' if self.type == 'out_invoice' else 'CreditNote')
        report_name = instance.seller_id.amz_invoice_report.report_name if instance.seller_id.amz_invoice_report else 'account.report_invoice'
        report = report_obj._get_report_from_name(report_name)
        result, result_type = report.render_qweb_pdf(res_ids=self.ids)
        invoice_pdf = base64.b64encode(result).decode('utf-8')
        return {'merchant_id': instance.seller_id.merchant_id and str(instance.seller_id.merchant_id) or False,
                'auth_token': instance.seller_id.auth_token and str(instance.seller_id.auth_token) or False,
                'app_name': 'amazon_ept',
                'emipro_api': 'update_invoices_in_amazon',
                'account_token': account.account_token,
                'dbuuid': dbuuid,
                'data': invoice_pdf,
                'metadata': metadata,
                'amazon_marketplace_code': instance.seller_id.country_id.amazon_marketplace_code or
                                           instance.seller_id.country_id.code,
                'marketplaceids': [instance.market_place_id]}

    @api.model
    def _update_amz_partner_address_detail_in_move(self):
        """
        Usage: Save data for tax reports in future use.
        :return:
        """
        self.env.cr.execute("""select is_move_data_updated from amazon_seller_ept""")
        raw_data = self.env.cr.dictfetchall()
        if raw_data and not raw_data[0].get('is_move_data_updated', False):
            query = """update account_move set ship_city=T.shipping_city, ship_state_id=T.shipping_state, ship_country_id=T.shipping_country, ship_postal_code=T.shipping_zip, bill_city=T.invoice_city,bill_postal_code=T.invoice_zip,bill_state_id=T.invoice_state,bill_country_id=T.invoice_country
                        from (select r2.id as partner_invoice_id, r2.city as invoice_city, r2.zip as invoice_zip, r2.state_id as invoice_state, r2.country_id as invoice_country, r3.id as partner_shipping_id, r3.city as shipping_city, r3.zip as shipping_zip, r3.state_id as shipping_state, r3.country_id as shipping_country from sale_order
                        inner join res_partner r2 on r2.id=sale_order.partner_invoice_id
                        inner join res_partner r3 on r3.id=sale_order.partner_shipping_id
                        where amz_instance_id is not null)T
                        where partner_id in (T.partner_invoice_id,T.partner_shipping_id);
                        """
            self.env.cr.execute(query)
            self.env.cr.execute("""update res_partner set is_amz_customer = 'true' where email like '%marketplace.amazon.%'""")
            self.env.cr.execute("""update amazon_seller_ept set is_move_data_updated = true""")
