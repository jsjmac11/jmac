from odoo import models, fields, api


class ShippedOrderDataQueue(models.Model):
    _name = "shipped.order.data.queue.ept"
    _description = 'Shipped Order Data Queue Ept'
    _order = "create_date desc"

    def _compute_queue_line_record(self):
        """
        This is used for count of total record of product queue line.
        :return: count
        """
        for order_queue in self:
            order_queue.queue_line_total_record = len(order_queue.shipped_order_data_queue_lines)
            order_queue.queue_line_draft_record = len(
                order_queue.shipped_order_data_queue_lines.filtered(lambda x: x.state == 'draft'))
            order_queue.queue_line_fail_record = len(
                order_queue.shipped_order_data_queue_lines.filtered(lambda x: x.state == 'failed'))
            order_queue.queue_line_done_record = len(
                order_queue.shipped_order_data_queue_lines.filtered(lambda x: x.state == 'done'))

    def get_log_count(self):
        """
        Find all stock moves associated with this report
        :return:
        """
        model_id = self.env['ir.model']._get('shipped.order.data.queue.ept').id
        log_obj = self.env['common.log.book.ept']
        self.log_count = log_obj.search_count([('res_id', '=', self.id), ('model_id', '=', model_id)])

    name = fields.Char(size=120, string='Name')
    amz_seller_id = fields.Many2one('amazon.seller.ept', string='Amazon Seller', help="Unique Amazon Seller name")
    state = fields.Selection(
        [('draft', 'Draft'), ('partially_completed', 'Partially Completed'), ('completed', 'Completed')],
        default='draft')
    shipped_order_data_queue_lines = fields.One2many('shipped.order.data.queue.line.ept', 'shipped_order_data_queue_id',
                                                     string="Shipped Order Queue Lines")
    log_lines = fields.One2many('common.log.lines.ept', 'order_queue_data_id',
                                compute="_compute_log_lines", string="Log Lines")
    queue_line_total_record = fields.Integer(string='Total Records', compute='_compute_queue_line_record')
    queue_line_draft_record = fields.Integer(string='Draft Records', compute='_compute_queue_line_record')
    queue_line_fail_record = fields.Integer(string='Fail Records', compute='_compute_queue_line_record')
    queue_line_done_record = fields.Integer(string='Done Records', compute='_compute_queue_line_record')
    log_count = fields.Integer(compute="get_log_count", string="Move Count",
                               help="Count number of created Stock Move", store=False)

    @api.model
    def create(self, vals):
        """
        This method used to create a sequence for Shipped Order data.
        :param vals: value from base method
        :return: True
        """
        seq = self.env['ir.sequence'].next_by_code('fbm_shipped_order_data_queue_ept_sequence') or '/'
        vals['name'] = seq
        return super(ShippedOrderDataQueue, self).create(vals)

    def action_product_queue_record_count(self):
        """
        This method used to display the product queue records.
        """
        return True

    def _compute_log_lines(self):
        """
        List Shipped Orders Logs
        @author: Twinkal Chandarana
        :return:
        """
        for queue in self:
            log_book_obj = self.env['common.log.book.ept']
            model_id = self.env['ir.model']._get('shipped.order.data.queue.ept').id
            domain = [('res_id', '=', queue.id), ('model_id', '=', model_id)]
            log_book_id = log_book_obj.search(domain)
            queue.log_lines = log_book_id and log_book_id.log_lines.ids or False

    def process_orders(self):
        """
        This method is process the orders that are in queue.
        :return:
        """
        sale_order_obj = self.env['sale.order']
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        common_log_book_obj = self.env['common.log.book.ept']
        if not self:
            datas = self.search([('state', '=', 'draft')])
        else:
            datas = self
        if datas:
            seller_ids = datas.mapped('amz_seller_id')
            for seller_id in seller_ids:
                cron_id = self.env.ref('amazon_ept.%s%d' % ("ir_cron_process_amazon_unshipped_orders_seller_",
                                                            seller_id.id), raise_if_not_found=False)
                if cron_id and cron_id.sudo().active:
                    res = cron_id.sudo().try_cron_lock()
                    if res and res.get('reason'):
                        return True
        for data_queue in datas:
            log_book = common_log_book_obj.search(
                [('model_id', '=', self.env['ir.model']._get('shipped.order.data.queue.ept').id),
                 ('res_id', '=', data_queue.id)])
            if not log_book:
                log_book_vals = {
                    'type': 'import',
                    'model_id': self.env['ir.model']._get('shipped.order.data.queue.ept').id,
                    'res_id': data_queue.id,
                    'module': 'amazon_ept',
                    'active': True
                }
                log_book = common_log_book_obj.create(log_book_vals)
            sale_order_obj.amz_create_sales_order(data_queue, account, dbuuid, log_book)
            status = data_queue.shipped_order_data_queue_lines.filtered(lambda x: x.state != 'done')
            if status:
                # Delete Done data queue lines for compliance of Amazon Rules
                data_queue.shipped_order_data_queue_lines.filtered(
                        lambda x: x.state == 'done').unlink()
                data_queue.write({'state': 'partially_completed'})
            else:
                # data_queue.write({'state': 'completed'})
                data_queue.unlink()
            self._cr.commit()
        return True
