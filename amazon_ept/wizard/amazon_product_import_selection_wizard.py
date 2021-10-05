import base64
import csv
from io import StringIO
from odoo import models, fields
from odoo.exceptions import Warning

"""
MUST BE REMOVE THIS MODEL AND FIELDS FROM ODOO VERSION 15
DUE TO EXISTING CUSTOMER NOT UPGRADE THE MODULE THAT'S WHY NOT REMOVE FROM  
"""
class AmazonProductImportSelectionWizard(models.TransientModel):
    _name = "amazon.import.product.wizard"
    _description = 'amazon.import.product.wizard'

    seller_id = fields.Many2one('amazon.seller.ept', string='Seller',
                                help="Select Seller Account to associate with this Instance")
    file_name = fields.Char(string='Name')
    choose_file = fields.Binary(string="Choose File", filename="filename")
    delimiter = fields.Selection([('tab', 'Tab'), ('semicolon', 'Semicolon'), ('comma', 'Comma')],
                                 string="Separator", default='comma')
