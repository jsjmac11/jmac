# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StockPickingGetRate(models.TransientModel):
    _name = 'stock.picking.get.rate'
    _description = 'Get Rates'

    # batch_id = fields.Many2one('stock.picking.batch', string='Batch Transfer')

    def get_rates(self):
        # use active_ids to add picking line to the selected batch
        self.ensure_one()
        picking_ids = self.env.context.get('active_ids')
        picking_objs = self.env['stock.picking'].browse(picking_ids)
        pick_ids = picking_objs.filtered(lambda p: p.state != 'assigned')
        if pick_ids:
            raise ValidationError(_("Please select only 'Ready' delivery orders!"))
        return picking_objs.with_context(api_call=True).get_shipping_rates()
