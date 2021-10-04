from odoo import models, fields, api


class stock_quant_package(models.Model):
    _inherit = 'stock.quant.package'

    @api.model
    def default_get(self, fields):
        """
        Use: Used for Add domain in Amazon Product field while enter Carton Information,
        display only Amazon Products which are in Shipment Lines
        @:param: self -> stock.quant.package, fields -> {}
        @:return: {} => dict
        ----------------------------------------------
        Added by: Dhaval Sanghani @Emipro Technologies
        Added on: 30-May-2020
        """
        res = super(stock_quant_package, self).default_get(fields)
        active_id = self._context.get('inbound_shipment', False)

        if active_id:
            inbound_shipment = self.env['amazon.inbound.shipment.ept'].browse(active_id)

            product_ids = inbound_shipment and self.get_amazon_products(inbound_shipment) or []

            res.update({'amazon_product_ids': product_ids})
        return res
    
    def get_products(self):
        # Added By: Dhaval Sanghani [30-May-2020]
        res = {}
        for record in self:

            shipment = record.partnered_ltl_shipment_id \
                if record.partnered_ltl_shipment_id else record.partnered_small_parcel_shipment_id

            if shipment:
                record.amazon_product_ids = record.get_amazon_products(shipment)
        return res

        # Comment By Dhaval Sanghani [30-May-2020]
        # Purpose: No Need of use
        # product_ids = []
        # for line in self.partnered_small_parcel_shipment_id.odoo_shipment_line_ids:
        #     product_ids.append(line.amazon_product_id.id)
        # for line in self.partnered_ltl_shipment_id.odoo_shipment_line_ids:
        #     product_ids.append(line.amazon_product_id.id)
        # self.amazon_product_ids = product_ids

    def get_amazon_products(self, inbound_shipment):
        """
        Use: Return Amazon Products which are in Shipment Lines
        @:param: self -> stock.quant.package, inbound_shipment -> amazon.inbound.shipment.ept record
        @:return:
        ----------------------------------------------
        Added by: Dhaval Sanghani @Emipro Technologies
        Added on: 30-May-2020
        """
        product_ids = inbound_shipment.mapped('odoo_shipment_line_ids').mapped('amazon_product_id').ids
        return product_ids
    
    box_no = fields.Char("Box No")
    carton_info_ids = fields.One2many("amazon.carton.content.info.ept", "package_id",
                                      string="Carton Info")
    amazon_product_ids = fields.One2many("amazon.product.ept", compute="get_products")
    partnered_small_parcel_shipment_id = fields.Many2one("amazon.inbound.shipment.ept",
                                                         "Small Parcel Shipment")
    is_update_inbound_carton_contents = fields.Boolean("Is Update Inbound Carton Contents",
                                                       default=False, copy=False)
    partnered_ltl_shipment_id = fields.Many2one("amazon.inbound.shipment.ept", "LTL Shipment")
    package_status = fields.Selection([('SHIPPED', 'SHIPPED'),
                                       ('IN_TRANSIT', 'IN_TRANSIT'),
                                       ('DELIVERED', 'DELIVERED'),
                                       ('CHECKED_IN', 'CHECKED_IN'),
                                       ('RECEIVING', 'RECEIVING'),
                                       ('CLOSED', 'CLOSED')], string='Package Status')
    weight_unit = fields.Selection([('pounds', 'Pounds'), ('kilograms', 'Kilograms'), ],
                                   string='Weight Unit')
    weight_value = fields.Float('Weight Value')
    ul_id = fields.Many2one('product.ul.ept', string="Logistic Unit")
    is_stacked = fields.Boolean('Is Stacked')

    # Added By: Dhaval Sanghani [26-Jun-2020]
    # Purpose: Manage Expiry Date Box Wise
    box_expiration_date = fields.Date("Box Expiration Date", copy=False)
