from odoo import models, fields


class product_ul_ept(models.Model):
    _name = "product.ul.ept"
    _description = 'product.ul.ept'

    dimension_unit = fields.Selection([('inches', 'Inches'), ('centimeters', 'Centimeters'), ],
                                      default='centimeters', string='Dimension Unit')
    name = fields.Char('Name', index=True, required=True, translate=True)
    type = fields.Selection(
        [('unit', 'Unit'), ('pack', 'Pack'), ('box', 'Box'), ('pallet', 'Pallet')], 'Type',
        required=True)
    height = fields.Float('Height', help='The height of the package')
    width = fields.Float('Width', help='The width of the package')
    length = fields.Float('Length', help='The length of the package')
    weight = fields.Float('Empty Package Weight')
