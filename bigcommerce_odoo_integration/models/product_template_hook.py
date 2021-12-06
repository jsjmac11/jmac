# See LICENSE file for full copyright and licensing details

from odoo import models, fields, api

from odoo.addons.product.models.product_template import ProductTemplate


@api.model_create_multi
def create(self, vals_list):
    ''' Store the initial standard price in order to be able to retrieve the cost of a product template for a given date'''
    templates = super(ProductTemplate, self).create(vals_list)
    if "create_product_product" not in self._context:
        templates._create_variant_ids()

    # This is needed to set given values to first variant after creation
    for template, vals in zip(templates, vals_list):
        related_vals = {}
        if vals.get('barcode'):
            related_vals['barcode'] = vals['barcode']
        if vals.get('default_code'):
            related_vals['default_code'] = vals['default_code']
        if vals.get('standard_price'):
            related_vals['standard_price'] = vals['standard_price']
        if vals.get('volume'):
            related_vals['volume'] = vals['volume']
        if vals.get('weight'):
            related_vals['weight'] = vals['weight']
        # Please do forward port
        if vals.get('packaging_ids'):
            related_vals['packaging_ids'] = vals['packaging_ids']
        related_vals.update({'manufacturer_URL': vals.get('manufacturer_URL'),
                            'mpn_URL':  vals.get('mpn_URL')})
        if related_vals:
            template.write(related_vals)
            
    return templates

ProductTemplate.create = create
