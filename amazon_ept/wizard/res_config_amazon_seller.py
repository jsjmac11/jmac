from odoo import models, fields, api
from odoo.exceptions import Warning

from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT


class AmazonSellerConfig(models.TransientModel):
    _name = 'res.config.amazon.seller'
    _description = 'Amazon Seller Configurations'

    name = fields.Char("Seller Name", help="Name of Seller to identify unique seller in the ERP")
    country_id = fields.Many2one('res.country', string="Country", help="Country name in which seller is registered")
    company_id = fields.Many2one('res.company', string='Company',
                                 help="Company of this seller All transactions which do based on seller country")
    developer_id = fields.Many2one('amazon.developer.details.ept', compute="set_developer_id",
                                   string="Developer ID", store=False,
                                   help="User have to autorised developer id in seller central account and generate auth token")
    developer_name = fields.Char("Developer Name")
    auth_token = fields.Char("Auth Token",
                             help="Generate auth_tocken from seller central account based on developer_id")
    merchant_id = fields.Char("Merchant Id", help="Seller's Merchant ID")
    amazon_selling = fields.Selection([('FBA', 'FBA'),
                                       ('FBM', 'FBM'),
                                       ('Both', 'FBA & FBM')],
                                      string='Fulfillment By ?', default='Both',
                                      help="Select FBA for Fulfillment by Amazon, FBM for Fulfillment by Merchant, "
                                           "FBA & FBM for those sellers who are doing both.")
    """
        Modified: updated code to create iap account if not exist and if exist iap account than
                  verify to check if credit exist for that account than it will allow to create seller
                  if credit not exist than it will raise popup to purchase credits for that account.
    """

    def prepare_marketplace_kwargs(self, account):
        """
        Prepare Arguments for Load Marketplace.
        :return: dict{}
        """
        ir_config_parameter_obj = self.env['ir.config_parameter']
        dbuuid = ir_config_parameter_obj.sudo().get_param('database.uuid')
        return {'merchant_id': self.merchant_id and str(self.merchant_id) or False,
                'auth_token': self.auth_token and str(self.auth_token) or False,
                'app_name': 'amazon_ept',
                'account_token': account.account_token,
                'emipro_api': 'test_amazon_connection_v13',
                'dbuuid': dbuuid,
                'amazon_selling': self.amazon_selling,
                'amazon_marketplace_code': self.country_id.amazon_marketplace_code or self.country_id.code
                }

    def prepare_amazon_seller_vals(self, company_id):
        """
        Prepare Amazon Seller values
        :param company_id: res.company()
        :return: dict
        """
        return {
            'name': self.name,
            'country_id': self.country_id.id,
            'company_id': company_id.id,
            'amazon_selling': self.amazon_selling,
            'merchant_id': self.merchant_id,
            'auth_token': self.auth_token,
            'developer_id': self.developer_id.id,
            'developer_name': self.developer_name,
        }

    def create_transaction_type(self, seller):
        trans_line_obj = self.env['amazon.transaction.line.ept']
        trans_type_ids = self.env['amazon.transaction.type'].search([])
        for trans_id in trans_type_ids:
            trans_line_vals = {
                'transaction_type_id': trans_id.id,
                'seller_id': seller.id,
                'amazon_code': trans_id.amazon_code,
            }
            trans_line_obj.create(trans_line_vals)

    def update_reimbursement_details(self, seller):
        prod_obj = self.env['product.product']
        partner_obj = self.env['res.partner']
        product = prod_obj.search(
            [('default_code', '=', 'REIMBURSEMENT'), ('type', '=', 'service')])

        vals = {'name': 'Amazon Reimbursement'}
        partner_id = partner_obj.create(vals)

        journal_id = self.env['account.journal'].search([('type','=','sale'),('company_id','=',
                                                                              seller.company_id.id)],order="id",limit=1)

        seller.write(
            {'reimbursement_customer_id': partner_id.id, 'reimbursement_product_id': product.id,
             'sale_journal_id':journal_id and journal_id.id})
        return True

    def test_amazon_connection(self):
        """
        Create Seller account in ERP if not created before.
        If auth_token and merchant_id found in ERP then raise Warning.
        If Amazon Seller Account is registered in IAP raise Warning.
        IF Amazon Seller Account is not registered in IAP then create it.
        This function will load Marketplaces automatically based on seller region.
        :return:
        """
        amazon_seller_obj = self.env['amazon.seller.ept']
        iap_account_obj = self.env['iap.account']
        seller_exist = amazon_seller_obj.search([('auth_token', '=', self.auth_token),
                                                 ('merchant_id', '=', self.merchant_id)])
        account = iap_account_obj.search([('service_name', '=', 'amazon_ept')])
        if seller_exist:
            raise Warning('Seller already exist with given Credential.')
        elif account:
            kwargs = self.prepare_marketplace_kwargs(account)
            response = iap.jsonrpc(DEFAULT_ENDPOINT + '/verify_iap', params=kwargs, timeout=1000)
        else:
            account = iap_account_obj.create({'service_name': 'amazon_ept'})
            account._cr.commit()
            kwargs = self.prepare_marketplace_kwargs(account)
            response = iap.jsonrpc(DEFAULT_ENDPOINT + '/register_iap', params=kwargs, timeout=1000)
        if response.get('error', {}):
            raise Warning(response.get('error'))
        else:
            flag = response.get('result', {})
            if flag:
                company_id = self.company_id or self.env.user.company_id or False
                vals = self.prepare_amazon_seller_vals(company_id)
                if self.country_id.code in ['AE', 'DE', 'EG', 'ES', 'FR', 'GB', 'IN', 'IT', 'SA', 'TR', 'NL', 'SE']:
                    vals.update({'is_european_region':True})
                else:
                    vals.update({'is_european_region':False})
                try:
                    seller = amazon_seller_obj.create(vals)
                    seller.load_marketplace()
                    self.create_transaction_type(seller)

                except Exception as e:
                    raise Warning('Exception during instance creation.\n %s' % (str(e)))
                action = self.env.ref(
                    'amazon_ept.action_amazon_configuration', False)
                result = action and action.read()[0] or {}
                result.update({'seller_id': seller.id})
                if seller.amazon_selling in ['FBA', 'Both']:
                    self.update_reimbursement_details(seller)
                    seller.auto_create_stock_adjustment_configuration()
                seller.update_user_groups()

        return True

    def set_developer_id(self):
        """
        change country id on change od developer id.
        :return:
        """
        self.onchange_country_id()

    @api.onchange('country_id')
    def onchange_country_id(self):
        """
        On change of country update developer id and developer name.
        :return:
        """
        if self.country_id:
            developer_id = self.env['amazon.developer.details.ept'].search(
                [('developer_country_id', '=', self.country_id.id)])
            self.update({'developer_id': developer_id.id or False,
                         'developer_name': developer_id.developer_name or False})
