# -*- coding: utf-8 -*-
from odoo import models, fields


class Rating(models.Model):
    _inherit = "rating.rating"

    amz_instance_id = fields.Many2one('amazon.instance.ept', string='Amazon Instance',
                                      help="Amazon Instance")
    amz_fulfillment_by = fields.Selection(
        [('FBA', 'Amazon Fulfillment Network'), ('FBM', 'Merchant Fullfillment Network')],
        string="Fulfillment By", help="Fulfillment Center by Amazon or Merchant")
    amz_rating_report_id = fields.Many2one("rating.report.history",
                                           "Amazon Rating Report History")
    amz_rating_submitted_date = fields.Date("Amazon Rating Submitted Date", readonly=True)
    
    publisher_comment = fields.Text("Publisher Comment")
    def action_open_rated_instance_object(self):
        return {
            'name': 'Amazon Rating Instance',
            'type': 'ir.actions.act_window',
            'res_model': 'amazon.instance.ept',
            'domain': "[('id', 'in', " + str(self.amz_instance_id.ids) + " )]",
            'view_mode': 'tree,form',
        }

    def action_open_rated_seller_object(self):
        return {
            'name': 'Amazon Rating Seller',
            'type': 'ir.actions.act_window',
            'res_model': 'amazon.seller.ept',
            'domain': "[('id', 'in', " + str(self.amz_instance_id.seller_id.ids) + " )]",
            'view_mode': 'tree,form',
        }
