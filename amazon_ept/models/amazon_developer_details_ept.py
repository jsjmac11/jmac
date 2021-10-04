from odoo import models, fields


class AmazonDeveloperDetailsEpt(models.Model):
    _name = "amazon.developer.details.ept"
    _description = 'amazon developer details ept'
    _rec_name = 'developer_id'

    developer_id = fields.Char('Developer ID')
    developer_name = fields.Char('Developer Name')
    developer_country_id = fields.Many2one('res.country', string='Developer Country')
