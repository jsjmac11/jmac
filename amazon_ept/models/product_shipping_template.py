from odoo import models, fields


class AmazonProductShippingTemplate(models.Model):
    _name = "amazon.product.shipping.template"
    _description = 'amazon.product.shipping.template'

    name = fields.Char(string="Shipping Template")