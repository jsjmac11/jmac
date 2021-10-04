from odoo import models, fields

class AmazonTransactionType(models.Model):
    _name = "amazon.transaction.type"
    _description = 'amazon.transaction.type'

    name = fields.Char(size=256, string='Name')
    amazon_code = fields.Char(size=256, string='Transaction Code')

    is_reimbursement = fields.Boolean("REIMBURSEMENT ?", default=False)

    _sql_constraints = [('amazon_transaction_type_unique_constraint',
                         'unique(amazon_code)',
                         "Amazon Transaction type must be unique by Amazon Code.")]