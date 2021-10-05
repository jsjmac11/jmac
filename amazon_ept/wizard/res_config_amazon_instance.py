from odoo import models, fields
from odoo.exceptions import Warning


class AmazonInstanceConfig(models.TransientModel):
    _name = 'res.config.amazon.instance'
    _description = 'Amazon Instance Configurations'

    name = fields.Char("Instance Name", help="Name of Amazon instance to identify unique instance in ERP")
    seller_id = fields.Many2one('amazon.seller.ept', string='Seller',
                                help="Select Seller Account to associate with this Instance")
    marketplace_id = fields.Many2one('amazon.marketplace.ept', string='Marketplace',
                                     domain="[('seller_id','=',seller_id),"
                                            "('is_participated','=',True)]",
                                     help="Amazon Marketplaces associated with this instanace")

    def create_amazon_instance(self):
        """
        Create Unique Amazon Instance in ERP.
        :return:
        """
        amazon_instance_obj = self.env['amazon.instance.ept']
        res_config_amazon_marketplace_obj = self.env['res.config.amazon.marketplace']
        account_tax_obj = self.env['account.tax']
        amz_tax = {}
        instance_exist = amazon_instance_obj.search([('seller_id', '=', self.seller_id.id),
                                                     ('marketplace_id', '=', self.marketplace_id.id)])
        if instance_exist:
            raise Warning('Instance already exist with given Credential.')
        company_id = self.seller_id.company_id.id or self.env.user.company_id or False
        warehouse_id = res_config_amazon_marketplace_obj.search_amazon_warehouse(company_id)
        marketplace = self.env['amazon.marketplace.ept'].search(
            [('seller_id', '=', self.seller_id.id), ('market_place_id', '=', self.marketplace_id.market_place_id)])
        if marketplace.country_id and marketplace.country_id.code == 'US':
            amz_tax_id = account_tax_obj.search(
                [('python_compute', '=', 'result = (price_unit * quantity * line_tax_amount_percent) / 100')])
            if not amz_tax_id:
                tax_vals = {
                    'name': 'Amazon Tax',
                    'amount_type': 'code',
                    'type_tax_use': 'sale',
                    'amount': 0.00,
                    'price_include': False,
                    'python_compute': 'result = (price_unit * quantity * line_tax_amount_percent) / 100'
                }
                amz_tax_id = account_tax_obj.create(tax_vals)
            amz_tax = {'amz_tax_id': amz_tax_id and amz_tax_id.id, 'is_use_percent_tax':True}
        vals = {
            'name': self.name,
            'marketplace_id': marketplace.id,
            'seller_id': self.seller_id.id,
            'warehouse_id': warehouse_id,
            'company_id': company_id,
            **amz_tax
        }
        try:
            amazon_instance_obj.create(vals)
        except Exception as e:
            raise Warning('Exception during instance creation.\n %s' % (str(e)))

        action = self.env.ref('amazon_ept.action_amazon_configuration', False)
        result = action and action.read()[0] or {}

        ctx = result.get('context', {}) and eval(result.get('context'))
        ctx.update({'default_seller_id': self.seller_id.id})
        result['context'] = ctx
        return result
