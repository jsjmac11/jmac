from odoo import models, fields, api


class export_product_amazon_prepare_product_wizard(models.TransientModel):
    _name = 'amazon.product.wizard'
    _description = 'amazon.product.wizard'

    instance_id = fields.Many2one("amazon.instance.ept", "Instance")
    amazon_product_ids = fields.Many2many('amazon.product.ept', 'amazon_product_copy_rel',
                                          'wizard_id', 'amazon_product_id', "Amazon Product")
    from_instance_id = fields.Many2one("amazon.instance.ept", "From Instance")
    to_instance_id = fields.Many2one("amazon.instance.ept", "To Instance")
    copy_all_products = fields.Boolean("Copy All Products", default=True)

    """Added field by Dhruvi [14-11-2018] for export product as csv"""
    datas = fields.Binary('File')

    fulfillment_by = fields.Selection(
        [('FBM', 'Manufacturer Fulfillment Network'), ('FBA', 'Amazon Fulfillment Network')],
        string="Fulfillment By", default='FBM', help="Amazon Fulfillment Type")

    @api.onchange("from_instance_id")
    def on_change_instance(self):
        for record in self:
            record.to_instance_id = False

    def export_product_in_amazon(self):
        """
        This Method Relocates export amazon product listing in amazon.
        :return: This Method return Boolean(True/False).
        """
        amazon_product_obj = self.env['amazon.product.ept']
        active_ids = self._context.get('active_ids', [])
        amazon_product = amazon_product_obj.browse(active_ids)
        amazon_product_instance = amazon_product.mapped('instance_id')
        for instance in amazon_product_instance:
            amazon_products = amazon_product.filtered(lambda
                                                          l: l.instance_id.id == instance.id
                                                             and l.exported_to_amazon == True)
            if not amazon_products:
                continue
            amazon_products.export_product_amazon(instance)
        return True

    def update_stock_ept(self):
        """
        This Method relocates update stock of amazon.
        :return: This Method return boolean(True/False).
        """
        product_obj = self.env['amazon.product.ept']
        product_ids = self._context.get('active_ids')
        amazon_product = product_obj.browse(product_ids)
        amazon_product_instance = amazon_product.mapped('instance_id')
        for instance in amazon_product_instance:
            amazon_products = amazon_product.filtered(lambda
                                                          l: l.instance_id.id == instance.id
                                                             and l.fulfillment_by == 'FBM'
                                                             and l.exported_to_amazon == True)
            amazon_products and amazon_products.export_stock_levels(instance)
        return True

    def update_price(self):
        """
        This Method relocates update price of amazon.
        :return: This Method return boolean(True/False).
        """
        product_obj = self.env['amazon.product.ept']
        product_ids = self._context.get('active_ids')
        amazon_product = product_obj.browse(product_ids)
        amazon_product_instance = amazon_product.mapped('instance_id')
        for instance in amazon_product_instance:
            amazon_products = amazon_product.filtered(lambda
                                                          l: l.instance_id.id == instance.id
                                                             and l.exported_to_amazon == True)
            amazon_products.update_price(instance)
        return True

    def update_image(self):
        """
        This Method relocates update image of amazon.
        :return: This Method return boolean(True/False).
        """
        product_obj = self.env['amazon.product.ept']
        product_ids = self._context.get('active_ids')
        amazon_product = product_obj.browse(product_ids)
        amazon_product_instance = amazon_product.mapped('instance_id')

        for instance in amazon_product_instance:
            amazon_products = amazon_product.filtered(lambda
                                                          l: l.instance_id.id == instance.id
                                                             and l.fulfillment_by == 'FBM'
                                                             and l.exported_to_amazon == True)
            amazon_products.update_images(instance)
        return True
