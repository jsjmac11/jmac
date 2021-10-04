# -*- coding: utf-8 -*-
from odoo import fields, api, models

class AmazonFulfillmentCenter(models.Model):
    _name = "amazon.fulfillment.country.rel"
    _description = 'amazon.fulfillment.country.rel'

    fulfillment_code = fields.Char(string="Fulfillment Center Code")
    country_id = fields.Many2one('res.country', string="Fulfillment Id")

    @api.model
    def load_fulfillment_code(self, country,seller_id,warehouse_id):
        fulfillment_center_obj = self.env['amazon.fulfillment.center']
        fulfillment_codes = country.fulfillment_code_ids
        for fulfillment in fulfillment_codes:
            fulfillment_center_obj.create(
                {'center_code':fulfillment.fulfillment_code,
                 'seller_id':seller_id,
                 'warehouse_id':warehouse_id
                 })
        return True

class ResCountry(models.Model):
    _inherit = "res.country"

    fulfillment_code_ids = fields.One2many('amazon.fulfillment.country.rel', 'country_id',
                                           string="Fulfillment Center code")
