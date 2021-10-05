from odoo import models, fields, api

class ProductProduct(models.Model):
    _inherit = "product.product"

    is_drop_ship_product = fields.Boolean(store=False, compute="_compute_is_drop_ship_product")

    @api.depends('route_ids')
    def _compute_is_drop_ship_product(self):
        """
        This Method sets is_drop_ship_product field.
        If dropship rule get this field _compute_is_drop_ship_product write boolean(True) and visible Vendor stock
        notebook page.
        Migration done by twinkalc August 2020
        """
        customer_locations = self.env['stock.location'].search([('usage', '=', 'customer')])
        route_ids = self.route_ids | self.categ_id.route_ids
        stock_rule = self.env['stock.rule'].search([('company_id', '=', self.env.company.id), ('action', '=', 'buy'),
                                                    ('location_id', 'in', customer_locations.ids),
                                                    ('route_id', 'in', route_ids.ids)])
        if stock_rule:
            self.is_drop_ship_product = True
        else:
            self.is_drop_ship_product = False
