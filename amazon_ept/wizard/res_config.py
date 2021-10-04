from odoo import models, fields, api
from odoo.addons.iap.models import iap
from odoo.exceptions import Warning
import requests
from odoo.http import request
from ..endpoint import DEFAULT_ENDPOINT
from odoo import SUPERUSER_ID
from datetime import datetime, timedelta


class AmazonConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    amz_seller_id = fields.Many2one('amazon.seller.ept', string='Amazon Seller', help="Unique Amazon Seller name")
    amz_instance_id = fields.Many2one('amazon.instance.ept', string='Amazon Instance', help="Select Amazon Instance")
    amz_instance_removal_order = fields.Many2one('amazon.instance.ept', string='Removal Order Instance',
                                                 help="Select Amazon Instance For Removal Order")
    amazon_selling = fields.Selection([('FBA', 'FBA'),
                                       ('FBM', 'FBM'),
                                       ('Both', 'FBA & FBM')],
                                      string='Fulfillment By ?', default='FBM',
                                      help="Select FBA for Fulfillment by Amazon, FBM for Fulfillment by Merchant, "
                                           "FBA & FBM for those sellers who are doing both.")
    is_default_odoo_sequence_in_sales_order_fbm = fields.Boolean("Is default Odoo Sequence in Sales Orders (FBM) ?")
    amz_order_prefix = fields.Char(size=10, string='Amazon Order Prefix')
    amz_auto_workflow_id = fields.Many2one('sale.workflow.process.ept',
                                           string='Amazon Auto Workflow')

    amz_country_id = fields.Many2one('res.country', string="Country Name")
    amz_warehouse_id = fields.Many2one('stock.warehouse', string="Amazon Warehouse")
    company_for_amazon_id = fields.Many2one('res.company', string='Amazon Company Name',
                                            related="amz_seller_id.company_id",
                                            store=False)
    amz_payment_term_id = fields.Many2one('account.payment.term', string='Payment Term')

    amz_partner_id = fields.Many2one('res.partner', string='Default Customer')
    amz_lang_id = fields.Many2one('res.lang', string='Language Name')
    amz_team_id = fields.Many2one('crm.team', 'Amazon Sales Team')
    amz_instance_pricelist_id = fields.Many2one(
        'product.pricelist', string='Pricelist Name')
    amz_create_new_product = fields.Boolean('Allow to create new product if not found in odoo ?',
                                            default=False)
    # Account field
    amazon_property_account_payable_id = fields.Many2one(
        'account.account', string="Account Payable",
        help='This account will be used instead of the default one as the payable account for the current partner')
    amazon_property_account_receivable_id = fields.Many2one(
        'account.account', string="Account Receivable",
        help='This account will be used instead of the default one as the receivable account for the current partner')

    amz_shipment_charge_product_id = fields.Many2one("product.product", "Amazon Shipment Fee",
                                                     domain=[('type', '=', 'service')])
    amz_gift_wrapper_product_id = fields.Many2one("product.product", "Amazon Gift Wrapper Fee",
                                                  domain=[('type', '=', 'service')])
    amz_promotion_discount_product_id = fields.Many2one("product.product",
                                                        "Amazon Promotion Discount",
                                                        domain=[('type', '=', 'service')])
    amz_ship_discount_product_id = fields.Many2one("product.product", "Amazon Shipment Discount",
                                                   domain=[('type', '=', 'service')])

    amz_fba_auto_workflow_id = fields.Many2one('sale.workflow.process.ept',
                                               string='Auto Workflow (FBA)')
    amz_fba_warehouse_id = fields.Many2one(
        'stock.warehouse', string='FBA Warehouse')
    amz_is_another_soft_create_fba_shipment = fields.Boolean(
        string="Does another software create the FBA shipment reports?", default=False)
    amz_is_another_soft_create_fba_inventory = fields.Boolean(
        string="Does another software create the FBA Inventory reports?", default=False)
    is_allow_to_create_removal_order = fields.Boolean('Allow Create Removal Order In FBA?',
                                                      help="Allow to create removal order in FBA.")
    removal_warehouse_id = fields.Many2one(
        'stock.warehouse', string="Removal Warehouse", help="Removal Warehouse")
    amz_validate_stock_inventory_for_report = fields.Boolean(
        "Auto Validate Amazon FBA Live Stock Report")
    amz_is_reserved_qty_included_inventory_report = fields.Boolean(
        string='Is Reserved Qyantity to be included FBA Live Inventory Report?')
    amz_is_default_odoo_sequence_in_sales_order_fba = fields.Boolean(
        "Is default Odoo Sequence In Sales Orders (FBA) ?")
    amz_fba_order_prefix = fields.Char(size=10, string='Amazon FBA Order Prefix')
    amz_def_fba_partner_id = fields.Many2one('res.partner',
                                             string='Default Customer for FBA pending order')
    amz_instance_stock_field = fields.Selection(
        [('free_qty', 'Free Quantity'), ('virtual_available', 'Forecast Quantity')],
        string="Stock Type", default='free_qty')
    amz_instance_settlement_report_journal_id = fields.Many2one('account.journal',
                                                                string='Settlement Report Journal')
    amz_instance_ending_balance_account_id = fields.Many2one('account.account',
                                                             string="Ending Balance Account")
    amz_instance_ending_balance_description = fields.Char(
        "Ending Balance Description")
    amz_instance_invoice_tmpl_id = fields.Many2one("mail.template", string="Invoice Template",
                                                   default=False)
    amz_instance_refund_tmpl_id = fields.Many2one("mail.template", string="Refund Template",
                                                  default=False)
    # Unsellable Location
    amz_unsellable_location_id = fields.Many2one('stock.location', string="Unsellable Location",
                                                 help="Select instance wise amazon unsellable location")
    amz_reimbursement_customer_id = fields.Many2one("res.partner", string="Reimbursement Customer")
    amz_reimbursement_product_id = fields.Many2one("product.product", string="Reimbursement Product")
    amz_sales_journal_id = fields.Many2one('account.journal', string='Sales Journal', domain=[('type', '=', 'sale')])
    amz_fulfillment_latency = fields.Integer('Fullfillment Latency', default=3)
    amz_outbound_instance_id = fields.Many2one('amazon.instance.ept', string='Default Outbound Instance',
                                                help="Select Amazon Instance for Outbound Orders.")
    amz_tax_id = fields.Many2one('account.tax', string="Tax Account")
    amz_is_usa_marketplace = fields.Boolean(string="Is USA Marketplace", store=False, default=False)
    stock_update_warehouse_ids = fields.Many2many('stock.warehouse',\
                                            'stock_warehouse_amazon_config_rel',
                                            'config_id',\
                                            'warehouse_id', string="Warehouses",\
                                            help="Warehouses which will fulfill the orders")
    def switch_amazon_fulfillment_by(self):
        action = self.env.ref('amazon_ept.res_config_action_amazon_marketplace', False)
        result = action and action.read()[0] or {}
        ctx = result.get('context', {}) and eval(result.get('context'))
        active_seller = request.session['amz_seller_id']
        if active_seller:
            marketplace_obj = self.env['amazon.marketplace.ept']
            amazon_active_seller = self.env['amazon.seller.ept'].browse(active_seller)
            amazon_active_seller.load_marketplace()
            market_place_id = amazon_active_seller.instance_ids.filtered(
                lambda x:x.market_place_id).mapped(
                    'market_place_id')
            marketplace_id = marketplace_obj.search([('seller_id', '=', active_seller),('market_place_id', 'not in', market_place_id)])
            other_marketplace_ids = marketplace_obj.search([('market_place_id', 'in', ['A1F83G8C2ARO7P']),
                                                            ('seller_id', '=', active_seller)])
            ctx.update({'default_seller_id': active_seller,
                        'deactive_marketplace':marketplace_id.ids,
                        'other_marketplace_ids':other_marketplace_ids.ids})
        # ctx.update({'default_seller_id':request.session['amz_seller_id']})
        result['context'] = ctx
        return result

    # VCS tax report
    is_vcs_activated = fields.Boolean(string="Is Vat calculation Service Activated ?")
    is_european_region = fields.Boolean(related='amz_seller_id.is_european_region')

    is_any_european_seller = fields.Boolean()

    allow_auto_create_outbound_orders = fields.Boolean()
    fulfillment_action = fields.Selection([("Ship", "Ship"), ("Hold", "Hold")], default="Ship")
    shipment_category = fields.Selection([("Expedited", "Expedited"),
                                          ("NextDay", "NextDay"),
                                          ("SecondDay", "SecondDay"),
                                          ("Standard", "Standard"),
                                          ("Priority", "Priority"),
                                          ("ScheduledDelivery", "ScheduledDelivery")],
                                         default="Standard")
    fulfillment_policy = fields.Selection([("FillOrKill", "FillOrKill"), ("FillAll", "FillAll"),
                                           ("FillAllAvailable", "FillAllAvailable")],
                                          default="FillOrKill")
    invoice_upload_policy = fields.Selection([("amazon", "Amazon Create invoices"), ("custom", "Upload Invoice from Odoo")],
                                          string="Invoice Upload Policy")
    is_invoice_number_same_as_vcs_report = fields.Boolean(string="Is Invoice Number Same As VCS Report?")
    amz_upload_refund_invoice = fields.Boolean(string='Export Customer Refunds to Amazon via API?', default=False)
    amz_invoice_report = fields.Many2one("ir.actions.report", string="Invoice Report")

    def set_values(self):
        super(AmazonConfigSettings, self).set_values()
        self.amz_seller_id.update_user_groups()
        return True

    @api.onchange('amz_seller_id')
    def onchange_amz_seller_id(self):
        vals = {}
        domain = {}
        if self.amz_seller_id:
            request.session['amz_seller_id'] = self.amz_seller_id.id
            seller = self.amz_seller_id
            self.env['amazon.instance.ept'].search(
                [('seller_id', '=', self.amz_seller_id.id)])
            vals = self.onchange_amz_instance_id()
            vals['value'][
                'is_default_odoo_sequence_in_sales_order_fbm'] = seller.is_default_odoo_sequence_in_sales_order or False
            vals['value']['amazon_selling'] = seller.amazon_selling
            vals['value']['amz_order_prefix'] = seller.order_prefix
            vals['value']['amz_fba_order_prefix'] = seller.fba_order_prefix

            vals['value'][
                'amz_auto_workflow_id'] = seller.fbm_auto_workflow_id and seller.fbm_auto_workflow_id.id or False
            vals['value']['amz_create_new_product'] = seller.create_new_product or False

            vals['value'][
                'amz_shipment_charge_product_id'] = seller.shipment_charge_product_id and \
                                                    seller.shipment_charge_product_id.id or False
            vals['value'][
                'amz_gift_wrapper_product_id'] = seller.gift_wrapper_product_id and seller.gift_wrapper_product_id.id \
                                                 or False
            vals['value'][
                'amz_promotion_discount_product_id'] = seller.promotion_discount_product_id and \
                                                       seller.promotion_discount_product_id.id or False
            vals['value'][
                'amz_ship_discount_product_id'] = seller.ship_discount_product_id and \
                                                  seller.ship_discount_product_id.id or False
            vals['value'][
                'amz_fba_auto_workflow_id'] = seller.fba_auto_workflow_id and seller.fba_auto_workflow_id.id or False
            vals['value'][
                'amz_is_another_soft_create_fba_shipment'] = seller.is_another_soft_create_fba_shipment or False
            vals['value'][
                'amz_is_another_soft_create_fba_inventory'] = seller.is_another_soft_create_fba_inventory or False
            vals['value'][
                'amz_validate_stock_inventory_for_report'] = seller.validate_stock_inventory_for_report or False
            vals['value'][
                'amz_is_reserved_qty_included_inventory_report'] = \
                seller.amz_is_reserved_qty_included_inventory_report or False
            vals['value'][
                'amz_is_default_odoo_sequence_in_sales_order_fba'] = \
                seller.is_default_odoo_sequence_in_sales_order_fba or False
            vals['value'][
                'amz_def_fba_partner_id'] = seller.def_fba_partner_id and seller.def_fba_partner_id.id or False
            vals['value'][
                'amz_payment_term_id'] = seller.payment_term_id and seller.payment_term_id.id or False
            vals['value'][
                'amz_reimbursement_customer_id'] = seller.reimbursement_customer_id and \
                                                   seller.reimbursement_customer_id.id or False
            vals['value'][
                'amz_reimbursement_product_id'] = seller.reimbursement_product_id and \
                                                  seller.reimbursement_product_id.id or False
            vals['value'][
                'amz_sales_journal_id'] = seller.sale_journal_id and seller.sale_journal_id.id or False
            vals['value'][
                'amz_fulfillment_latency'] = seller.fulfillment_latency or 0
            vals['value']['invoice_upload_policy'] = seller.invoice_upload_policy
            vals['value']['amz_upload_refund_invoice'] = seller.amz_upload_refund_invoice
            vals['value']['amz_invoice_report'] = seller.amz_invoice_report.id or False
            vals['value']['is_invoice_number_same_as_vcs_report'] = \
                seller.is_invoice_number_same_as_vcs_report
            vals['value']['is_vcs_activated'] = seller.is_vcs_activated
            vals['value']['amz_outbound_instance_id'] = seller.amz_outbound_instance_id and seller.amz_outbound_instance_id.id or False

            removal_instance_id = seller.instance_ids.filtered(
                lambda r: r.is_allow_to_create_removal_order == True)
            if removal_instance_id:
                vals['value'][
                    'is_allow_to_create_removal_order'] = removal_instance_id.is_allow_to_create_removal_order or False
                vals['value']['amz_instance_removal_order'] = removal_instance_id.id or False
                vals['value'][
                    'removal_warehouse_id'] = removal_instance_id.removal_warehouse_id and \
                                              removal_instance_id.removal_warehouse_id.id or False
            if seller.allow_auto_create_outbound_orders:
                vals["value"]["allow_auto_create_outbound_orders"] = seller.allow_auto_create_outbound_orders
                vals["value"]["fulfillment_action"] = seller.fulfillment_action
                vals["value"]["shipment_category"] = seller.shipment_category
                vals["value"]["fulfillment_policy"] = seller.fulfillment_policy
        else:
            """
            Checks if any seller is there of european region for configuration of VAT.
            @author: Maulik Barad on Date 11-Jan-2020.
            """
            sellers = self.env["amazon.seller.ept"].search_read([("is_european_region", "=", True)], ["id"])
            if sellers:
                self.is_any_european_seller = True
        vals.update({'domain': domain})
        return vals

    @api.constrains('amz_fba_warehouse_id')
    def onchange_company_fba_warehouse_id(self):
        if self.amz_fba_warehouse_id and self.amz_fba_warehouse_id.company_id and self.company_for_amazon_id and \
            self.amz_fba_warehouse_id.company_id.id !=  self.company_for_amazon_id.id:
            raise Warning(
                "Company in FBA warehouse is different than the selected company. "
                "Selected Company is %s and Company in FBA Warehouse is %s which must be same." %(
                self.company_for_amazon_id.name, self.amz_fba_warehouse_id.company_id.name))


    @api.constrains('amz_warehouse_id')
    def onchange_company_warehouse_id(self):
        if self.amz_warehouse_id and self.amz_warehouse_id.company_id and self.company_for_amazon_id and \
            self.amz_warehouse_id.company_id.id !=  self.company_for_amazon_id.id:
            raise Warning(
                "Company in warehouse is different than the selected company. "
                "Selected Company %s and Company in Warehouse is %s must be same."%(
                    self.company_for_amazon_id.name, self.amz_warehouse_id.company_id.name))

    @api.onchange('amz_instance_id')
    def onchange_amz_instance_id(self):
        values = {}

        instance = self.amz_instance_id
        if instance:
            values['amz_instance_id'] = instance.id or False
            values['amz_partner_id'] = instance.partner_id and \
                                       instance.partner_id.id or False
            values['amz_warehouse_id'] = instance.warehouse_id and \
                                         instance.warehouse_id.id or False
            values['amz_country_id'] = instance.country_id and \
                                       instance.country_id.id or False
            values['amz_team_id'] = instance.team_id and instance.team_id.id or False
            values['amz_lang_id'] = instance.lang_id and instance.lang_id.id or False
            values['amz_instance_pricelist_id'] = instance.pricelist_id and \
                                                  instance.pricelist_id.id or False

            values[
                'amazon_property_account_payable_id'] = instance.amazon_property_account_payable_id and \
                                                        instance.amazon_property_account_payable_id or False
            values[
                'amazon_property_account_receivable_id'] = instance.amazon_property_account_receivable_id and \
                                                           instance.amazon_property_account_receivable_id.id or False

            values['amz_instance_stock_field'] = instance.stock_field or False
            values['amz_instance_settlement_report_journal_id'] = instance.settlement_report_journal_id or False
            values[
                'amz_instance_ending_balance_account_id'] = instance.ending_balance_account_id and \
                                                            instance.ending_balance_account_id.id or False
            values[
                'amz_instance_ending_balance_description'] = instance.ending_balance_description or False
            values['amz_instance_invoice_tmpl_id'] = instance.invoice_tmpl_id.id or False
            values['amz_instance_refund_tmpl_id'] = instance.refund_tmpl_id.id or False
            values[
                'amz_unsellable_location_id'] = instance.fba_warehouse_id.unsellable_location_id and \
                                                instance.fba_warehouse_id.unsellable_location_id.id or False
            values['amz_fba_warehouse_id'] = instance.fba_warehouse_id and instance.fba_warehouse_id.id or False
            values['amz_tax_id'] = instance.amz_tax_id and instance.amz_tax_id.id or False
            values['amz_is_usa_marketplace'] = True if instance.market_place_id == 'ATVPDKIKX0DER' else False
            values[
                'stock_update_warehouse_ids'] = instance.stock_update_warehouse_ids and instance.stock_update_warehouse_ids.ids or False
        else:
            values = {'amz_instance_id': False, 'amz_instance_stock_field': False,
                      'amz_country_id': False,'stock_update_warehouse_ids': False,
                      'amz_lang_id': False, 'amz_warehouse_id': False,
                      'amz_instance_pricelist_id': False, 'amz_partner_id': False}
        return {'value': values}

    def execute(self):
        instance = self.amz_instance_id
        values, vals = {}, {}
        res = super(AmazonConfigSettings, self).execute()
        ctx = {}
        if instance:
            ctx.update({'default_instance_id': instance.id})

            values['warehouse_id'] = self.amz_warehouse_id and self.amz_warehouse_id.id or False
            values['country_id'] = self.amz_country_id and self.amz_country_id.id or False
            values['lang_id'] = self.amz_lang_id and self.amz_lang_id.id or False
            values['pricelist_id'] = self.amz_instance_pricelist_id and \
                                     self.amz_instance_pricelist_id.id or False
            values['partner_id'] = self.amz_partner_id and self.amz_partner_id.id or False
            values['team_id'] = self.amz_team_id and self.amz_team_id.id or False
            values['amazon_property_account_payable_id'] = self.amazon_property_account_payable_id.id or False
            values['amazon_property_account_receivable_id'] = self.amazon_property_account_receivable_id.id or False
            values['stock_field'] = self.amz_instance_stock_field or False
            values[
                'settlement_report_journal_id'] = self.amz_instance_settlement_report_journal_id and \
                                                  self.amz_instance_settlement_report_journal_id.id or False
            values[
                'ending_balance_account_id'] = self.amz_instance_ending_balance_account_id and \
                                               self.amz_instance_ending_balance_account_id.id or False
            values[
                'ending_balance_description'] = self.amz_instance_ending_balance_description or False
            values['invoice_tmpl_id'] = self.amz_instance_invoice_tmpl_id.id or False
            values['refund_tmpl_id'] = self.amz_instance_refund_tmpl_id.id or False
            # fix
            # values[
            #     'unsellable_location_id'] = self.amz_unsellable_location_id and self.amz_unsellable_location_id.id
            #     or False
            values[
                'fba_warehouse_id'] = self.amz_fba_warehouse_id and self.amz_fba_warehouse_id.id or False
            values['amz_tax_id'] = self.amz_tax_id and self.amz_tax_id.id or False
            values['is_use_percent_tax'] = True if self.amz_tax_id else False
            values['stock_update_warehouse_ids'] = [(6, 0,
                                                     self.stock_update_warehouse_ids and self.stock_update_warehouse_ids.ids or [])]

            instance.write(values)
        if self.amz_seller_id:
            vals['amazon_selling'] = self.amz_seller_id.amazon_selling or False
            vals[
                'is_default_odoo_sequence_in_sales_order'] = self.is_default_odoo_sequence_in_sales_order_fbm or False
            vals['order_prefix'] = self.amz_order_prefix and self.amz_order_prefix or False
            vals['fba_order_prefix'] = self.amz_fba_order_prefix and self.amz_fba_order_prefix or False

            vals['fbm_auto_workflow_id'] = self.amz_auto_workflow_id and self.amz_auto_workflow_id.id or False
            vals['create_new_product'] = self.amz_create_new_product or False
            vals[
                'shipment_charge_product_id'] = self.amz_shipment_charge_product_id and \
                                                self.amz_shipment_charge_product_id.id or False
            vals[
                'gift_wrapper_product_id'] = self.amz_gift_wrapper_product_id and self.amz_gift_wrapper_product_id.id \
                                             or False
            vals[
                'promotion_discount_product_id'] = self.amz_promotion_discount_product_id and \
                                                   self.amz_promotion_discount_product_id.id or False
            vals[
                'ship_discount_product_id'] = self.amz_ship_discount_product_id and \
                                              self.amz_ship_discount_product_id.id or False
            vals['fba_auto_workflow_id'] = self.amz_fba_auto_workflow_id and self.amz_fba_auto_workflow_id.id or False
            vals['is_another_soft_create_fba_shipment'] = self.amz_is_another_soft_create_fba_shipment or False
            vals['is_another_soft_create_fba_inventory'] = self.amz_is_another_soft_create_fba_inventory or False
            vals['validate_stock_inventory_for_report'] = self.amz_validate_stock_inventory_for_report or False
            vals[
                'amz_is_reserved_qty_included_inventory_report'] = self.amz_is_reserved_qty_included_inventory_report \
                                                                   or False
            vals[
                'is_default_odoo_sequence_in_sales_order_fba'] = self.amz_is_default_odoo_sequence_in_sales_order_fba \
                                                                 or False
            vals['def_fba_partner_id'] = self.amz_def_fba_partner_id and self.amz_def_fba_partner_id.id or False
            vals['payment_term_id'] = self.amz_payment_term_id and self.amz_payment_term_id.id or False
            vals[
                'reimbursement_customer_id'] = self.amz_reimbursement_customer_id and \
                                               self.amz_reimbursement_customer_id.id or False
            vals[
                'reimbursement_product_id'] = self.amz_reimbursement_product_id and \
                                              self.amz_reimbursement_product_id.id or False
            vals['sale_journal_id'] = self.amz_sales_journal_id and self.amz_sales_journal_id.id or False
            vals['fulfillment_latency'] = self.amz_fulfillment_latency or 0
            vals['invoice_upload_policy'] = self.invoice_upload_policy
            vals['amz_upload_refund_invoice'] = self.amz_upload_refund_invoice
            vals['amz_invoice_report'] = self.amz_invoice_report.id or False
            vals['is_vcs_activated'] = True if self.invoice_upload_policy else False
            vals['is_invoice_number_same_as_vcs_report'] = self.is_invoice_number_same_as_vcs_report or False
            vals['amz_outbound_instance_id'] = self.amz_outbound_instance_id and self.amz_outbound_instance_id.id or False

            if self.is_allow_to_create_removal_order:
                removal_instance_ids = self.amz_seller_id.instance_ids.filtered(
                    lambda r: r.id != self.amz_instance_removal_order.id and r.is_allow_to_create_removal_order)
                for instance_id in removal_instance_ids:
                    instance_id.write({'is_allow_to_create_removal_order': False,'removal_warehouse_id': False})

                instance_for_removal_order = self.amz_seller_id.instance_ids.filtered(
                    lambda r: r.id == self.amz_instance_removal_order.id)

                if instance_for_removal_order:
                    instance_for_removal_order.write({
                        'is_allow_to_create_removal_order':self.is_allow_to_create_removal_order
                                                           or False,
                        'removal_warehouse_id':self.removal_warehouse_id and
                                               self.removal_warehouse_id.id or False,
                    })
                    if not instance_for_removal_order.removal_order_config_ids:
                        instance_for_removal_order.amazon_removal_order_routes_create()
            else:
                if self.amz_seller_id.instance_ids:
                    self.amz_seller_id.instance_ids.write({'is_allow_to_create_removal_order': self.is_allow_to_create_removal_order or False,
                                                           'removal_warehouse_id': self.removal_warehouse_id.id if self.removal_warehouse_id else False})

            vals["allow_auto_create_outbound_orders"] = self.allow_auto_create_outbound_orders
            if self.allow_auto_create_outbound_orders:
                vals["fulfillment_action"] = self.fulfillment_action
                vals["shipment_category"] = self.shipment_category
                vals["fulfillment_policy"] = self.fulfillment_policy
            self.auto_create_outbound_scheduler()
            self.amz_seller_id.write(vals)
        if res and ctx:
            res['context'] = ctx
            res['params'] = {'seller_id': self.amz_seller_id and self.amz_seller_id.id,
                             'instance_id': instance and instance.id or False}
        return res

    def create_more_amazon_marketplace(self):
        """
        Create Other Amazon Marketplaces instance in ERP.
        :return:
        """
        action = self.env.ref('amazon_ept.res_config_action_amazon_marketplace', False)
        result = action and action.read()[0] or {}
        ctx = result.get('context', {}) and eval(result.get('context'))
        active_seller = request.session['amz_seller_id']
        if active_seller:
            marketplace_obj = self.env['amazon.marketplace.ept']
            amazon_active_seller = self.env['amazon.seller.ept'].browse(active_seller)
            amazon_active_seller.load_marketplace()
            market_place_id = amazon_active_seller.instance_ids.filtered(lambda x: x.market_place_id).mapped(
                'market_place_id')
            marketplace_id = marketplace_obj.search(
                [('seller_id', '=', active_seller), ('market_place_id', 'not in', market_place_id)])
            other_marketplace_ids = marketplace_obj.search([('market_place_id', 'in', ['A1F83G8C2ARO7P']),
                                                            ('seller_id', '=', active_seller)])

            ctx.update({'default_seller_id': request.session['amz_seller_id'],
                        'deactive_marketplace': marketplace_id.ids,
                        'default_other_marketplace_ids': other_marketplace_ids.ids})
        # ctx.update({'default_seller_id':request.session['amz_seller_id']})
        result['context'] = ctx
        return result

    def generate_buy_pack_url(self):
        """
        Generate Buy Pack URL while registering Seller ID
        :return: {}
        """
        url = 'https://iap.odoo.com/iap/1/credit?dbuuid='
        dbuuid = self.env['ir.config_parameter'].sudo(
        ).get_param('database.uuid')
        service_name = 'amazon_ept'
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        if not account:
            account = self.env['iap.account'].create({'service_name': 'amazon_ept'})
        account_token = account.account_token
        url = ('%s%s&service_name=%s&account_token=%s&credit=1') % (url, dbuuid, service_name, account_token)
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new'
        }

    def register_seller(self):
        """
        Registeration of seller with IAP
        :return: dict
        """
        payload = {'key1': 'value1'}
        url = "https://iap.odoo.emiprotechnologies.com/amazon-seller-registration"
        requests.post(url, data=payload)
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new'
        }

    def create_amazon_seller_transaction_type(self):
        """
        Create Other Amazon Marketplaces instance in ERP.
        :return:
        """
        action = self.env.ref('amazon_ept.res_config_action_amazon_transaction_type', False)
        result = action and action.read()[0] or {}
        result.update({'res_id': request.session['amz_seller_id']})
        return result

    def create_vcs_tax(self):
        action = self.env.ref('amazon_ept.res_config_action_amazon_tax_configuration', False)
        result = action and action.read()[0] or {}
        result.update({'res_id': request.session['amz_seller_id']})
        return result

    def auto_create_outbound_scheduler(self):
        """
            Auto enable/disable outbound orders scheduler based on configurations.
            :return: None
        """
        auto_create_outbound_order_cron = self.env.ref('amazon_ept.auto_create_outbound_order', raise_if_not_found=False)
        if auto_create_outbound_order_cron and self.allow_auto_create_outbound_orders:
            vals = {
                'active': self.allow_auto_create_outbound_orders,
                'nextcall': datetime.now(),
                'doall': True
            }
            auto_create_outbound_order_cron.write(vals)
        elif auto_create_outbound_order_cron:
            auto_create_outbound_order_cron.write({'active': self.allow_auto_create_outbound_orders})
