from odoo import models, fields


class amazon_stock_adjustment_config(models.Model):
    _name = "amazon.stock.adjustment.config"
    _description = "amazon.stock.adjustment.config"

    def _get_email_template(self):
        template = False
        try:
            template = self.env.ref('amazon_ept.email_template_amazon_stock_adjustment_email_ept')
        except:
            pass
        return template.id

    group_id = fields.Many2one("amazon.adjustment.reason.group", string="Group")
    seller_id = fields.Many2one("amazon.seller.ept", string="Seller")
    location_id = fields.Many2one("stock.location", string="Location")
    is_send_email = fields.Boolean("Is Send Email ?", default=False)
    email_template_id = fields.Many2one("mail.template", string="Email Template", default=_get_email_template)

    _sql_constraints = [
        ('amazon_stock_adjustment_unique_constraint', 'unique(group_id,seller_id)', "Group must be unique per seller")]
