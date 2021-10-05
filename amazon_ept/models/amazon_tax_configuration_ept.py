from odoo import models, fields, api


class Amazontaxconfiguration(models.Model):
    _name = 'amazon.tax.configuration.ept'
    _description = 'Amazon Tax Configuration'

    seller_id = fields.Many2one('amazon.seller.ept')
    tax_id = fields.Many2one('account.tax', string="Tax")
    is_outside_eu = fields.Boolean(string="Is Outside EU ?")
    jurisdiction_country_id = fields.Many2one('res.country', string="Jurisdiction Country")

    _sql_constraints = [
        ("amazon_tax_configuration_unique_co", "UNIQUE(seller_id,is_outside_eu,jurisdiction_country_id)",
         "Jurisdiction Country and Is Outside EU? must be unique for Seller.")]
