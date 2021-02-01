# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class NotificationMessage(models.TransientModel):
    _name = 'notification.message'
    _description = 'Notification Message'

    message = fields.Char("Message", readonly=True)
    qty = fields.Float(string="Quantity", digits='Product Unit of Measure')
    remaining_qty = fields.Float(
        string="Remaining Quantity", digits='Product Unit of Measure')
    sale_line_id = fields.Many2one(
        "sale.order.line", 'Line ID', invisible=True)
    partner_id = fields.Many2one('res.partner', 'Vendor', invisible=True)
    unit_price = fields.Float('Unit Price')
    order_id = fields.Many2one("sale.order", 'Order ID', invisible=True)
    purchase_id = fields.Many2one("purchase.order", string="Purchase Order #")
    purchase_line_id = fields.Many2one(
        "purchase.order.line", string="Purchase Order Line #")
    note = fields.Text("Note")
    user_id = fields.Many2one("res.users", string="User")
    item_note = fields.Text("Item Note")
    # po_so_line = fields.One2many("purchase.allocate.line", "notification_id",
    #                              string="Allocate Line")

    def update_quantity(self):
        dict = {'line_split': True,
                'vendor_id': self.partner_id.id,
                'order_id': self.order_id.id if self.order_id else self.sale_line_id.order_id.id,
                'sequence_ref': ''
                }
        if self._context.get('add_to_buy'):
            route_id = self.env.ref(
                'sale_distributor.route_warehouse0_mto_buy').id
            dict.update({'line_type': 'buy', 'route_id': route_id})
        elif self._context.get('dropship'):
            route_id = self.env.ref(
                'stock_dropshipping.route_drop_shipping').id
            dict.update({'line_type': 'dropship', 'route_id': route_id})
        elif self._context.get('ship_from_here'):
            route_id = self.env.ref('stock.route_warehouse0_mto').id
            dict.update({'line_type': 'stock', 'route_id': route_id})
        elif self._context.get('allocate'):
            dict.update({'line_type': 'allocate', 'route_id': False})
        elif self._context.get('allocate_po'):
            route_id = self.env.ref(
                'sale_distributor.route_warehouse0_mto_buy').id
            dict.update({'line_type': 'allocate_po', 'route_id': route_id})

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
                if (self._context.get('add_to_buy') or self._context.get('dropship')) and self.unit_price <= 0.0:
                    raise ValidationError(
                        _("Vendor price must be greater than 0!"))
                if self.qty <= 0.0:
                    raise ValidationError(
                        _("Quantity must be greater than 0!"))
                elif self.qty > self.remaining_qty:
                    raise ValidationError(
                        _("Quantity must not be greater than unprocess quantity %s!" % self.remaining_qty))
                order_qty = self.qty
                # Multipier Quantity based on Pack selected
                if self.sale_line_id.product_pack_id:
                    order_qty = self.qty * self.sale_line_id.product_pack_id.quantity
                dict.update({'product_uom_qty': order_qty,
                             'parent_line_id': self.sale_line_id.id,
                             'vendor_price_unit': self.unit_price,
                             'product_id': product_id.id,
                             'item_note': self.item_note,
                             })
                split_line_id = self.sale_line_id.copy(dict)
            self.sale_line_id.order_id._genrate_line_sequence()
        else:
            for line in self.order_id.order_line.filtered(lambda l: not l.is_delivery):
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
                    'item_note': self.item_note,
                })
                split_line_id = line.copy(dict)
            self.order_id._genrate_line_sequence()
            self.order_id.action_confirm()
        return True

    def submit(self):
        if self._context.get('review', False):
            self.order_id.message_post(body=_(
                u'Quote assign to <b>%s</b> <br/> <b>Note :</b> %s' % (self.user_id.name, self.note)))
            self.order_id.write({'state': 'review'})
        if self._context.get('reject', False):
            self.order_id.message_post(
                body=_(u'<b>Quote reject reson :</b> %s' % self.note))
            self.order_id.write({'state': 'new'})
        return True

    def reallocate_so_in_po(self):
        if self.qty == 0.0:
            raise ValidationError(("You cannot process zero quantity!"))
        """For re-allcate sale order in purchase line."""
        if self.sale_line_id and self.qty > self.remaining_qty:
            raise ValidationError(
                _("Cannot allocate more quantity!"))
        purchase_line = self.env['purchase.order.line']
        if self.sale_line_id:
            # For all conditions.
            inventory_qty = self.sale_line_id.product_uom_qty - self.qty
            # if self.qty < self.purchase_line_id.product_qty:
            po_inventory_qty = self.purchase_line_id.product_qty - self.qty
            if self.qty > self.sale_line_id.product_uom_qty:
                raise ValidationError(
                _("Cannot allocate more quantity!"))
            if self.purchase_line_id.sale_line_id and (self.sale_line_id.id != self.purchase_line_id.sale_line_id.id):
                """
                Remove Old sale line from POL and cancel stock move
                and update unprocess Qty in Parent SOL.
                """
                so_move_id = self.purchase_line_id.sale_line_id.move_ids.filtered(
                    lambda l: l.picking_id.state not in ('done', 'cancel'))
                so_move_id._action_cancel()
                self.purchase_line_id.sale_line_id.write({'active': False})
                self.purchase_line_id.sale_line_id.order_id._compute_is_process_qty()
            # if (not self.purchase_line_id.sale_line_id.id and self.sale_line_id.id) or (self.sale_line_id.id == self.purchase_line_id.sale_line_id.id):
            
            """Allocate Po sale line updation in qty."""
            if self.sale_line_id.line_type == 'allocate_po':
                """Update sale order line and stock move qty."""
                if inventory_qty:
                    self.sale_line_id.write({'product_uom_qty': self.qty})
                if self.sale_line_id.state == 'sale':
                    if inventory_qty:
                        so_move_id = self.sale_line_id.move_ids.filtered(lambda l: l.picking_id.state not in ('done','cancel'))
                        so_move_id.product_uom_qty = inventory_qty
                        # Update OLD PO qty
                        if self.sale_line_id.id != self.purchase_line_id.sale_line_id.id:
                            self.sale_line_id.allocated_pol_id.product_qty = self.qty
                            st_move_id = self.sale_line_id.allocated_pol_id.move_ids.filtered(lambda l: l.picking_id.state not in ('done','cancel'))
                            st_move_id.product_uom_qty = self.qty
                            self.sale_line_id.allocated_pol_id.copy({'product_qty': inventory_qty,
                                                                     'sale_line_id': False,
                                                                     'line_split':True})
                        # self.sale_line_id.order_id._compute_unprocess_qty()
                    else:
                        if self.sale_line_id.id != self.purchase_line_id.sale_line_id.id:
                            self.sale_line_id.allocated_pol_id.sale_line_id = False
                            self.sale_line_id.allocated_pol_id.action_cancel_pol()
                    
                        
                """Update current purchase line qty and stock move."""
                self.purchase_line_id.product_qty = self.qty
                if (not self.purchase_line_id.sale_line_id.id and self.sale_line_id.id) or (self.purchase_line_id.sale_line_id.id != self.sale_line_id.id):
                    self.sale_line_id.write({'allocated_pol_id': self.purchase_line_id.id,
                                             'allocated_po_id': self.purchase_id.id})
                    # self.sale_line_id.allocated_pol_id = self.purchase_line_id.id
                    self.purchase_line_id.sale_line_id = self.sale_line_id.id
                if self.purchase_line_id.state == 'purchase':
                    st_move_id = self.purchase_line_id.move_ids.filtered(lambda l: l.picking_id.state not in ('done','cancel'))
                    st_move_id.product_uom_qty = self.qty
                
                if po_inventory_qty:
                    """Checking and update remaining qty as inventory qty."""
                    inventory_line = self.purchase_id.split_line.filtered(
                        lambda l: l.product_id == self.purchase_line_id.product_id and not l.sale_line_id)
                    if inventory_line: # and self.purchase_line_id.state in ('draft', 'sent')
                        inventory_line.product_qty = po_inventory_qty
                        if self.purchase_line_id.state == 'purchase':
                            inv_st_move_id = inventory_line.move_ids.filtered(lambda l: l.picking_id.state not in ('done','cancel'))
                            inv_st_move_id.product_uom_qty = po_inventory_qty
                    else:
                        self.purchase_line_id.copy({'product_qty': po_inventory_qty,
                                                    'sale_line_id': False,
                                                    'line_split': True})
                    

            elif self.sale_line_id.line_type in ('buy', 'dropship'):
                self.sale_line_id.update({'product_uom_qty': self.qty})
                if self.sale_line_id.order_id.picking_ids and self.sale_line_id.line_type == 'buy':
                    move_line = self.sale_line_id.order_id.picking_ids.mapped('move_lines')
                    move_line.filtered(lambda l: l.sale_line_id.id == self.sale_line_id.id and l.picking_id.state not in ('done','cancel'))
                    move_line.product_uom_qty = self.qty

                self.purchase_line_id.product_qty = self.qty
                st_move_id = self.purchase_line_id.move_ids.filtered(
                    lambda l: l.picking_id.state not in ('done', 'cancel'))
                if st_move_id:
                    st_move_id.product_uom_qty = self.qty

                if self.sale_line_id.state == 'sale':
                    # if inventory_qty:
                    #     # so_move_id = self.sale_line_id.move_ids.filtered(lambda l: l.picking_id.state not in ('done','cancel'))
                    #     # so_move_id.product_uom_qty = inventory_qty
                    #     # Update OLD PO qty
                    #     if self.sale_line_id.id != self.purchase_line_id.sale_line_id.id:
                    #         purchase_lines = self.env['purchase.order.line'].search(
                    #                             [('sale_line_id', '=', self.sale_line_id.id),
                    #                              ('id', '!=', self.purchase_line_id.id),
                    #                             ])

                    #         purchase_lines.product_qty = self.qty
                    #         if purchase_lines.state == 'purchase':
                    #             st_move_id = purchase_lines.move_ids.filtered(lambda l: l.picking_id.state not in ('done','cancel'))
                    #             st_move_id.product_uom_qty = self.qty
                    #         purchase_lines.copy({'product_qty': inventory_qty,
                    #                                                  'sale_line_id': False,
                    #                                                  'line_split':True})
                    # else:
                    if self.sale_line_id.id != self.purchase_line_id.sale_line_id.id:
                        purchase_lines = self.env['purchase.order.line'].search(
                                        [('sale_line_id', '=', self.sale_line_id.id),
                                         ('id', '!=', self.purchase_line_id.id),
                                        ])
                        purchase_lines.sale_line_id = False
                        purchase_lines.action_cancel_pol()
                if (not self.purchase_line_id.sale_line_id.id and self.sale_line_id.id) or (self.purchase_line_id.sale_line_id.id != self.sale_line_id.id):
                # if not self.purchase_line_id.sale_line_id.id and self.sale_line_id.id:
                    self.purchase_line_id.sale_line_id = self.sale_line_id.id
                if po_inventory_qty:
                    """Checking and update remaining qty as inventory qty."""
                    inventory_line = self.purchase_id.split_line.filtered(
                        lambda l: l.product_id == self.purchase_line_id.product_id and not l.sale_line_id)
                    if inventory_line: # and self.purchase_line_id.state in ('draft', 'sent')
                        inventory_line.product_qty = po_inventory_qty
                        if self.purchase_line_id.state == 'purchase':
                            inv_st_move_id = inventory_line.move_ids.filtered(lambda l: l.picking_id.state not in ('done','cancel'))
                            inv_st_move_id.product_uom_qty = po_inventory_qty
                    else:
                        self.purchase_line_id.copy({'product_qty': po_inventory_qty,
                                                    'sale_line_id': False,
                                                    'line_split': True})

                # if inventory_qty:
                #     if self.purchase_line_id.state in ('draft', 'sent', 'cancel'):
                #         inventory_qty = self.purchase_line_id.parent_line_id.product_qty - inventory_qty
                #         self._cr.execute("""update purchase_order_line
                #             set product_qty = %s where id = %s """ % (inventory_qty, self.purchase_line_id.parent_line_id.id))
                #     else:
                #         self.purchase_line_id.copy({'product_qty': inventory_qty,
                #                                     'sale_line_id': False})
            self.sale_line_id.order_id._compute_is_process_qty()
        else:
            if self.purchase_line_id.sale_line_id:
                so_move_id = self.purchase_line_id.sale_line_id.move_ids.filtered(
                    lambda l: l.picking_id.state not in ('done', 'cancel'))
                so_move_id._action_cancel()
                self.purchase_line_id.sale_line_id.write({'active': False})
                self.purchase_line_id.sale_line_id.order_id._compute_is_process_qty()
                self.purchase_line_id.sale_line_id = False
                st_move_id = self.purchase_line_id.move_ids.filtered(lambda l: l.picking_id.state not in ('done','cancel'))
                st_move_id.sale_line_id = False
            diff_qty = self.purchase_line_id.product_qty - self.qty
            inventory_qty = self.purchase_line_id.parent_line_id.product_qty - diff_qty
            self._cr.execute("""update purchase_order_line
                set product_qty = %s where id = %s """ % (inventory_qty, self.purchase_line_id.parent_line_id.id))
            """Update current purchase line qty and stock move."""
            self.purchase_line_id.product_qty = self.qty
            if self.purchase_line_id.state == 'purchase':
                st_move_id = self.purchase_line_id.move_ids.filtered(lambda l: l.picking_id.state not in ('done','cancel'))
                st_move_id.product_uom_qty = self.qty
                        
            # elif self.sale_line_id.id != self.purchase_line_id.sale_line_id.id:
                # st_move_id = self.purchase_line_id.move_ids.filtered(
                #     lambda l: l.picking_id.state not in ('done', 'cancel'))
                # st_move_id._action_cancel()
                # if self.qty == self.purchase_line_id.sale_line_id.product_uom_qty:
                    


                # if self.sale_line_id.line_type == 'allocate_po':
            #         move_id = self.env['stock.move'].search([('purchase_line_id', '=', self.sale_line_id.id)])
            #         sol_move_id = self.env['stock.move'].search(
            #             [('sale_line_id', '=', sol.id), ('picking_code', '=', 'outgoing')])
            #         sol_in_move_id = self.env['stock.move'].search(
            #             [('sale_line_id', '=', sol.id), ('picking_code', '=', 'incoming')])
            #         if move_id:
            #             if diff_qty:
            #                 move_id.product_uom_qty = diff_qty
            #                 sol_in_move_id.write(
            #                     {'move_dest_ids': [(6, 0, [sol_move_id.id])]})
            #             else:
            #                 move_id.sale_line_id = sol.id
            #                 # move_id.write({'move_dest_ids': [(4, sol_move_id.id, False)]})
            #                 move_id.write(
            #                     {'move_dest_ids': [(6, 0, [sol_move_id.id])]})



            #         po_st_move_ids = self.env['stock.move'].search(
            #             [('purchase_line_id', '=', self.sale_line_id.allocated_pol_id.id)], limit=1)
            #         po_st_move_ids.sale_line_id = False
            #         self.sale_line_id.allocated_pol_id.sale_line_id = False
            #         self.sale_line_id.update({'product_uom_qty': self.qty,
            #                                   'allocated_pol_id': self.name.id})
            #         self.purchase_line_id.sale_line_id = self.sale_line_id.id
            #         st_move_ids = self.env['stock.move'].search(
            #             [('purchase_line_id', '=', self.purchase_line_id.id)], limit=1)
            #         st_move_ids.sale_line_id = self.sale_line_id.id
            #     if self.sale_line_id.line_type == 'buy':
            #         pol_id = self.env['purchase.order.line'].search([('sale_line_id','=',self.sale_line_id.id)], limit=1)
            #         pol_id.sale_line_id = False
            #         pol_id.action_cancel_pol()
            #         self.sale_line_id.update({'product_uom_qty': line.qty})
            #         self.purchase_line_id.sale_line_id = self.sale_line_id.id
            #         po_st_move_ids = self.env['stock.move'].search(
            #             [('purchase_line_id', '=', self.id)])
            #         po_st_move_ids.sale_line_id = self.sale_line_id.id
        return True


# class PurchaseAllocateLine(models.TransientModel):
#     """Allocate SOL to POL."""

#     _name = "purchase.allocate.line"
#     _description = "Allocate Sale order to PO line"

#     name = fields.Many2one("purchase.order.line", string="Purchase Line")
#     qty = fields.Float("Quantity")
#     notification_id = fields.Many2one("notification.message",
#                                       string="Notification")
#     sale_line_id = fields.Many2one("sale.order.line", string="Sale Line #")
#     sale_id = fields.Many2one("sale.order", string="Sale order #")
