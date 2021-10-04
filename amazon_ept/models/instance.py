from datetime import datetime
import time
from odoo import models, fields, api, exceptions
from odoo.exceptions import Warning

from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT


class AmazonInstanceEpt(models.Model):
    _name = 'amazon.instance.ept'
    _inherit = ['mail.thread']
    _description = 'Amazon Instance Details'

    seller_id = fields.Many2one('amazon.seller.ept', string='Seller', required=True)
    marketplace_id = fields.Many2one('amazon.marketplace.ept', string='Marketplace', required=True,
                                     domain="[('seller_id','=',seller_id),"
                                            "('is_participated','=',True)]")
    fiscal_position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position',
                                         help="Fiscal Position for Taxes calculation")
    name = fields.Char(size=120, string='Name', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    color = fields.Integer(string='Color Index')
    warehouse_id = fields.Many2one(comodel_name='stock.warehouse', string='Warehouse', required=True)
    pricelist_id = fields.Many2one(comodel_name='product.pricelist', string='Pricelist')
    lang_id = fields.Many2one('res.lang', string='Language')
    partner_id = fields.Many2one('res.partner', string='Default Customer')
    merchant_id = fields.Char("Merchant Id", related="seller_id.merchant_id")
    market_place_id = fields.Char("Marketplace ID", related="marketplace_id.market_place_id", store=True)
    team_id = fields.Many2one('crm.team', 'Sales Team')
    auth_token = fields.Char('Auth Token', related="seller_id.auth_token")
    country_id = fields.Many2one("res.country", "Country", related="marketplace_id.country_id")
    active = fields.Boolean(string='Active', default=True)
    # Account Field
    amazon_property_account_payable_id = fields.Many2one('account.account', string="Account Payable",
                                                         help='This account will be used instead of the default one as the payable account for the current partner')
    amazon_property_account_receivable_id = fields.Many2one('account.account', string="Account Receivable",
                                                            help='This account will be used instead of the default one as the receivable account for the current partner')

    picking_policy = fields.Selection([('direct', 'Deliver each product when available'),
                                       ('one', 'Deliver all products at once')],
                                      string='Shipping Policy', related="seller_id.fbm_auto_workflow_id.picking_policy",
                                      readonly=True, help="Shipping Policy for orders in Amazon")
    stock_field = fields.Selection([('free_qty', 'Free Quantity'),
                                    ('virtual_available', 'Forecast Quantity')],
                                   string="Stock Type", default='free_qty')

    settlement_report_journal_id = fields.Many2one('account.journal',
                                                   string='Settlement Report Journal')
    ending_balance_account_id = fields.Many2one('account.account', string="Ending Balance Account")
    ending_balance_description = fields.Char("Ending Balance Description")
    fba_warehouse_id = fields.Many2one(comodel_name='stock.warehouse', string='FBA Warehouse',
                                       help="Select Warehouse for Manage FBA Stock")
    inventory_last_sync_on = fields.Datetime("Last FBM Inventory Sync Time")
    # Removal Order Field
    removal_order_config_ids = fields.One2many("removal.order.config.ept", 'instance_id',
                                               string="Removal Order Configuration")
    is_allow_to_create_removal_order = fields.Boolean('Allow Create Removal Order In FBA?',
                                                      help="Allow to create removal order in FBA.")
    removal_warehouse_id = fields.Many2one('stock.warehouse', string="Removal Warehouse", help="Removal Warehouse")
    is_configured_rm_ord_routes = fields.Boolean(string="Configured Removal Order Routes", default=False,
                                                 help="Configured Removal Order Routes")
    fba_order_count = fields.Integer(compute='_orders_invoices_count', string="FBA Sales Orders Count")
    fbm_order_count = fields.Integer(compute='_orders_invoices_count', string="FBM Sales Orders Count")
    fba_invoice_count = fields.Integer(compute='_orders_invoices_count', string="FBA Sales Invoices Count")
    fbm_invoice_count = fields.Integer(compute='_orders_invoices_count', string="FBM Sales Invoices Count")
    invoice_tmpl_id = fields.Many2one("mail.template", string="Invoice Template")
    refund_tmpl_id = fields.Many2one("mail.template", string="Refund Template")
    amz_tax_id = fields.Many2one('account.tax', string="Tax Account")
    is_use_percent_tax = fields.Boolean(string="Use Tax Percent?")

    stock_update_warehouse_ids = fields.Many2many('stock.warehouse', \
                                                  'stock_warehouse_amazon_instance_rel', \
                                                  'instance_id', \
                                                  'warehouse_id', \
                                                  string="FBM Warehouse(S)", \
                                                  copy=False, \
                                                  help="Warehouses which will fulfill the orders")

    def _orders_invoices_count(self):
        """
        Count Orders and Invoices via sql query from database because of increase speed of Dashboard.
        @author: Keyur Kanani
        :return:
        """
        for instance in self:
            self._cr.execute(
                "SELECT count(*) AS row_count FROM sale_order WHERE amz_fulfillment_by = 'FBA' "
                "and state not in ('draft','sent','cancel') and amz_instance_id = %s" % (
                    instance.id))
            instance.fba_order_count = self._cr.fetchall()[0][0]

            self._cr.execute(
                "SELECT count(*) AS row_count FROM sale_order WHERE amz_fulfillment_by = 'FBM' "
                "and state not in ('draft','sent','cancel') and amz_instance_id = %s" % (
                    instance.id))
            instance.fbm_order_count = self._cr.fetchall()[0][0]

            self._cr.execute(
                "SELECT count(*) AS row_count FROM account_move WHERE amz_fulfillment_by = 'FBM' "
                "and amazon_instance_id = %s" % (instance.id))
            instance.fbm_invoice_count = self._cr.fetchall()[0][0]

            self._cr.execute(
                "SELECT count(*) AS row_count FROM account_move WHERE amz_fulfillment_by = 'FBA' "
                "and amazon_instance_id = %s" % (instance.id))
            instance.fba_invoice_count = self._cr.fetchall()[0][0]

    def test_amazon_connection(self):
        """
        Test Amazon Connection from auth_token, merchant_id, account_tocken and dbuuid
        :return: Boolean
        """
        iap_account_obj = self.env['iap.account']
        ir_config_parameter_obj = self.env['ir.config_parameter']
        account = iap_account_obj.search([('service_name', '=', 'amazon_ept')])
        dbuuid = ir_config_parameter_obj.sudo().get_param('database.uuid')
        flag = False
        kwargs = {'merchant_id': self.merchant_id and str(self.merchant_id) or False,
                  'auth_token': self.auth_token and str(self.auth_token) or False,
                  'app_name': 'amazon_ept',
                  'account_token': account.account_token,
                  'emipro_api': 'test_amazon_connection_v13',
                  'dbuuid': dbuuid,
                  'amazon_selling': self.seller_id.amazon_selling,
                  'amazon_marketplace_code': self.country_id.amazon_marketplace_code or self.country_id.code,
                  }
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/verify_iap', params=kwargs, timeout=1000)
        if response.get('result'):
            flag = response.get('result')
        else:
            raise exceptions.Warning(response.get('error'))
        if flag:
            raise exceptions.Warning('Service working properly')
        return True

    def toggle_active(self):
        """ Inverse the value of the field ``active`` on the records in ``self``. """
        for record in self:
            record.active = not record.active

    def export_stock_levels(self):
        """
        This Method relocates prepare envelop using operation.
        :return: This Method return Boolean(True/False).
        """
        self.env['amazon.product.ept'].export_stock_levels_operation(self)
        self.write({'inventory_last_sync_on': datetime.now()})
        return True

    @api.constrains('is_allow_to_create_removal_order')
    def check_removal_config(self):
        """
        This Method check removal order configuration if more then one try to configure removal order configuration raise warning.
        """
        if len(self.env['amazon.instance.ept'].search(
                [('is_allow_to_create_removal_order', '=', True), ('seller_id', '=', self.seller_id.id)]).ids) > 1:
            raise Warning("Default Removal configuration allow only marketplace per seller")

    def amazon_removal_order_routes_create(self):
        """
        This Method create removal order routes.
        :return: This Method return boolean(True/False)
        """
        self.configure_amazon_removal_order_routes()

    def configure_amazon_removal_order_routes(self):
        """
        This Method relocates to create routes and pull/procurement rules for an amazon removal order.
        If is_allow_to_create_removal_order and removal_order_config_ids found in current marketplace this cases update unsellable route.
        :return: This Method Return Boolean(True/False).
        """
        self.ensure_one()
        stock_picking_type_obj = self.env['stock.picking.type']
        stock_location_obj = self.env['stock.location']
        is_allow_to_create_removal_order = self.is_allow_to_create_removal_order
        removal_order_config_ids = self.removal_order_config_ids
        if is_allow_to_create_removal_order and removal_order_config_ids:
            fba_warehouse_id = self.fba_warehouse_id or False
            self.update_unsellable_route(fba_warehouse_id, removal_order_config_ids)

        if is_allow_to_create_removal_order and not removal_order_config_ids:
            warehouse_id = self.removal_warehouse_id or False
            fba_warehouse_id = self.fba_warehouse_id or False
            if not warehouse_id or not fba_warehouse_id:
                return True

            unsellable_route_id = self.create_unsellable_route(warehouse_id, fba_warehouse_id) or False
            sellable_route_id = self.create_sellable_route(warehouse_id, fba_warehouse_id) or False
            if unsellable_route_id and sellable_route_id:
                removal_disposition_return = 'Return'
                unsellable_routes_id = unsellable_route_id.id,
                sellable_routes_id = sellable_route_id.id,
                routes_value = self.prepare_unsellable_route_value(removal_disposition_return, unsellable_routes_id,
                                                                   sellable_routes_id)
                self.removal_order_config_ids = [(0, 0, routes_value)]

            disp_picking_type_id = stock_picking_type_obj.search(
                [('warehouse_id', '=', warehouse_id.id), ('code', '=', 'outgoing')], limit=1)
            disp_location_id = stock_location_obj.search([('usage', '=', 'inventory'), ('scrap_location', '=', True)],
                                                         limit=1)
            if disp_picking_type_id and disp_location_id:
                removal_disposition = 'Disposal'
                disposal_location_id = disp_location_id.id
                disposal_picking_type_id = disp_picking_type_id.id,
                disposal_vals = self.prepare_disposal_value(removal_disposition, disposal_location_id,
                                                            disposal_picking_type_id)
                self.removal_order_config_ids = [(0, 0, disposal_vals)]
        return True

    def prepare_unsellable_route_value(self, removal_disposition_return, unsellable_routes_id, sellable_routes_id):
        """
        This Method prepare dictionary unsellable routes 'return' value.
        :param removal_disposition_return: This arguments relocates removal disposition 'return'.
        :param unsellable_routes_id: This arguments relcocates unsellable route id.
        :param sellable_routes_id: This argumentes sellable routes id.
        :return: This Method return unsellable route value dictionary.
        """
        unsellable_routes_vals = {
            'removal_disposition': removal_disposition_return,
            'unsellable_route_id': unsellable_routes_id,
            'sellable_route_id': sellable_routes_id,
        }
        return unsellable_routes_vals

    def prepare_disposal_value(self, removal_disposition, disposal_location_id, disposal_picking_type_id):
        """
        This Method prepare dictionary disposal value.
        :param removal_disposition: This arguments relocates removal disposition 'disposal'.
        :param disposal_location_id: This arguments relocates disposal location id.
        :param disposal_picking_type_id: This argument disposal picking type id.
        :return: This Method return disposal value dictionary.
        """
        disposal_vals = {
            'removal_disposition': removal_disposition,
            'location_id': disposal_location_id,
            'picking_type_id': disposal_picking_type_id,
        }
        return disposal_vals

    def create_unsellable_route(self, warehouse_id, fba_warehouse_id):
        """
        This Method relocates to create unsellable routes and pull/procurement rules for an amazon removal order.
        :param warehouse_id: This Arguments relocates removal warehouse id of amazon.
        :param fba_warehouse_id: This Argument relocates FBA warehouse id of amazon.
        :return: This Method return boolean(True/False).
        If fba_unsellable_location_id and unsellable_location_id found in this cases return unsellable_route_id object or False return.
        """
        stock_location_route_obj = self.env['stock.location.route']
        stock_location_obj = self.env['stock.location']
        stock_picking_type_obj = self.env['stock.picking.type']

        fba_unsellable_location_id = fba_warehouse_id and fba_warehouse_id.unsellable_location_id or False
        unsellable_location_id = warehouse_id and warehouse_id.unsellable_location_id or False
        if not unsellable_location_id:
            unsellable_location_id = self.env['stock.location'].search(['|', ('company_id', '=', False),
                                                                        ('company_id', '=', fba_warehouse_id.company_id.id),
                                                                        ('scrap_location', '=', True)],limit=1)

        if fba_unsellable_location_id and unsellable_location_id:
            location_id = stock_location_obj.search(
                ['|', ('company_id', '=', False), ('company_id', '=', fba_warehouse_id.company_id.id),
                 ('usage', '=', 'transit')], limit=1)
            stock_picking_type_id = fba_warehouse_id.out_type_id
            pull1_vals = {
                'name': '%s Unsellable to Transit' % (fba_warehouse_id.code),
                'action': 'pull',
                'location_src_id': fba_unsellable_location_id.id,
                'procure_method': 'make_to_stock',
                'location_id': location_id and location_id.id or False,
                'picking_type_id': stock_picking_type_id and stock_picking_type_id.id or False,
                'warehouse_id': warehouse_id.id
            }
            pull2_stock_picking_type_id = stock_picking_type_obj.search(
                [('code', '=', 'incoming'), ('warehouse_id', '=', warehouse_id.id)], limit=1)
            pull2_vals = {
                'name': '%s to %s Transit' % (fba_warehouse_id.code, warehouse_id.code),
                'action': 'pull',
                'location_src_id': location_id and location_id.id or False,
                'procure_method': 'make_to_order',
                'location_id': unsellable_location_id and unsellable_location_id.id or False,
                'picking_type_id': pull2_stock_picking_type_id and pull2_stock_picking_type_id.id or False,
                'warehouse_id': warehouse_id.id,
            }
            vals = {
                'name': '%s Unsellable to %s Unsellable' % (fba_warehouse_id.code, warehouse_id.code),
                'is_removal_order': True,
                'supplied_wh_id': warehouse_id.id,
                'supplier_wh_id': fba_warehouse_id.id,
                'rule_ids': [(0, 0, pull1_vals), (0, 0, pull2_vals)]
            }
            unsellable_route_id = stock_location_route_obj.create(vals)
            return unsellable_route_id or False
        return False

    def create_sellable_route(self, warehouse_id, fba_warehouse_id):
        """
        This Method relocates to create sellable routes and pull/procurement rules for an amazon removal order.
        :param warehouse_id: This Arguments relocates removal warehouse id of amazon.
        :param fba_warehouse_id: This Argument relocates FBA warehouse id of amazon.
        :return: This Method return boolean(True/False).
        If sellable_location_id and fba_sellable_location_id found in this cases return sellable_route_id object or False return.
        """
        stock_location_route_obj = self.env['stock.location.route']
        stock_location_obj = self.env['stock.location']
        fba_sellable_location_id = fba_warehouse_id and fba_warehouse_id.lot_stock_id or False
        sellable_location_id = warehouse_id and warehouse_id.lot_stock_id or False
        if sellable_location_id and fba_sellable_location_id:
            location_id = stock_location_obj.search(
                ['|', ('company_id', '=', False), ('company_id', '=', fba_warehouse_id.company_id.id),
                 ('usage', '=', 'transit')], limit=1)
            stock_picking_type_id = fba_warehouse_id.out_type_id
            pull1_vals = {
                'name': '%s Sellable to Transit' % (fba_warehouse_id.code),
                'action': 'pull',
                'location_src_id': fba_sellable_location_id.id,
                'procure_method': 'make_to_stock',
                'location_id': location_id and location_id.id or False,
                'picking_type_id': stock_picking_type_id and stock_picking_type_id.id or False,
                'warehouse_id': warehouse_id.id
            }

            pull2_stock_picking_type_id = warehouse_id.in_type_id
            pull2_vals = {
                'name': 'Transit to %s Transit' % (warehouse_id.code),
                'action': 'pull',
                'location_src_id': location_id and location_id.id or False,
                'procure_method': 'make_to_order',
                'location_id': sellable_location_id and sellable_location_id.id or False,
                'picking_type_id': pull2_stock_picking_type_id and pull2_stock_picking_type_id.id or False,
                'warehouse_id': warehouse_id.id
            }
            vals = {
                'name': '%s Sellable to %s Sellable' % (fba_warehouse_id.name, warehouse_id.name),
                'rule_ids': [(0, 0, pull1_vals), (0, 0, pull2_vals)],
                'supplied_wh_id': warehouse_id.id,
                'supplier_wh_id': fba_warehouse_id.id
            }
            sellable_route_id = stock_location_route_obj.create(vals)
            return sellable_route_id or False
        return False

    def update_unsellable_route(self, fba_warehouse_id, removal_order_config_ids):
        """
        This Method relocates update unsellable routes and pull/procurement rules for amazon removal order.
        :param fba_warehouse_id: This Arguments relocates FBA warehouse id of amazon.
        :param removal_order_config_ids: This Arguments relocates removal order configuration ids(Return,Disposal).
        :return: This Method return boolean(True/False).If unsellable_route_id found in this cases write pull_id.
        """
        stock_location_obj = self.env['stock.location']
        unsellable_route_id = False
        for removal_order_config_id in removal_order_config_ids:
            if removal_order_config_id.removal_disposition == "Return":
                unsellable_route_id = removal_order_config_id.unsellable_route_id or False

        fba_unsellable_location_id = fba_warehouse_id and fba_warehouse_id.unsellable_location_id or False
        for pull_id in (unsellable_route_id.rule_ids if unsellable_route_id else []):
            if pull_id.procure_method == "make_to_stock":
                location_id = stock_location_obj.search(
                    ['|', ('company_id', '=', False), ('company_id', '=', fba_warehouse_id.company_id.id),
                     ('usage', '=', 'transit')], limit=1)
                stock_picking_type_id = fba_warehouse_id.out_type_id
                cha_pull1_vals = {
                    'name': '%s Unsellable to Transit' % (fba_warehouse_id.code),
                    'location_src_id': fba_unsellable_location_id.id,
                    'location_id': location_id and location_id.id or False,
                    'picking_type_id': stock_picking_type_id and stock_picking_type_id.id or False
                }
                pull_id.write(cha_pull1_vals)
        return True

