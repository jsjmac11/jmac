from odoo import fields, models, api, _
import werkzeug.utils


class NotificationMessage(models.TransientModel):
    _name = 'notification.message'
    _description = 'Notification Message'

    message = fields.Char("Message", readonly=True)
    qty = fields.Float(string="Add to Buy Quantity")
    sale_line_id = fields.Many2one("sale.order.line", 'Line ID', invisible=True)
    partner_id = fields.Many2one('res.partner', 'Vendor', invisible=True)

    def update_quantity(self):
        dict = {'line_split': True,
                'vendor_id': self.partner_id.id,
                'product_uom_qty': self.qty,
                'parent_line_id': self.sale_line_id.id,
                'order_id': self.sale_line_id.order_id.id if self.sale_line_id.order_id else False,
                }
        if self._context.get('add_to_buy'):
            route_id = self.env.ref('purchase_stock.route_warehouse0_buy').id
            dict.update({'line_type': 'buy','route_id': route_id})
        elif self._context.get('dropship'):
            route_id = self.env.ref('stock_dropshipping.route_drop_shipping').id
            dict.update({'line_type': 'dropship','route_id': route_id})
        elif self._context.get('ship_from_here'):
            dict.update({'line_type': 'stock'})

        split_line_id = self.sale_line_id.copy(dict)
        return True