from odoo import models, fields, api, _
from odoo.exceptions import Warning

class inbound_shipment_plan_line(models.Model):
    _name = "inbound.shipment.plan.line"
    _description = 'inbound.shipment.plan.line'

    amazon_product_id = fields.Many2one('amazon.product.ept', string='Product',
                                        domain=[('fulfillment_by', '=', 'FBA')])
    quantity = fields.Float('Quantity')
    seller_sku = fields.Char(size=120, string='Seller SKU', related="amazon_product_id.seller_sku",
                             readonly=True)
    shipment_plan_id = fields.Many2one('inbound.shipment.plan.ept', string='Shipment Plan')
    odoo_shipment_id = fields.Many2one('amazon.inbound.shipment.ept', string='Shipment')
    fn_sku = fields.Char(size=120, string='Fulfillment Network SKU', readonly=True,
                         help="Provided by Amazon when we send shipment to Amazon")
    quantity_in_case = fields.Float(string="Quantity In Case", help="Amazon FBA: Quantity In Case.")
    received_qty = fields.Float("Received Quantity", default=0.0, copy=False,
                                help="Received Quantity")
    difference_qty = fields.Float("Difference Quantity", compute="_get_total_diffrence_qty",
                                  help="Difference Quantity")
    is_extra_line = fields.Boolean("Extra Line ?", default=False, help="Extra Line ?")

    def _get_total_diffrence_qty(self):
        for shipment_line in self:
            shipment_line.difference_qty = shipment_line.quantity - shipment_line.received_qty


    @api.constrains('amazon_product_id', 'shipment_plan_id', 'odoo_shipment_id')
    def _check_unique_line(self):
        # Modified By: Dhaval Sanghani [30-May-2020]
        # Add changes of use filtered instead of prepare domain and search method
        lines = False

        for shipment_line in self:

            if shipment_line.odoo_shipment_id:
                shipment_lines = shipment_line.odoo_shipment_id.mapped('odoo_shipment_line_ids')
                # domain = [('id', '<>', shipment_line.id), ('amazon_product_id', '=', shipment_line.amazon_product_id.id),
                #           ('shipment_plan_id', '=', shipment_line.shipment_plan_id.id),
                #           ('odoo_shipment_id', '=', shipment_line.odoo_shipment_id.id)]
            else:
                shipment_lines = shipment_line.shipment_plan_id.mapped('shipment_line_ids')
                # domain = [('id', '<>', shipment_line.id), ('amazon_product_id', '=', shipment_line.amazon_product_id.id),
                #           ('shipment_plan_id', '=', shipment_line.shipment_plan_id.id),
                #           ('odoo_shipment_id', '=', False)]
            # if shipment_line.search(domain):
            if shipment_lines:
                lines = shipment_lines.filtered(lambda line: line.id != shipment_line.id and
                                                             line.amazon_product_id.id == shipment_line.amazon_product_id.id)
            if lines:
                if not shipment_line._context.get('ignore_rule'):
                    raise Warning(_('Product %s line already exist in Shipping plan Line.' % (
                    shipment_line.amazon_product_id.seller_sku)))


    def create_update_plan_line(self, odoo_shipment, items):
        ship_plan = odoo_shipment.shipment_plan_id
        sku_qty_dict = []
        #sku_prep_details_dict = {}
        for item in items:
            sku = item.get('SellerSKU', {}).get('value', '')
            qty = float(item.get('Quantity', {}).get('value', 0.0))
            if odoo_shipment.shipment_plan_id.is_are_cases_required:
                quantity_in_case = float(item.get('QuantityInCase', {}).get('value', 0.0)) or qty
            else:
                quantity_in_case = 0
            fn_sku = item.get('FulfillmentNetworkSKU', {}).get('value', '')

            # Commented By: Dhaval Sanghani [29-05-2020]
            # Purpose: Use filtered() instead of Search()
            # line = self.search([('amazon_product_id.seller_sku', '=', sku),
            #                     ('shipment_plan_id', '=', ship_plan.id)])

            # Added By: Dhaval Sanghani [29-05-2020]
            line = ship_plan.shipment_line_ids.filtered(lambda shipment_line: shipment_line.seller_sku == sku)

            if line and len(line) > 1:
                # Commented By: Dhaval Sanghani [29-05-2020]
                # Purpose: Use filtered() instead of Search()
                # line = self.search([('amazon_product_id.seller_sku', '=', sku),
                #                     ('shipment_plan_id', '=', ship_plan.id),
                #                     ('odoo_shipment_id', '=', odoo_shipment.id)])

                # Added By: Dhaval Sanghani [29-05-2020]
                line = line.filtered(lambda shipment_line: shipment_line.odoo_shipment_id.id == odoo_shipment.id)
                if not line:
                    # Commented By: Dhaval Sanghani [29-05-2020]
                    # Purpose: Use filtered() instead of Search()
                    # line = self.search([('amazon_product_id.seller_sku', '=', sku),
                    #                     ('shipment_plan_id', '=', ship_plan.id),
                    #                     ('odoo_shipment_id', '=', False)])

                    # Added By: Dhaval Sanghani [29-05-2020]
                    line = line.filtered(lambda shipment_line: not shipment_line.odoo_shipment_id)
            if line:
                line = line[0] if len(line) > 1 else line
                vals = {'odoo_shipment_id': odoo_shipment.id, 'fn_sku': fn_sku,'quantity_in_case':line.quantity_in_case}
                amazon_product = line.amazon_product_id

                if line.quantity == qty:
                    line.write(vals)
                else:
                    qty_left = line.quantity - qty
                    vals.update({'quantity': qty})
                    line.write(vals)
                    # Modified Code
                    # Modified By: Dhaval Sanghani [29-May-2020]
                    # Purpose: Add fn_sku when create new shipment line
                    self.with_context({'ignore_rule': True}).create(
                        {'quantity': qty_left, 'amazon_product_id': amazon_product.id,
                         'shipment_plan_id': ship_plan.id, 'odoo_shipment_id': False,
                         'quantity_in_case': quantity_in_case, 'fn_sku': fn_sku})
                #sku_qty_dict.update({sku: [str(int(qty)), str(int(quantity_in_case))]})
                sku_qty_dict.append({'sku':sku,'quantity':int(qty),'quantity_in_case':int(quantity_in_case)})
        return sku_qty_dict
