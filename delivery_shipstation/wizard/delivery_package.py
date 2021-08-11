# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from datetime import datetime
from odoo.exceptions import ValidationError


class DeliveryPackage(models.TransientModel):
    _name = 'delivery.package.ref'
    _description = 'Delivery Package'

    name = fields.Char(string="Package Reference")
    tracking_ref = fields.Char(string="Tracking Reference")
    shipping_date = fields.Datetime(string="Date", default=fields.Datetime.now,)
    shipstation_carrier_id = fields.Many2one("shipstation.carrier", string="Shipstation Carrier")
    carrier_id = fields.Many2one("delivery.carrier", string="Carrier")
    ship_package_id = fields.Many2one("shipstation.package", string="Package")
    product_line = fields.One2many('delivery.package.plan', 'delivery_ref_id', string="Product Line")
    picking_id = fields.Many2one('stock.picking', string="Picking")
    shipping_weight = fields.Float(string='Shipping Weight', help="Total weight of the package.")
    is_dropship = fields.Boolean(string="Is Dropship")

    def confirm(self):
        package_history = []
        move_lines = self.env['stock.move.line']
        # move_lines = self.product_line.mapped('move_line_id')
        for line  in self.product_line.filtered(lambda x: x.quantity_done > 0):
            move_lines |= line.move_line_id
            line.move_line_id.qty_done = line.quantity_done

        if move_lines:
            package_id = self.picking_id._put_in_pack(move_lines)
            if package_id:
                package_id.update({
                        'tracking_ref': self.tracking_ref,
                        'package_date': self.shipping_date,
                        'shipstation_carrier_id': self.shipstation_carrier_id,
                        'carrier_id': self.carrier_id,
                        'ship_package_id': self.ship_package_id,
                        'shipping_weight': self.shipping_weight
                })
            for pack_line in self.product_line.filtered(lambda x: x.quantity_done > 0):
                item_dict = {
                    'product_id': pack_line.product_id.id,
                    'tracking_ref': self.tracking_ref,
                    'shipping_date': self.shipping_date,
                    'product_qty': pack_line.quantity_done,
                    'package_id': package_id.id
                }
                package_history.append((0,0,item_dict))
            self.picking_id.update({'shipping_package_line': package_history})
        else:
            raise ValidationError(_("No product for put in pack.!"))


    @api.model
    def default_get(self, fields):
        res = super(DeliveryPackage, self).default_get(fields)
        if self._context.get('active_id'):
            active_id = self._context.get('active_id')
            active_data = self.env['stock.picking'].browse(active_id)
            product_line = [(0, 0, {
                'product_id': line.product_id.id,
                'product_uom_qty': line.product_uom_qty,
                'move_id': line.move_id.id,
                'move_line_id': line.id,
            }) for line in active_data.move_line_ids_without_package.filtered(lambda x: not x.result_package_id)]
            is_dropship = any([m._is_dropshipped() for m in active_data.move_ids_without_package])
            res.update({'product_line': product_line, 'picking_id': active_id, 'is_dropship': is_dropship})
        return res
        

class DeliveryPackagePlan(models.TransientModel):
    _name = 'delivery.package.plan'
    _description = 'Delivery Package Plan'

    delivery_ref_id = fields.Many2one('delivery.package.ref', string="Delivery Ref")
    product_id = fields.Many2one('product.product', string="Product")
    quantity_done = fields.Float(string='Done Quantity')
    product_uom_qty = fields.Float(string='Reserved Quantity')
    move_id = fields.Many2one('stock.move', string="Move")
    move_line_id = fields.Many2one("stock.move.line", string="Move Line")
