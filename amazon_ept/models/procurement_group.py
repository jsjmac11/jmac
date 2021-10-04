from odoo import models, fields


class procurement_group(models.Model):
    _inherit = 'procurement.group'

    removal_order_id = fields.Many2one('amazon.removal.order.ept',string='Removal Order')
    odoo_shipment_id = fields.Many2one('amazon.inbound.shipment.ept', string='Shipment')