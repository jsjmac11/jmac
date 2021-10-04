from odoo import models,fields

class amazon_adjustment_reason_code(models.Model):
    _name="amazon.adjustment.reason.code"
    _description = "amazon.adjustment.reason.code"
    
    name=fields.Char("Name",required=True)
    type=fields.Selection([('-','-'),('+','+')])
    description=fields.Char("Description")
    long_description=fields.Text("Long Description")
    group_id=fields.Many2one("amazon.adjustment.reason.group",string="Group")
    counter_part_id=fields.Many2one("amazon.adjustment.reason.code",string="Counter Part")
    is_reimbursed = fields.Boolean("Is Reimbursed ?",default=False,help="Is Reimbursed?")
    
