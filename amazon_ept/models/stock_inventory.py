from odoo import models, fields

class stock_inventory(models.Model):
    _inherit = 'stock.inventory'

    amazon_instance_id = fields.Many2one('amazon.instance.ept', string='Instance')
    
    fba_live_stock_report_id = fields.Many2one('amazon.fba.live.stock.report.ept',
                                               "FBA Live Inventory Report")
    

