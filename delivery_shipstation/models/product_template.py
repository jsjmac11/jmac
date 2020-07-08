# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _get_default_weight_oz_uom(self):
        uom_id = self.env.ref('uom.product_uom_oz', False) or self.env['uom.uom'].search(
            [('measure_type', '=', 'weight'), ('uom_type', '=', 'reference')], limit=1)
        return uom_id.display_name

    length = fields.Float(string='Length')
    width = fields.Float(string='Width')
    height = fields.Float(string='Height')
    weight_oz = fields.Float(string="Weight(oz)")
    weight_oz_uom_name = fields.Char(string='Weight oz unit of measure', default=_get_default_weight_oz_uom)

    @api.onchange('weight_oz')
    def onchange_weight_oz(self):
        """
        Get weight(oz) and validation.
        :return:
        """
        if self.weight_oz >= 16 or self.weight_oz < 0:
            raise ValidationError(_("Please enter Weight(oz) between 0 and 15.99!"))
