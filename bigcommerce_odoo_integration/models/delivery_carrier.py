from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    is_bigcommerce_shipping_method = fields.Boolean(default=False, string="Is Bigcommerce Delivery Method.?")
