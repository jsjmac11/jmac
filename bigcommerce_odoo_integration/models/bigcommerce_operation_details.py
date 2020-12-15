from odoo import models, fields, api
import datetime

class BigCommerceOperation(models.Model):
    _name = "bigcommerce.operation"
    _order = 'id desc'
    _inherit = ['mail.thread']

    name = fields.Char("Name")
    bigcommerce_operation = fields.Selection([('product_category', 'Product Category'),
                                              ('product', 'Product'),
                                              ('customer', 'Customer'),
                                              ('product_attribute','Product Attribute'),
                                              ('product_variant', 'Product Variant'),
                                              ('order', 'Order'),
                                              ('stock', 'Stock'),
                                              ('brand','Brand')
                                    # ('sale', 'Sales'),
                                    # ('delivery_order', 'Delivery Order'),
                                    # ('warehouse', 'Warehouse'),
                                    # ('other', 'Other')
], string="Bigcommerce Operation")
    bigcommerce_operation_type = fields.Selection([('export', 'Export'),
                                       ('import', 'Import'),
                                       ('update', 'Update'),
                                       ('delete', 'Cancel / Delete')], string="Bigcommerce Operation Type")
    warehouse_id = fields.Many2one("stock.warehouse", "Warehouse")
    company_id = fields.Many2one("res.company", "Company")
    operation_ids = fields.One2many("bigcommerce.operation.details", "operation_id",string="Operation")
    bigcommerce_store = fields.Many2one('bigcommerce.store.configuration',string="Bigcommerce Store")
    bigcommerce_message = fields.Char("Message")

    @api.model
    def create(self, vals):
        sequence = self.env.ref("bigcommerce_odoo_integration.seq_bigcommerce_operation_detail")
        name = sequence and sequence.next_by_id() or '/'
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        if type(vals) == dict:
            vals.update({'name': name, 'company_id': company_id})
        return super(BigCommerceOperation, self).create(vals)


class BigCommerceOperationDetail(models.Model):
    _name = "bigcommerce.operation.details"
    _rec_name = 'operation_id'
    _order = 'id desc'
    
    operation_id = fields.Many2one("bigcommerce.operation", string="BigCommerce Operation")
    bigcommerce_operation = fields.Selection([('product_category', 'Product Category'),
                                              ('product','Product'),
                                              ('customer', 'Customer'),
                                              ('product_attribute','Product Attribute'),
                                              ('product_variant', 'Product Variant'),
                                              ('order', 'Order'),
                                              ('stock', 'Stock'),
                                              ('brand','Brand')
                                    #('warehouse', 'Warehouse'),
                                    #('stock', 'Stock'),
                                    #('other', 'Other')
    ], string="Operation")
    bigcommerce_operation_type = fields.Selection([('export', 'Export'),
                                       ('import', 'Import'),
                                       ('update', 'Update'),
                                       ('delete', 'Cancel / Delete')], string="Bigcommerce operation Type")

    warehouse_id = fields.Many2one("stock.warehouse", "Warehouse", related="operation_id.warehouse_id")
    company_id = fields.Many2one("res.company", "Company")
    bigcommerce_request_message = fields.Char("Request Message")
    bigcommerce_response_message = fields.Char("Response Message")
    fault_operation = fields.Boolean("Fault Operation", default=False)
    process_message=fields.Char("Message")    
    
    @api.model
    def create(self, vals):
        if type(vals) == dict:
            operation_id = vals.get('operation_id')
            operation = operation_id and self.env['bigcommerce.operation'].browse(operation_id) or False
            company_id = operation and operation.company_id.id or self.env.user.company_id.id
            vals.update({'company_id': company_id})
        return super(BigCommerceOperationDetail, self).create(vals)
