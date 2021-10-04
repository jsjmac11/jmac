from odoo import models, fields, api


class amazon_fulfillment_center(models.Model):
    _name = "amazon.fulfillment.center"
    _description = 'amazon.fulfillment.center'
    _rec_name = 'center_code'

    @api.depends('warehouse_id', 'warehouse_id.seller_id')
    def _get_seller_id(self):
        if self.warehouse_id and self.warehouse_id.seller_id:
            self.seller_id = self.warehouse_id.seller_id.id


    center_code = fields.Char(size=50, string='Fulfillment Center Code', required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    seller_id = fields.Many2one('amazon.seller.ept', string='Amazon Seller', compute="_get_seller_id", store=True,
                                readonly=True)

    _sql_constraints = [('fulfillment_center_unique_constraint', 'unique(seller_id,center_code)',
                         "Fulfillment center must be unique by seller.")]

    @api.model
    def _map_amazon_fulfillment_centers_warehouse(self):
        """
        Map New Fulfillment centers to amazon warehouses while upgrading app.
        :return:
        """
        fba_wh_ids = self.env['stock.warehouse'].search([]).filtered(lambda l: l.is_fba_warehouse)
        for fba_wh in fba_wh_ids:
            wh_country = fba_wh.partner_id and fba_wh.partner_id.country_id or \
                         fba_wh.company_id and fba_wh.company_id.partner_id and fba_wh.company_id.partner_id.country_id
            amz_seller = fba_wh.seller_id.id
            fc_codes = self.search([('warehouse_id', '=', fba_wh.id), ('seller_id', '=', amz_seller)]).mapped(
                'center_code')
            if wh_country:
                fulfillment_codes = wh_country.fulfillment_code_ids.filtered(
                    lambda l: l.fulfillment_code not in fc_codes).mapped('fulfillment_code')
                for fulfillment in fulfillment_codes:
                    self.create({
                        'center_code': fulfillment,
                        'seller_id': amz_seller,
                        'warehouse_id': fba_wh.id
                    })
