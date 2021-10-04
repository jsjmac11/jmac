from odoo import models, fields


class amazon_return_reason_ept(models.Model):
    _name = "amazon.return.reason.ept"
    _description = "Amazon Return Reasons"

    name = fields.Char("Name", required=True)
    description = fields.Char("Description", help="Description")
    is_reimbursed = fields.Boolean("Is Reimbursed ?", default=False, help="Is Reimbursed?")
