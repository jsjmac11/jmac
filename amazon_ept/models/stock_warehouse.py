# -*- coding: utf-8 -*-
from odoo import api, models, fields


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    seller_id = fields.Many2one('amazon.seller.ept', string='Amazon Seller')
    fulfillment_center_ids = fields.One2many('amazon.fulfillment.center', 'warehouse_id',
                                             string='Fulfillment Centers')
    is_fba_warehouse = fields.Boolean("Is FBA Warehouse ?")
    unsellable_location_id = fields.Many2one('stock.location', string="Unsellable Location",
                                             help="Amazon unsellable location")

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        """
        Inherited for updating the VAT number of the partner as per the VAT configuration.
        @author: Maulik Barad on Date 13-Jan-2020.
        """
        if self.partner_id:
            self.update_partner_vat()

    @api.model
    def create(self, values):
        """
        Inherited for updating the VAT number of warehouse's partner as per the VAT configuration.
        @author: Maulik Barad on Date 13-Jan-2020.
        """
        result = super(StockWarehouse, self).create(values)

        if result.partner_id:
            result.update_partner_vat()
        return result

    def update_partner_vat(self):
        """
        Updates the VAT number of warehouse's partner as per the VAT configuration.
        @author: Maulik Barad on Date 13-Jan-2020.
        """
        vat_config = self.env["vat.config.ept"].search([("company_id", "=", self.company_id.id)])
        vat_config_line = vat_config.vat_config_line_ids.filtered(
            lambda x: x.country_id == self.partner_id.country_id)
        if vat_config_line and not self.partner_id.vat:
            self.partner_id.write({"vat": vat_config_line.vat})
        return True
