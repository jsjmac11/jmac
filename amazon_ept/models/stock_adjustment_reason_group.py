from odoo import models,fields
    
class amazon_adjustment_reason_group(models.Model):
    _name="amazon.adjustment.reason.group"
    _description = "amazon.adjustment.reason.group"

    def check_counter_part_group_or_not(self):
        is_counter_part_group=False
        for code in self.reason_code_ids:
            if code.counter_part_id:
                is_counter_part_group=True
                break
        self.is_counter_part_group=is_counter_part_group
            
    name=fields.Char("Name",required=True)
    is_counter_part_group=fields.Boolean(compute="check_counter_part_group_or_not",string="Is counter Part group")
    reason_code_ids=fields.One2many('amazon.adjustment.reason.code','group_id',string="Reason Codes") 
