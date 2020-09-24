# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, SUPERUSER_ID

class StockMove(models.Model):
    _inherit = "stock.move"

    def _prepare_procurement_values(self):
        """ Create or Merge PO if MTO route find
        Prepare specific key for moves or other componenets that will be created from a stock rule
        comming from a stock move. This method could be override in order to add other custom key that could
        be used in move/po creation.
        """
        values = super(StockMove, self)._prepare_procurement_values()
        values.update({
        		'sale_line_id': self.sale_line_id.id,
                'supplier_id': self.sale_line_id.vendor_id,
                'vendor_price_unit': self.sale_line_id.vendor_price_unit,
                })
        return values
