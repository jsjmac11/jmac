from odoo import models, fields


class amazon_product_bullet_description(models.Model):
    _name = "amazon.product.bullet.description"
    _description = 'amazon.product.bullet.description'

    amazon_product_id = fields.Many2one('amazon.product.ept', string="Product")
    name = fields.Text(string="Description")


