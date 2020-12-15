from odoo import fields, models, api

class Warehouse(models.Model):
    _inherit = "stock.warehouse"

    bigcommerce_store_ids = fields.Many2many('bigcommerce.store.configuration',string="BigCommerce Stores")

