from odoo import models, fields, api, _


class removal_order_configuration(models.Model):
    _name = "removal.order.config.ept"
    _description = "removal.order.config.ept"
    _rec_name = "removal_disposition"

    removal_disposition = fields.Selection([('Return', 'Return'), ('Disposal', 'Disposal')], default='Return',
                                           required=True, string="Disposition")
    picking_type_id = fields.Many2one("stock.picking.type", string="Picking Type")
    location_id = fields.Many2one("stock.location", string="Location")
    unsellable_route_id = fields.Many2one("stock.location.route", string="UnSellable Route")
    sellable_route_id = fields.Many2one("stock.location.route", string="Sellable Route")
    instance_id = fields.Many2one("amazon.instance.ept", string="Instance")

    _sql_constraints = [('amazon_removal_order_unique_constraint', 'unique(removal_disposition,instance_id)',
                         "Disposition must be unique per Instance.")]
