from odoo import models,api,fields,_
import logging
import base64
from odoo.exceptions import ValidationError
import requests
import json
import time
import re

_logger = logging.getLogger("BigCommerce")

class ProductSearchKeyword(models.Model):
    _name = "product.search.keyword"
    _description = "Product Search Keyword"
    
    name = fields.Char('Keyword')
    product_template_id = fields.Many2one(
            'product.template','Product')
    
    @api.model
    def create(self, vals):
        if vals.get('name'):
            name_url = vals.get('name')
            res = re.sub('[^+A-Za-z0-9]', '', name_url)
            if not res[-1].isalnum():
               name_url = re.sub('[^A-Za-z0-9]', '', name_url)[:-1]
            else:
                name_url = re.sub('[^A-Za-z0-9]', '', name_url)
            vals.update({'name': name_url})
        return super(ProductSearchKeyword, self).create(vals)
    
    @api.constrains('name', 'product_template_id')
    def _check_url_fields(self):
        for rec in self:
            keyword = self.search([('name', '=', rec.name),
                        ('product_template_id','=', rec.product_template_id.id),
                         ('id', '!=', rec.id)])
            if keyword:
                raise ValidationError("Same Keyword already Exists.!")
        