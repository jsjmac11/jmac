from odoo import models, fields


class ShippedOrderDataQueueLine(models.Model):
    _name = "shipped.order.data.queue.line.ept"
    _description = 'Shipped Order Data Queue Line Ept'

    amz_instance_id = fields.Many2one('amazon.instance.ept', string='Amazon Instance', help="Amazon Instance")
    order_id = fields.Char(string='Order Id')
    order_data_id = fields.Char(string='Order Data Id')
    state = fields.Selection([('draft', 'Draft'), ('failed', 'Failed'), ('done', 'Done')], default='draft')
    last_process_date = fields.Datetime('Last Process Date', readonly=True)
    shipped_order_data_queue_id = fields.Many2one('shipped.order.data.queue.ept', string='Shipped Order Data Queue',
                                                  required=True, ondelete='cascade', copy=False)
