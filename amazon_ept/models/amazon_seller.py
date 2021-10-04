import time
from datetime import datetime, timedelta

from odoo import SUPERUSER_ID
from odoo import models, fields, api
from odoo.exceptions import Warning
from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT

TYPE2JOURNAL = {
    'entry': 'Journal Entry',
    'out_invoice': 'Customer Invoice',
    'out_refund': 'Customer Credit Note',
    'in_invoice': 'Vendor Bill',
    'in_refund': 'Vendor Credit Note',
    'out_receipt': 'Sales Receipt',
    'in_receipt': 'Purchase Receipt'
}


class AmazonSellerEpt(models.Model):
    """
    :updated by : Kishan Sorani on date 19-Jul-2021
    :Mod : If external id was not found for default configured fields then set
           False and return so process not raise any warning like external id was not found
    """
    _name = 'amazon.seller.ept'
    _description = 'Amazon Seller Details'

    @api.model
    def _get_default_shipment_amzon_fee(self):
        return self.env.ref('amazon_ept.product_product_amazon_shipping_ept', raise_if_not_found=False)

    @api.model
    def _get_default_gift_wrapper_fee(self):
        return self.env.ref('amazon_ept.product_product_amazon_giftwrapper_fee', raise_if_not_found=False)

    @api.model
    def _get_default_promotion_discount(self):
        return self.env.ref('amazon_ept.product_product_amazon_promotion_discount', raise_if_not_found=False)

    @api.model
    def _get_default_shipment_discount(self):
        return self.env.ref('amazon_ept.product_product_amazon_shipment_discount', raise_if_not_found=False)

    @api.model
    def _get_default_payment_term(self):
        return self.env.ref('account.account_payment_term_immediate', raise_if_not_found=False)

    @api.model
    def _get_default_auto_workflow(self):
        return self.env.ref('auto_invoice_workflow_ept.automatic_validation_ept', raise_if_not_found=False)

    @api.model
    def _get_default_fba_partner_id(self):
        try:
            return self.env.ref('amazon_ept.amazon_fba_pending_order')
        except:
            pass

    @api.model
    def _get_default_fba_auto_workflow(self):
        try:
            return self.env.ref('auto_invoice_workflow_ept.automatic_validation_ept')
        except:
            pass

    def _default_journal(self):
        inv_type = self._context.get('type', 'out_invoice')
        inv_types = inv_type if isinstance(inv_type, list) else [inv_type]
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        domain = [
            ('type', 'in', list(filter(None, list(map(TYPE2JOURNAL.get, inv_types))))),
            ('company_id', '=', company_id),
        ]
        return self.env['account.journal'].search(domain, limit=1)

    def get_scheduler_list(self):
        seller_cron = self.env['ir.cron'].sudo().search([('amazon_seller_cron_id', '=', self.id)])
        for record in self:
            record.cron_count = len(seller_cron.ids)

    def _compute_region(self):
        if self.country_id.code in ['AE', 'DE', 'EG', 'ES', 'FR', 'GB', 'IN', 'IT', 'SA', 'TR','NL']:
            self.is_european_region = True
        else:
            self.is_european_region = False

    @api.constrains('invoice_upload_policy')
    def _hide_show_vcs_vidr_menu(self):
        """
        use: For Hide and Show VCS Report and VIDR Report Menu In the Statement Menu.
        @author: Keyur Kanani
        :return:
        """
        vcs_menu_id = self.env.ref('amazon_ept.menu_amazon_vcs_tax_report_ept')
        # vidr_menu_id = self.env.ref('amazon_ept.menu_amazon_vidr_tax_report_ept')
        if not self.invoice_upload_policy:
            vcs_menu_id.write({'active': False})
            # vidr_menu_id.write({'active': False})
        elif self.invoice_upload_policy == 'amazon':
            vcs_menu_id.write({'active': True})
            # vidr_menu_id.write({'active': False})
        elif self.invoice_upload_policy == 'custom':
            vcs_menu_id.write({'active': False})
            # vidr_menu_id.write({'active': True})

    name = fields.Char(string='Name', size=120, required=True, help="Amazon Seller Name for ERP")
    amazon_selling = fields.Selection([('FBA', 'FBA'),
                                       ('FBM', 'FBM'),
                                       ('Both', 'FBA & FBM')],
                                      string='Fulfillment By ?', default='FBM')
    merchant_id = fields.Char("Merchant Id")
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    country_id = fields.Many2one('res.country', string="Region",
                                 domain="[('amazon_marketplace_code','!=',False)]")
    instance_ids = fields.One2many("amazon.instance.ept", "seller_id", "Instances",
                                   help="Amazon Instance id.")
    developer_id = fields.Many2one('amazon.developer.details.ept', string="Developer ID",
                                   help="Developer Id automatically load as per region")
    developer_name = fields.Char("Developer Name", help="Developer name for use Amazon MWS")
    auth_token = fields.Char("Auth Token", help="Authentication Token created from Amazon seller central account")
    # is_pan_european = fields.Boolean(string='Is Pan European ?', help="This Field relocates Is
    # Pan European ")
    marketplace_ids = fields.One2many('amazon.marketplace.ept', 'seller_id', string='Marketplaces')
    is_default_odoo_sequence_in_sales_order = fields.Boolean(
        "Is default Odoo Sequence in Sales Orders ?")
    is_default_odoo_sequence_in_sales_order_fba = fields.Boolean(
        "Is default Odoo Sequence In Sales Orders (FBA) ?")
    order_prefix = fields.Char(size=10, string='Order Prefix')
    fba_order_prefix = fields.Char(size=10, string='FBA Order Prefix')
    allow_to_process_shipped_order = fields.Boolean(
        'Allow to process shipped order (FBM) in odoo ?',
        default=False)
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Term',
                                      default=_get_default_payment_term)
    fbm_auto_workflow_id = fields.Many2one('sale.workflow.process.ept',
                                           string='Auto Workflow (FBM)',
                                           default=_get_default_auto_workflow)
    create_new_product = fields.Boolean('Allow to create new product if not found in odoo ?',
                                        default=False)
    fba_auto_workflow_id = fields.Many2one('sale.workflow.process.ept',
                                           string='Auto Workflow (FBA)',
                                           default=_get_default_fba_auto_workflow)
    fulfillment_latency = fields.Integer('Fullfillment Latency', default=3)
    shipment_charge_product_id = fields.Many2one("product.product", "Shipment Fee",
                                                 domain=[('type', '=', 'service')],
                                                 default=_get_default_shipment_amzon_fee)
    gift_wrapper_product_id = fields.Many2one("product.product", "Gift Wrapper Fee",
                                              domain=[('type', '=', 'service')],
                                              default=_get_default_gift_wrapper_fee)
    promotion_discount_product_id = fields.Many2one("product.product", "Promotion Discount",
                                                    domain=[('type', '=', 'service')],
                                                    default=_get_default_promotion_discount)
    ship_discount_product_id = fields.Many2one("product.product", "Shipment Discount",
                                               domain=[('type', '=', 'service')],
                                               default=_get_default_shipment_discount)
    transaction_line_ids = fields.One2many('amazon.transaction.line.ept', 'seller_id',
                                           'Transactions')
    reimbursement_customer_id = fields.Many2one("res.partner", string="Reimbursement Customer")
    reimbursement_product_id = fields.Many2one("product.product", string="Product")
    sale_journal_id = fields.Many2one('account.journal', string='Sales Journal',
                                      default=_default_journal, domain=[('type', '=', 'sale')])
    removal_order_report_last_sync_on = fields.Datetime("Last Removal Order Report Request Time")
    return_report_last_sync_on = fields.Datetime("Last Return Report Request Time")
    def_fba_partner_id = fields.Many2one('res.partner',
                                         string='Default Customer for FBA pending order',
                                         default=_get_default_fba_partner_id)
    is_another_soft_create_fba_shipment = fields.Boolean(
        string="Does another software create the FBA shipment reports?", default=False)
    amz_is_reserved_qty_included_inventory_report = fields.Boolean(
        string='Is Reserved Quantity to be included FBA Live Inventory Report?',
        help="Is Reserved Quantity to be included FBA Live Inventory Report")

    is_another_soft_create_fba_inventory = fields.Boolean(
        string="Does another software create the FBA Inventory reports?",
        default=False,
        help="Does another software create the FBA Inventory reports")

    validate_stock_inventory_for_report = fields.Boolean(
        "Auto Validate Amazon FBA Live Stock Report",
        help="Auto Validate Amazon FBA Live Stock Report")
    amz_warehouse_ids = fields.One2many('stock.warehouse', 'seller_id',
                                        string='Warehouses')

    inv_adjustment_report_days = fields.Integer("Inv Adjustment Report Days", default=3,
                                                help="Days of report to import inventory Report")
    shipping_report_days = fields.Integer("Shipping Report Report Days", default=3,
                                          help="Days of report to import Shipping Report")
    customer_return_report_days = fields.Integer("Customer Return Report Days", default=3,
                                                 help="Days of report to import Customer Return Report")
    removal_order_report_days = fields.Integer("Removal Order Report Days", default=3,
                                               help="Days of report to import Removal ORder Report")
    live_inv_adjustment_report_days = fields.Integer("Live Inv Adjustment Report Days", default=3,
                                                     help="Days of report to import Live inventory Report")
    # for cron
    order_auto_import = fields.Boolean(string='Auto Order Import?')
    order_last_sync_on = fields.Datetime("Last FBM Order Sync Time")
    update_shipment_last_sync_on = fields.Datetime("Last Shipment update status Sync Time")
    amz_order_auto_update = fields.Boolean("Auto Update Order Shipment ?")
    amz_stock_auto_export = fields.Boolean(string="Stock Auto Export?")
    # For Cron FBA
    auto_import_fba_pending_order = fields.Boolean(string='Auto Import FBA Pending Order?')
    fba_pending_order_last_sync_on = fields.Datetime("FBA Pendng Order Last Sync Time")
    auto_import_shipment_report = fields.Boolean(string='Auto Import Shipment Report?')
    shipping_report_last_sync_on = fields.Datetime("Last Shipping Report Request Time")

    auto_create_removal_order_report = fields.Boolean(string="Auto Create Removal Order Report ?")
    auto_import_return_report = fields.Boolean(string='Auto Import Return Report?')
    auto_import_product_stock = fields.Boolean("Auto Import Amazon FBA Live Stock Report")
    auto_create_fba_stock_adj_report = fields.Boolean(string="Auto Create FBA Stock Adjustment Report ?")
    stock_adjustment_report_last_sync_on = fields.Datetime("Last Stock Adjustment Report Request Time")
    auto_send_refund = fields.Boolean("Auto Send Refund Via Email ?", default=False)
    auto_send_invoice = fields.Boolean("Auto Send Invoice Via Email ?", default=False)
    auto_check_cancel_order = fields.Boolean("Auto Check Cancel Order ?", default=False)
    settlement_report_auto_create = fields.Boolean("Auto Create Settlement Report ?", default=False)
    cron_count = fields.Integer("Scheduler Count",
                                compute="get_scheduler_list",
                                help="This Field relocates Scheduler Count.")

    fba_recommended_removal_report_last_sync_on = fields.Datetime("Last FBA Recommended  Report Request Time")
    inventory_report_last_sync_on = fields.Datetime("Last Inventory Report Request Time")
    settlement_report_last_sync_on = fields.Datetime("Settlement Report Last Sync Time")
    fba_order_last_sync_on = fields.Datetime("Last FBA Order Sync Time")
    is_european_region = fields.Boolean('Is European Region ?')
    is_north_america_region = fields.Boolean('Is North America Region ?', default=False)
    # is_other_pan_europe_country = fields.Boolean('Is other Pan Europe Country ?')
    other_pan_europe_country_ids = fields.Many2many('res.country', 'other_pan_europe_country_seller_rel',
                                                    'res_marketplace_id',
                                                    'country_id', "Other Pan Europe Countries")
    last_inbound_shipment_status_sync = fields.Datetime("Last Inbound Shipment Status Sync")
    amz_auto_import_inboud_shipment_status = fields.Boolean(string='Auto Import Inbound Shipment '
                                                                   'Status ?')
    auto_import_rating_report = fields.Boolean(string='Auto Import Rating Report?')
    auto_process_rating_report = fields.Boolean(string='Auto Process Rating Report?')
    rating_report_days = fields.Integer("Rating Report Days", default=3,
                                        help="Days of report to import rating Report")
    rating_report_last_sync_on = fields.Datetime("Last Rating Report Request Time")

    b2b_amazon_tax_ids = fields.One2many('amazon.tax.configuration.ept', 'seller_id', string="B2B VCS Tax")
    is_vcs_activated = fields.Boolean(string="Is VCS Activated ?")
    fba_vcs_report_days = fields.Integer("Default VCS Request Report Days", default=3)
    amz_auto_import_vcs_tax_report = fields.Boolean(string='Auto import VCS Tax report ?')
    amz_auto_upload_tax_invoices = fields.Boolean(string='Auto Upload Tax Invoices to Amazon ?')
    amz_auto_process_vcs_tax_report = fields.Boolean(string='Download and Process VCS Tax Report ?')
    vcs_report_last_sync_on = fields.Datetime("Last VCS Report Request Time")
    vidr_report_last_sync_on = fields.Datetime("Last VIDR Report Request Time")

    amazon_program = fields.Selection([('pan_eu', 'PAN EU'),
                                       ('efn', 'EFN'),
                                       ('mci', 'MCI'),
                                       ('cep', 'CEP'),
                                       ('efn+mci', 'EFN+MCI')])
    amz_fba_us_program = fields.Selection([('narf', 'NARF')])
    store_inv_wh_efn = fields.Many2one('res.country', string="Store Inv. Country")
    active = fields.Boolean('Active', default=True)
    allow_auto_create_outbound_orders = fields.Boolean()
    fulfillment_action = fields.Selection([("Ship", "Ship"), ("Hold", "Hold")])
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
    invoice_upload_policy = fields.Selection([("amazon", "Amazon Create invoices"),
                                              ("custom", "Upload Invoice from Odoo")],
                                             string="Invoice Upload Policy")
    amz_outbound_instance_id = fields.Many2one('amazon.instance.ept', string='Default Outbound Instance',
                                                help="Select Amazon Instance for Outbound Orders.")
    is_move_data_updated = fields.Boolean(string="Is Data Updated in Move?", default=False)

    is_invoice_number_same_as_vcs_report = fields.Boolean(string="Is Invoice Number Same As VCS Report?")
    amz_upload_refund_invoice = fields.Boolean(string='Export Customer Refunds to Amazon via API?', default=False)
    amz_invoice_report = fields.Many2one("ir.actions.report", string="Invoice Report")
    amz_auto_import_shipped_orders = fields.Boolean(string="Auto Import Shipped Orders?",
                                                    help="If checked, then system auto import shipped "
                                                         "orders from amazon", default=False)

    def deactivate_fba_warehouse(self):
        for seller in self:
            if seller.amazon_program in ('pan_eu', 'cep'):
                location = seller.amz_warehouse_ids.mapped('lot_stock_id')
                warehouses = tuple(seller.amz_warehouse_ids.ids)
                for warehouse in seller.amz_warehouse_ids:
                    name = warehouse.name + 'archived' + (seller.amazon_program)
                    warehouse.name = name + str(time.time())[-2:]
                    warehouse.code = warehouse.code + str(time.time())[-2:]
                    warehouse.fulfillment_center_ids.unlink()
                unsellable_location = seller.amz_warehouse_ids.mapped('unsellable_location_id')
                picking_types = self.env['stock.picking.type'].search([('warehouse_id', 'in', seller.amz_warehouse_ids.ids)])
                rule_ids = self.env['stock.rule'].search([('warehouse_id', 'in', seller.amz_warehouse_ids.ids)])
                rule_ids.write({'active': False})
                route_ids = seller.amz_warehouse_ids.mapped('route_ids')
                route_ids.write({'active': False})

                if location:
                    self._cr.execute(
                        'update stock_location set active=False where id in %s' % str(tuple(location.ids)))
                if picking_types:
                    self._cr.execute('update stock_picking_type set active=False where id in %s' % (
                        str(tuple(picking_types.ids))))
                if warehouses:
                    qry = '''update stock_warehouse set active=False where id in %s''' % (
                        str(warehouses))
                    self._cr.execute(qry)
                unsellable_location and unsellable_location.write({'active': False})

            if (seller.amazon_program in ('efn', 'mci', 'efn+mci')) or (not seller.amazon_program):
                warehouses = seller.amz_warehouse_ids
                unsellable_location = seller.amz_warehouse_ids.mapped('unsellable_location_id')
                for wh in warehouses:
                    if not seller.amazon_program:
                        name = wh.name + 'archived'
                    else:
                        name = wh.name + 'archived' + (seller.amazon_program)
                    wh.write({'active': False, 'name': name + str(time.time())[-2:], 'code': wh.code + str(time.time())[-2:]})
                    wh.fulfillment_center_ids.unlink()
                unsellable_location and unsellable_location.write({'active': False})

    def write(self, vals):
        if vals.get('active') == False:
            self.instance_ids.write({'active': False})
            self.deactivate_fba_warehouse()
            for seller in self:
                seller.with_context(deactive_seller= True).update_user_groups()

        elif vals.get('active') == True:
            seller_exist = self.env['amazon.seller.ept'].search([('auth_token', '=', self.auth_token),
                                                                 ('merchant_id', '=', self.merchant_id)])

            if seller_exist:
                raise Warning(
                    'You can not active this seller due to other seller already created with same credential.')

            instance_ids = self.with_context({'active_test': False}).instance_ids
            instance_ids and instance_ids.write({'active': True})
            fba_warehouse_ids = self.with_context({'active_test': False}).amz_warehouse_ids
            if fba_warehouse_ids:
                picking_types = self.env['stock.picking.type'].search(
                    [('warehouse_id', 'in', fba_warehouse_ids.ids), ('active', '=', False)])
                picking_types and picking_types.write({'active': True})
                unsellable_location = fba_warehouse_ids.mapped('unsellable_location_id')
                unsellable_location and unsellable_location.write({'active': True})
                rule_ids = self.env['stock.rule'].search(
                    [('warehouse_id', 'in', fba_warehouse_ids.ids), ('active', '=', False)])
                rule_ids and rule_ids.write({'active': True})
                route_ids = fba_warehouse_ids.with_context({'active_test': False}).mapped(
                    'route_ids')
                route_ids and route_ids.write({'active': True})
                location = fba_warehouse_ids.with_context({'active_test': False}).mapped('lot_stock_id')
                if len(location) == 1:
                    self._cr.execute(
                        'update stock_location set active=True where id =%s' % (location.id))
                else:
                    location = tuple(location.ids)
                    self._cr.execute('update stock_location set active=True where id in %s' % str(location))

                if len(fba_warehouse_ids) > 1:
                    fba_warehouse_ids = tuple(fba_warehouse_ids.ids)
                    qry = '''update stock_warehouse set active=True where id in %s''' % (str(fba_warehouse_ids))
                    self._cr.execute(qry)
                else:
                    qry = '''update stock_warehouse set active=True where id = %s''' % (fba_warehouse_ids.id)
                    self._cr.execute(qry)
                for fba_warehouse in self.with_context({'active_test': False}).amz_warehouse_ids:
                    name = fba_warehouse.name.split(')')[0]
                    name = name + ')'
                    fba_warehouse.write({'name': name})
            for seller in self:
                seller.update_user_groups()
        res = super(AmazonSellerEpt, self).write(vals)
        return res

    def list_of_seller_cron(self):
        seller_cron = self.env['ir.cron'].sudo().search([('amazon_seller_cron_id', '=', self.id)])
        action = {
            'domain': "[('id', 'in', " + str(seller_cron.ids) + " )]",
            'name': 'Cron Scheduler',
            'view_mode': 'tree,form',
            'res_model': 'ir.cron',
            'type': 'ir.actions.act_window',
        }
        return action

    def fbm_cron_configuration_action(self):
        action = self.env.ref('amazon_ept.action_wizard_fbm_cron_configuration_ept').read()[0]
        context = {
            'amz_seller_id': self.id,
            'amazon_selling': self.amazon_selling
        }
        action['context'] = context
        return action

    def fba_cron_configuration_action(self):
        action = self.env.ref('amazon_ept.action_wizard_fba_cron_configuration_ept').read()[0]
        context = {
            'amz_seller_id': self.id,
            'amazon_selling': self.amazon_selling
        }
        action['context'] = context
        return action

    def global_cron_configuration_action(self):
        action = self.env.ref('amazon_ept.action_wizard_global_cron_configuration_ept').read()[0]
        context = {
            'amz_seller_id': self.id,
            'amazon_selling': self.amazon_selling
        }
        action['context'] = context
        return action

    def amazon_instance_list(self):
        instance_obj = self.env['amazon.instance.ept'].search([('seller_id', '=', self.id)])
        action = {
            'domain': "[('id', 'in', " + str(instance_obj.ids) + " )]",
            'name': 'Active Instance',
            'view_mode': 'tree,form',
            'res_model': 'amazon.instance.ept',
            'type': 'ir.actions.act_window',
        }
        return action

    def auto_import_sale_order_ept(self, args={}):
        fbm_sale_order_obj = self.env['fbm.sale.order.report.ept']
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(int(seller_id))
            fbm_sale_order_obj.with_context({'is_auto_process': True}).auto_import_unshipped_order_report(seller)
            seller.write({'order_last_sync_on': datetime.now()})
        return True

    @api.model
    def auto_process_unshipped_sale_order_ept(self, args={}):
        fbm_sale_order_obj = self.env['fbm.sale.order.report.ept']
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(int(seller_id))
            cron_id = self.env.ref('amazon_ept.%s%d' % ("ir_cron_import_missing_unshipped_orders_seller_", seller_id),
                                   raise_if_not_found=False)
            if cron_id and cron_id.sudo().active:
                res = cron_id.sudo().try_cron_lock()
                if res and res.get('reason'):
                    return True
            cron_id = self.env.ref('amazon_ept.%s' % ("ir_cron_child_to_process_shipped_order_queue_line"),
                                   raise_if_not_found=False)
            if cron_id and cron_id.sudo().active:
                res = cron_id.sudo().try_cron_lock()
                if res and res.get('reason'):
                    return True
            fbm_sale_order_obj.with_context({'is_auto_process': True}).auto_process_unshipped_order_report(seller)
        return True

    @api.model
    def auto_process_missing_unshipped_sale_order_ept(self, args={}):
        sale_order_obj = self.env['sale.order']
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(int(seller_id))
            cron_id = self.env.ref('amazon_ept.%s%d' % ("ir_cron_process_amazon_unshipped_orders_seller_", seller_id),
                                   raise_if_not_found=False)
            if cron_id and cron_id.sudo().active:
                res = cron_id.sudo().try_cron_lock()
                if res and res.get('reason'):
                    return True
            sale_order_obj.import_fbm_shipped_or_missing_unshipped_orders(seller, False, False, ['Unshipped', 'PartiallyShipped'])
        return True

    @api.model
    def auto_update_order_status_ept(self, args={}):
        sale_order_obj = self.env['sale.order']
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(int(seller_id))
            sale_order_obj.amz_update_tracking_number(seller)
            seller.write({'update_shipment_last_sync_on': datetime.now()})
        return True

    condition = fields.Selection([('New', 'New'),
                                  ('UsedLikeNew', 'UsedLikeNew'),
                                  ('UsedVeryGood', 'UsedVeryGood'),
                                  ('UsedGood', 'UsedGood'),
                                  ('UsedAcceptable', 'UsedAcceptable'),
                                  ('CollectibleLikeNew', 'CollectibleLikeNew'),
                                  ('CollectibleVeryGood', 'CollectibleVeryGood'),
                                  ('CollectibleGood', 'CollectibleGood'),
                                  ('CollectibleAcceptable', 'CollectibleAcceptable'),
                                  ('Refurbished', 'Refurbished'),
                                  ('Club', 'Club')], string="Condition", default='New', copy=False)

    @api.model
    def fbm_auto_check_cancel_order_in_amazon(self, args={}):
        sale_order_obj = self.env['sale.order']
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(int(seller_id))
            marketplaceids = tuple(\
                [x.market_place_id for x in seller.instance_ids])
            sale_order_obj.with_context({'is_auto_process': True}).cancel_amazon_fbm_pending_sale_orders(\
                seller, marketplaceids, seller.instance_ids.ids)
        return True

    @api.model
    def auto_export_inventory_ept(self, args={}):
        amazon_product_obj = self.env['amazon.product.ept']
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(int(seller_id))
            if not seller:
                return True
            for instance in seller.instance_ids:
                amazon_product_obj.export_stock_levels_operation(instance)
                instance.write({'inventory_last_sync_on': datetime.now()})
        return True

    # FBA Pending Order
    @api.model
    def auto_import_fba_pending_sale_order_ept(self, args={}):
        sale_order_obj = self.env['sale.order']
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(int(seller_id))
            # Import FBM Pending Sale Order
            marketplaceids = tuple([x.market_place_id for x in seller.instance_ids])
            last_sync = seller.fba_pending_order_last_sync_on
            sale_order_obj.import_fba_pending_sales_order(seller, marketplaceids, last_sync)
            seller.write({'fba_pending_order_last_sync_on': datetime.now()})

            # Cancel Amazon FBA Pending Order
            """
            Merge Cron of Import Amazon FBA Pending Order and Check Cancelled Orders In Amazon.
            @author: Deval Jagad (31/12/2019)
            """
            sale_order_obj.with_context({'auto_process': True}).cancel_amazon_fba_pending_sale_orders(seller,
                                                                                                      marketplaceids,
                                                                                                      seller.instance_ids.ids)
        return True

    @api.model
    def auto_import_fba_shipment_status_ept(self, args={}):
        inbound_shipment_obj = self.env['amazon.inbound.shipment.ept']
        job_id = False
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(seller_id)
            current_date = datetime.utcnow()
            last_updated_before = current_date
            if seller.last_inbound_shipment_status_sync:
                last_sync_time = seller.last_inbound_shipment_status_sync
            else:
                last_sync_time = datetime.utcnow()  # UTC
            last_updated_after = (last_sync_time - timedelta(days=1))

            account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
            dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')

            kwargs = {'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
                      'auth_token': seller.auth_token and str(seller.auth_token) or False,
                      'app_name': 'amazon_ept',
                      'account_token': account.account_token,
                      'emipro_api': 'check_amazon_shipment_status_v13',
                      'dbuuid': dbuuid,
                      'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                                 seller.country_id.code,
                      'last_updated_after': last_updated_after.isoformat(),
                      'last_updated_before': last_updated_before.isoformat()
                      }
            response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
            if response.get('reason'):
                raise Warning(response.get('reason'))
            else:
                items = response.get('items')

            amazon_inbound_shipments = {}
            for amazon_result in items:
                shipment_id = amazon_result.get('ShipmentId').get('value')
                seller_sku = amazon_result.get('SellerSKU').get('value')
                if amazon_inbound_shipments:
                    keys = amazon_inbound_shipments.keys()
                    if shipment_id in keys:
                        ship_members = amazon_inbound_shipments.get(shipment_id)
                        flag = 1
                        for ship_member in ship_members:
                            if seller_sku == ship_member.get('SellerSKU').get('value'):
                                new_received_quantity = amazon_result.get('QuantityReceived').get(
                                    'value')
                                old_quantity = ship_member.get('QuantityReceived').get('value')
                                qty = float(old_quantity) + (float(new_received_quantity))
                                ship_member.get('QuantityReceived').update({'value': str(qty)})
                                flag = 0
                        if flag:
                            ship_members.append(amazon_result)
                            amazon_inbound_shipments.update({shipment_id: ship_members})
                    else:
                        amazon_inbound_shipments.update({shipment_id: [amazon_result]})
                else:
                    amazon_inbound_shipments.update({shipment_id: [amazon_result]})

            if amazon_inbound_shipments:
                job_id = self.env['common.log.book.ept'].create({'module': 'amazon_ept', 'type': 'import'})
                #Check status of all shipment from Amazon and update in ERP
                inbound_shipment_obj.check_status_ept(amazon_inbound_shipments, seller, job_id)
                max_range = 0
                ship_id_list = amazon_inbound_shipments.keys()
                while max_range < len(ship_id_list):
                    amazon_status = []
                    account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
                    dbuuid = self.env['ir.config_parameter'].sudo(
                    ).get_param('database.uuid')
                    ship_id_list = list(ship_id_list)
                    kwargs = {
                        'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
                        'auth_token': seller.auth_token and str(seller.auth_token) or False,
                        'app_name': 'amazon_ept',
                        'account_token': account.account_token,
                        'emipro_api': 'check_status_v13',
                        'dbuuid': dbuuid,
                        'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                                   seller.country_id.code,

                        'shipment_ids': ship_id_list[max_range:max_range + 50], }
                    max_range += 50
                    response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
                    if response.get('reason'):
                        raise Warning(response.get('reason'))
                    else:
                        items = response.get('amazon_shipments')
                        # items = response.get('items')
                        # datas = response.get('datas')

                    shipment_status = {}
                    for ship_member in items:
                        shipmentid = ship_member.get('ShipmentId', {}).get('value', '')
                        status = ship_member.get('ShipmentStatus', {}).get('value', '')
                        shipment_status[shipmentid] = status
                    inbound_shipment_ids = shipment_status.keys()
                    inbound_shipments = inbound_shipment_obj.search([('shipment_id', 'in', list(inbound_shipment_ids))]).ids
                    for inbound_shipment_id in inbound_shipments:
                        inbound_shipment = inbound_shipment_obj.browse(inbound_shipment_id)
                        ship_status = shipment_status.get(inbound_shipment.shipment_id)
                        inbound_shipment.write({'state': ship_status})
                        if ship_status == 'CLOSED':
                            if not inbound_shipment.closed_date:
                                inbound_shipment.write({'closed_date': time.strftime("%Y-%m-%d")})

                            # Added By: Dhaval Sanghani [12-Jun-2020]
                            # Purpose: Action Back Orders Pickings and Create Return Picking
                            pickings = inbound_shipment.mapped('picking_ids').\
                                filtered(lambda r: r.state in ['partially_available', 'assigned'] and
                                                   r.is_fba_wh_picking)
                            pickings and pickings.action_cancel()

                if not job_id:
                    job_id = self.env['common.log.book.ept'].create({'module': 'amazon_ept', 'type': 'import'})

                    self.env['common.log.lines.ept'].create(
                        {'message': "%s inbound shipment is successfully processed" % (len(amazon_inbound_shipments)),
                         'model_id': self.env['common.log.lines.ept'].get_model_id('amazon.inbound.shipment.ept'),
                         'res_id': '',
                         'log_line_id': job_id.id})

            seller.last_inbound_shipment_status_sync = last_updated_before
        return True

    def prepare_marketplace_kwargs(self):
        """
        Prepare Arguments for Load Marketplace.
        :return: dict{}
        """
        account_obj = self.env['iap.account']
        ir_config_parameter_obj = self.env['ir.config_parameter']
        account = account_obj.search([('service_name', '=', 'amazon_ept')])
        dbuuid = ir_config_parameter_obj.sudo().get_param('database.uuid')
        return {'merchant_id': self.merchant_id and str(self.merchant_id) or False,
                'auth_token': self.auth_token and str(self.auth_token) or False,
                'app_name': 'amazon_ept',
                'account_token': account.account_token,
                'emipro_api': 'load_marketplace_v13',
                'dbuuid': dbuuid,
                'amazon_selling': self.amazon_selling,
                'amazon_marketplace_code': self.country_id.amazon_marketplace_code or
                                           self.country_id.code
                }

    def prepare_marketplace_vals(self, marketplace, participations_dict):
        """
        Prepatation of values of marketplaces to create in odoo
        :param marketplace: dict{}
        :param participations_dict: dict{}
        :return: {}
        """
        currency_obj = self.env['res.currency']
        lang_obj = self.env['res.lang']
        country_obj = self.env['res.country']
        country_code = marketplace.get('DefaultCountryCode', {}).get('value')
        name = marketplace.get('Name', {}).get('value', '')
        domain = marketplace.get('DomainName', {}).get('value', '')
        lang_code = marketplace.get('DefaultLanguageCode', {}).get('value', '')
        currency_code = marketplace.get('DefaultCurrencyCode', {}).get('value', '')
        marketplace_id = marketplace.get('MarketplaceId', {}).get('value', '')
        currency_id = currency_obj.search([('name', '=', currency_code)])
        if not currency_id:
            currency_id = currency_id.search([('name', '=', currency_code), ('active', '=', False)])
            currency_id.write({'active': True})
        lang_id = lang_obj.search([('code', '=', lang_code)])
        country_id = country_obj.search([('code', '=', country_code)])
        return {
            'seller_id': self.id,
            'name': name,
            'market_place_id': marketplace_id,
            'is_participated': participations_dict.get(marketplace_id, False),
            'domain': domain,
            'currency_id': currency_id and currency_id[0].id or False,
            'lang_id': lang_id and lang_id[0].id or False,
            'country_id': country_id and country_id[0].id or self.country_id and self.country_id.id or False,
        }

    def load_marketplace(self):
        """
        Load Amazon Marketplaces based on seller regions.
        :return: True
        """
        marketplace_list = ['A2Q3Y263D00KWC', 'A2EUQ1WTGCTBG2', 'A1AM78C64UM0Y8', 'ATVPDKIKX0DER', 'A2VIGQ35RCS4UG',
                            'A1PA6795UKMFR9', 'ARBP9OOSHTCHU', 'A1RKKUPIHCS9HS', 'A13V1IB3VIYZZH', 'A1F83G8C2ARO7P',
                            'A21TJRUUN4KGV', 'APJ6JRA9NG5V4', 'A33AVAJ2PDY3EV', 'A19VAU5U5O7RUS', 'A39IBJ37TRP1C6',
                            'A1VC38T7YXB528', 'A17E79C6D8DWNP', 'A1805IZSGTT6HS', 'A2NODRKZP88ZB9', 'A1C3SOZRARQ6R3']
        marketplace_obj = self.env['amazon.marketplace.ept']
        kwargs = self.prepare_marketplace_kwargs()

        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(response.get('reason'))
        values = response.get('result')
        for value in values:
            participations = values[value].get('participations')
            marketplaces = values[value].get('marketplaces')

            participations_dict = dict(map(lambda x: (
                x.get('MarketplaceId', {}).get('value', ''),
                x.get('SellerId', {}).get('value', False)),
                                           participations))
            for marketplace in marketplaces:
                marketplace_id = marketplace.get('MarketplaceId', {}).get('value', '')
                if marketplace_id in marketplace_list:
                    vals = self.prepare_marketplace_vals(marketplace, participations_dict)
                    marketplace_rec = marketplace_obj.search(
                        [('seller_id', '=', self.id), ('market_place_id', '=',
                                                       marketplace_id)])
                    if marketplace_rec:
                        marketplace_rec.write(vals)
                    else:
                        marketplace_obj.create(vals)
        return True
    
    def update_user_groups(self):
        """
        Use: Update the user groups as per the fulfilment by
        Added on: 28Th Dec, 2020
        :return: 
        """
        amazon_selling = self.amazon_selling
        if self._context.get('deactive_seller', False):
            amazon_selling = self.update_user_group_deactive_seller(amazon_selling)
        else:
            amazon_selling = self.update_user_group_active_seller(amazon_selling)

        self = self.with_user(SUPERUSER_ID)
        amazon_fba_group = self.env.ref('amazon_ept.group_amazon_fba_ept')
        amazon_fbm_group = self.env.ref('amazon_ept.group_amazon_fbm_ept')
        amazon_fba_fbm_group = self.env.ref(
            'amazon_ept.group_amazon_fba_and_fbm_ept')
        amazon_user_group = self.env.ref('amazon_ept.group_amazon_user_ept')
        amazon_manager_group = self.env.ref('amazon_ept.group_amazon_manager_ept')
        user_list = list(set(amazon_user_group.users.ids + amazon_manager_group.users.ids))

        if amazon_selling == 'FBM':
            amazon_fbm_group.write({'users': [(6, 0, user_list)]})
            amazon_fba_group.write({'users': [(6, 0, [])]})
            amazon_fba_fbm_group.write({'users': [(6, 0, [])]})
        elif amazon_selling == 'FBA':
            amazon_fba_group.write({'users': [(6, 0, user_list)]})
            amazon_fbm_group.write({'users': [(6, 0, [])]})
            amazon_fba_fbm_group.write({'users': [(6, 0, [])]})
        elif amazon_selling == 'Both':
            amazon_fba_fbm_group.write({'users': [(6, 0, user_list)]})
            amazon_fba_group.write({'users': [(6, 0, user_list)]})
            amazon_fbm_group.write({'users': [(6, 0, user_list)]})
        return True

    def update_user_group_active_seller(self, amazon_selling):
        """
        Use: Update user group for active seller it's call when create the seller and change fulfilment by.
        Added on: 28Th Dec, 2020
        :return: fulfilment by
        """
        amazon_seller_obj = self.env['amazon.seller.ept']
        if amazon_selling == 'FBA':
            other_seller = amazon_seller_obj.search([('id', '!=', self.id), ('amazon_selling', '=', 'Both')])
            seller_company = other_seller.filtered(lambda x: x.company_id.id in self.env.user.company_ids.ids)
            if other_seller and seller_company:
                return True
            else:
                other_seller = amazon_seller_obj.search([('id', '!=', self.id), ('amazon_selling', '=', 'FBM')])
                seller_company = other_seller.filtered(lambda x: x.company_id.id in self.env.user.company_ids.ids)
                if other_seller and seller_company:
                    amazon_selling = 'Both'
        elif amazon_selling == 'FBM':
            other_seller = amazon_seller_obj.search([('id', '!=', self.id), ('amazon_selling', '=', 'Both')])
            seller_company = other_seller.filtered(lambda x: x.company_id.id in self.env.user.company_ids.ids)
            if other_seller and seller_company:
                return True
            else:
                other_seller = amazon_seller_obj.search([('id', '!=', self.id), ('amazon_selling', '=', 'FBA')])
                seller_company = other_seller.filtered(lambda x: x.company_id.id in self.env.user.company_ids.ids)
                if other_seller and seller_company:
                    amazon_selling = 'Both'
        return amazon_selling

    def update_user_group_deactive_seller(self, amazon_selling):
        """
        Use: Update user group when deactivate the seller.
        Added on: 28Th Dec, 2020
        :return: fulfilment by
        """
        amazon_seller_obj = self.env['amazon.seller.ept']
        if amazon_selling == 'FBA':
            other_seller = amazon_seller_obj.search([('id', '!=', self.id), ('amazon_selling', '=', 'Both')])
            seller_company = other_seller.filtered(lambda x: x.company_id.id in self.env.user.company_ids.ids)
            if other_seller and seller_company:
                return True
            else:
                other_seller = amazon_seller_obj.search([('id', '!=', self.id), ('amazon_selling', '=', 'FBM')])
                other_fba_seller = amazon_seller_obj.search([('id', '!=', self.id), ('amazon_selling', '=', 'FBA')])
                seller_company = other_seller.filtered(lambda x: x.company_id.id in self.env.user.company_ids.ids)
                other_fba_seller_company = other_fba_seller.filtered(lambda x: x.company_id.id in self.env.user.company_ids.ids)
                if (other_seller and other_fba_seller and seller_company and other_fba_seller_company) or (
                        not other_seller and not other_fba_seller and not seller_company and not other_fba_seller_company):
                    amazon_selling = 'Both'
                elif other_seller and not other_fba_seller and seller_company:
                    amazon_selling = 'FBM'
        elif amazon_selling == 'FBM':
            other_seller = amazon_seller_obj.search([('id', '!=', self.id), ('amazon_selling', '=', 'Both')])
            seller_company = other_seller.filtered(lambda x: x.company_id.id in self.env.user.company_ids.ids)
            if other_seller and seller_company:
                return True
            else:
                other_seller = amazon_seller_obj.search([('id', '!=', self.id), ('amazon_selling', '=', 'FBA')])
                other_fbm_seller = amazon_seller_obj.search([('id', '!=', self.id), ('amazon_selling', '=', 'FBM')])
                seller_company = other_seller.filtered(lambda x: x.company_id.id in self.env.user.company_ids.ids)
                other_seller_fbm_company = other_fbm_seller.filtered(lambda x: x.company_id.id in self.env.user.company_ids.ids)
                if (other_seller and other_fbm_seller and seller_company and other_seller_fbm_company) or (
                        not other_seller and not other_fbm_seller and not seller_company and not other_seller_fbm_company):
                    amazon_selling = 'Both'
                elif other_seller and not other_fbm_seller and seller_company:
                    amazon_selling = 'FBA'
        elif amazon_selling == 'Both':
            other_seller = amazon_seller_obj.search([('id', '!=', self.id), ('amazon_selling', '=', 'Both')])
            seller_company = other_seller.filtered(lambda x: x.company_id.id in self.env.user.company_ids.ids)
            if other_seller and seller_company:
                return True
            else:
                other_seller = amazon_seller_obj.search([('id', '!=', self.id), ('amazon_selling', '=', 'FBA')])
                other_fbm_seller = amazon_seller_obj.search([('id', '!=', self.id), ('amazon_selling', '=', 'FBM')])
                seller_company = other_seller.filtered(lambda x: x.company_id.id in self.env.user.company_ids.ids)
                other_seller_fbm_company = other_fbm_seller.filtered(lambda x: x.company_id.id in self.env.user.company_ids.ids)
                if (other_seller and other_fbm_seller and seller_company and other_seller_fbm_company) or (
                        not other_seller and not other_fbm_seller and not seller_company and not other_seller_fbm_company):
                    amazon_selling = 'Both'
                elif other_seller and not other_fbm_seller and seller_company:
                    amazon_selling = 'FBA'
                elif not other_seller and other_fbm_seller and other_seller_fbm_company:
                    amazon_selling = 'FBM'
        return amazon_selling

    def auto_create_stock_adjustment_configuration(self):
        """
        Use: Generate the stock adjustment configuration
        Added on: 11th Jan, 2021
        :return: True
        """
        reason_group_ids = self.env['amazon.adjustment.reason.group'].search([])
        customer_location, inventory_location, misplace_location_id, inbound_shipment_id = self.find_stock_adjustment_config_location()
        prepare_config_vals = list()
        stock_adjustment_configuration_obj = self.env['amazon.stock.adjustment.config']
        for group_id in reason_group_ids:
            exist_configuration = stock_adjustment_configuration_obj.search(
                [('seller_id', '=', self.id), ('group_id', '=', group_id.id)])
            if exist_configuration:
                continue
            if group_id.id == self.env.ref('amazon_ept.amazon_misplaced_and_found_ept').id:
                prepare_config_vals.append(
                    {'seller_id': self.id, 'location_id': misplace_location_id.id, 'group_id': group_id.id})
            elif group_id.id in  [self.env.ref('amazon_ept.amazon_unrecoverable_inventory_ept').id, self.env.ref('amazon_ept.amazon_transferring_ownership_ept').id]:
                prepare_config_vals.append(
                    {'seller_id': self.id, 'group_id': group_id.id, 'location_id': customer_location.id})
            elif group_id.id == self.env.ref('amazon_ept.amazon_inbound_shipement_receive_adjustment_ept').id:
                prepare_config_vals.append(
                    {'seller_id': self.id, 'group_id': group_id.id, 'location_id': inbound_shipment_id.id})
            elif group_id.id in [self.env.ref('amazon_ept.amazon_software_corrections_ept').id, self.env.ref('amazon_ept.amazon_catalogue_management_ept').id]:
                prepare_config_vals.append(
                    {'seller_id': self.id, 'group_id': group_id.id, 'location_id': inventory_location.id})
            elif group_id.id == self.env.ref('amazon_ept.amazon_damaged_inventory_ept').id:
                prepare_config_vals.append({'seller_id': self.id, 'group_id': group_id.id, 'location_id': False})

        if prepare_config_vals:
            stock_adjustment_configuration_obj.create(prepare_config_vals)
        return True

    def find_stock_adjustment_config_location(self):
        """
        Use: Find the location if not exist location then create it:
        Added on: 13th Jan, 2021
        :return: customer_location, inventory_location, misplace_location_id, inbound_shipment_id locations
        """
        stock_location_obj = self.env['stock.location']
        physical_view_location = self.env.ref('stock.stock_location_locations')
        partner_view_location = self.env.ref('stock.stock_location_locations_partner')
        virtual_location = self.env.ref('stock.stock_location_locations_virtual')
        customer_location = self.env.ref('stock.stock_location_customers')
        if not customer_location:
            customer_location = stock_location_obj.search([('location_id', '=', partner_view_location.id),
                                                           ('company_id', '=', self.company_id.id),
                                                           ('usage', '=','customer')], limit=1)
            if not customer_location:
                customer_location = stock_location_obj.search([('location_id', '=', partner_view_location.id),
                                                               ('company_id', '=', False),
                                                               ('usage', '=', 'customer')], limit=1)
            if not customer_location:
                location_vals = {'name': 'Customer',
                                 'active': True,
                                 'usage': 'customer',
                                 'company_id': self.company_id.id,
                                 'location_id': partner_view_location.id}
                customer_location = self.env['stock.location'].create(location_vals)

        inventory_location = stock_location_obj.search([('location_id', '=', virtual_location.id),
                                                        ('company_id', '=', self.company_id.id),
                                                        ('usage', '=', 'inventory')], limit=1)
        if not inventory_location:
            inventory_location = stock_location_obj.search([('location_id', '=', virtual_location.id),
                                                            ('company_id', '=', False),
                                                            ('usage', '=', 'inventory')], limit=1)
        if not inventory_location:
            location_vals = {'name': 'Inventory adjustment',
                             'active': True,
                             'usage': 'inventory',
                             'company_id': self.company_id.id,
                             'location_id': virtual_location.id}
            inventory_location = stock_location_obj.create(location_vals)

        misplace_location_id = stock_location_obj.search([('location_id', '=', physical_view_location.id),
                                                          ('company_id', '=', self.company_id.id),
                                                          ('usage', '=', 'internal'),
                                                          ('name', '=', self.name + ' ' + 'Loss by amazon')], limit=1)
        if not misplace_location_id:
            misplace_location_id = stock_location_obj.search([('location_id', '=', physical_view_location.id),
                                                              ('company_id', '=', False),
                                                              ('usage', '=', 'internal'),
                                                              ('name', '=', self.name + ' ' + 'Loss by amazon')], limit=1)
        if not misplace_location_id:
            location_vals = {'name': self.name + ' ' + 'Loss by amazon',
                             'active': True,
                             'usage': 'internal',
                             'company_id': self.company_id.id,
                             'location_id': physical_view_location.id}
            misplace_location_id = stock_location_obj.create(location_vals)

        inbound_shipment_id = stock_location_obj.search([('location_id', '=', physical_view_location.id),
                                                         ('company_id', '=', self.company_id.id),
                                                         ('usage', '=', 'transit')], limit=1)
        if not inbound_shipment_id:
            inbound_shipment_id = stock_location_obj.search([('location_id', '=', physical_view_location.id),
                                                             ('company_id', '=', False),
                                                             ('usage', '=', 'transit')], limit=1)
        if not inbound_shipment_id:
            location_vals = {'name': self.company_id.name + ': Transit Location',
                             'active': True,
                             'usage': 'transit',
                             'company_id': self.company_id.id,
                             'location_id': physical_view_location.id}
            inbound_shipment_id = self.env['stock.location'].create(location_vals)
        return customer_location, inventory_location, misplace_location_id, inbound_shipment_id

    @api.model
    def auto_process_shipped_sale_order_ept(self, args={}):
        """
        This method will auto process FBM Shipped Orders.
        :param args:
        :return: True
        """
        sale_order_obj = self.env['sale.order']
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(int(seller_id))
            sale_order_obj.import_fbm_shipped_or_missing_unshipped_orders(seller, False, False, ['Shipped'])
        return True
