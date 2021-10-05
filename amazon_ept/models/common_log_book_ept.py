from odoo import models, fields

class CommonLogBookEpt(models.Model):
    _inherit = 'common.log.book.ept'

    fbm_sales_order_report_id = fields.Many2one('fbm.sale.order.report.ept',
                                                string="Sale Order Report")
    attachment_id = fields.Many2one('ir.attachment', string='Attachment')
