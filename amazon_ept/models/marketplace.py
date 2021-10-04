from odoo import models, fields, api


class AmazonMarketplaceEpt(models.Model):
    _name = "amazon.marketplace.ept"
    _description = 'Amazon Marketplace Details'

    name = fields.Char(size=120, string='Name', required=True)
    seller_id = fields.Many2one('amazon.seller.ept', string='Seller')
    market_place_id = fields.Char("Marketplace")
    is_participated = fields.Boolean("Marketplace Participation")
    country_id = fields.Many2one('res.country', string='Country')
    amazon_domain = fields.Char(size=120, string='Amazon Domain')
    currency_id = fields.Many2one('res.currency', string='Currency')
    lang_id = fields.Many2one('res.lang', string='Language')
    domain = fields.Char("Domain")

    @api.model
    def find_instance(self, seller, sales_channel):
        """
        Find Amazon Instance from seller_id and and Marketplace
        :param seller:
        :param sales_channel:
        :return: amazon.instance.ept()
        """

        amazon_instance_ept_obj = self.env['amazon.instance.ept']
        marketplace = self.search([('seller_id', '=', seller.id), ('name', '=', sales_channel)])
        if marketplace:
            instance = amazon_instance_ept_obj.search(
                [('seller_id', '=', seller.id), ('marketplace_id', '=', marketplace[0].id)])
            return instance and instance[0]
        return amazon_instance_ept_obj
