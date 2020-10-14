# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
import werkzeug.utils
from odoo.exceptions import ValidationError



class NotificationMessage(models.TransientModel):
    _name = 'notification.message'
    _description = 'Notification Message'

    message = fields.Char("Message", readonly=True)
    qty = fields.Float(string="Quantity", digits='Product Unit of Measure')
    remaining_qty = fields.Float(string="Remaining Quantity", digits='Product Unit of Measure')
    sale_line_id = fields.Many2one("sale.order.line", 'Line ID', invisible=True)
    partner_id = fields.Many2one('res.partner', 'Vendor', invisible=True)
    unit_price = fields.Float('Unit Price')
    order_id = fields.Many2one("sale.order", 'Order ID', invisible=True)
    # purchase_id = fields.Many2one("purchase.order", string="Purchase Order")

    def update_quantity(self):
        dict = {'line_split': True,
                'vendor_id': self.partner_id.id,
                'order_id': self.order_id.id if self.order_id else self.sale_line_id.order_id.id,
                'sequence_ref': ''
                }
        if self._context.get('add_to_buy'):
            route_id = self.env.ref('sale_distributor.route_warehouse0_mto_buy').id
            dict.update({'line_type': 'buy','route_id': route_id})
        elif self._context.get('dropship'):
            route_id = self.env.ref('stock_dropshipping.route_drop_shipping').id
            dict.update({'line_type': 'dropship','route_id': route_id})
        elif self._context.get('ship_from_here'):
            route_id = self.env.ref('stock.route_warehouse0_mto').id
            dict.update({'line_type': 'stock', 'route_id': route_id})
        elif self._context.get('allocate'):
            dict.update({'line_type': 'allocate', 'route_id': False})
        elif self._context.get('allocate_po'):
            route_id = self.env.ref('sale_distributor.route_warehouse0_mto_buy').id
            dict.update({'line_type': 'allocate_po','route_id': route_id})

        if not self.order_id:
            product_id = self.sale_line_id.product_id
            if self.sale_line_id.substitute_product_id:
                product_id = self.sale_line_id.substitute_product_id

            if self._context.get('allocate_po', False):
                for po_line in self.sale_line_id.inbound_stock_lines.filtered(lambda l: l.select_pol):
                    dict.update({'product_uom_qty': po_line.allocate_qty,
                        'parent_line_id': self.sale_line_id.id,
                        'vendor_price_unit': self.unit_price,
                        'product_id': product_id.id,
                        'allocated_pol_id': po_line.po_line_id.id,
                        'allocated_po_id': po_line.po_line_id.order_id.id,
                        })
                    split_line_id = self.sale_line_id.copy(dict)
            else:
                if self.qty <= 0.0:
                    raise ValidationError(_("Quantity must be greater than 0!"))
                elif self.qty > self.remaining_qty:
                    raise ValidationError(_("Quantity must not be greater than unprocess quantity %s!" % self.remaining_qty))
                
                dict.update({'product_uom_qty': self.qty,
                    'parent_line_id': self.sale_line_id.id,
                    'vendor_price_unit': self.unit_price,
                    'product_id': product_id.id,
                    })
                split_line_id = self.sale_line_id.copy(dict)
            self.sale_line_id.order_id._genrate_line_sequence()
        else:
            for line in self.order_id.order_line.filtered(lambda l : not l.is_delivery):
                vendor_price_unit = 0.0
                if self.partner_id.id == line.adi_partner_id.id:
                    vendor_price_unit = line.adi_actual_cost
                elif self.partner_id.id == line.nv_partner_id.id:
                    vendor_price_unit = line.nv_actual_cost
                elif self.partner_id.id == line.ss_partner_id.id:
                    vendor_price_unit = line.ss_actual_cost
                elif self.partner_id.id == line.sl_partner_id.id:
                    vendor_price_unit = line.sl_actual_cost
                elif self.partner_id.id == line.jne_partner_id.id:
                    vendor_price_unit = line.jne_actual_cost
                elif self.partner_id.id == line.bnr_partner_id.id:
                    vendor_price_unit = line.bnr_actual_cost
                elif self.partner_id.id == line.wr_partner_id.id:
                    vendor_price_unit = line.wr_actual_cost
                elif self.partner_id.id == line.dfm_partner_id.id:
                    vendor_price_unit = line.dfm_actual_cost
                elif self.partner_id.id == line.bks_partner_id.id:
                    vendor_price_unit = line.bks_actual_cost
                elif self.partner_id.id == line.partner_id.id:
                    vendor_price_unit = line.otv_cost
                product_id = line.product_id
                if line.substitute_product_id:
                    product_id = line.substitute_product_id
                dict.update({
                    'product_uom_qty': line.product_uom_qty,
                    'parent_line_id': line.id,
                    'vendor_price_unit': vendor_price_unit,
                    'product_id': product_id.id,
                    })
                split_line_id = line.copy(dict)
            self.order_id._genrate_line_sequence()
            self.order_id.action_confirm()
        return True
