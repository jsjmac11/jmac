from odoo import models, fields, api, _


class CommonLogLineEpt(models.Model):
    _inherit = "common.log.lines.ept"

    order_queue_data_id = fields.Many2one('shipped.order.data.queue.ept', string='Shipped Order Data Queue')
    fulfillment_by = fields.Selection(
            [('FBA', 'Amazon Fulfillment Network'), ('FBM', 'Merchant Fullfillment Network')],
            string="Fulfillment By", help="Fulfillment Center by Amazon or Merchant")
    mismatch_details = fields.Boolean(string='Mismatch Detail', help="Mismatch Detail of process order")

    def amazon_create_common_log_line_ept(self, message, model_id, res_id, log_rec):
        """
            Creates log line.
            :param message: str
            :param model_id: int
            :param res_id: int
            :param log_rec: common.log.book.ept
            :return: common.log.lines.ept
        """
        transaction_vals = {'message': message,
                            'model_id': model_id,
                            'res_id': res_id or False,
                            'log_line_id': log_rec.id or False}
        log_line = self.create(transaction_vals)
        return log_line
