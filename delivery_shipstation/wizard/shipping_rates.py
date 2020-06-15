# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class StockPickingGetRate(models.TransientModel):
    _name = 'stock.picking.get.rate'
    _description = 'Get Rates'

    # batch_id = fields.Many2one('stock.picking.batch', string='Batch Transfer')

    def get_rates(self):
        # use active_ids to add picking line to the selected batch
        self.ensure_one()
        picking_ids = self.env.context.get('active_ids')
        return self.env['stock.picking'].browse(picking_ids).with_context(api_call=True).get_shipping_rates()
