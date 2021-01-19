# -*- coding: utf-8 -*-
from odoo import models


class StockMove(models.Model):
    """Update values in procument for PO."""

    _inherit = "stock.move"

    def _prepare_procurement_values(self):
        """Create or Merge PO if MTO route find.

        Prepare specific key for moves or other componenets that will be
        created from a stock rule comming from a stock move.
        This method could be override in order to add other custom key that
        could be used in move/po creation.
        """
        values = super(StockMove, self)._prepare_procurement_values()
        values.update({
            'split_sale_line_id': self.sale_line_id,
            'supplier_id': self.sale_line_id.vendor_id,
            'vendor_price_unit': self.sale_line_id.vendor_price_unit,
        })
        return values


class StockPicking(models.Model):
    """Cancel sale order process line linked with stock Picking."""

    _inherit = "stock.picking"

    # def action_cancel(self):
    #     """Cancel Sale order line."""
    #     super(StockPicking, self).action_cancel()
    #     sol_ids = self.mapped('move_lines').mapped('sale_line_id')
    #     sol_ids.write({'po_cancel_note': '', 'active': False})
    #     return True
