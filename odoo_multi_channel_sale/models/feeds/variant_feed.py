# -*- coding:utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL :<https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models


class ProductVariantFeed(models.Model):
	_name        = 'product.variant.feed'
	_inherit     = 'wk.feed'
	_description = 'Product Variant Feed'

	name_value = fields.Text(
		string='Name Value list',
		help = "Format of the name value list should be like this :-> [" \
			"{'name': 'Memory', 'value': '16 GB'}, " \
			"{'name': 'Color', 'value': 'White'}, " \
			"{'name': 'Wi-Fi', 'value': '2.4 GHz'}]",
	)
	extra_categ_ids = fields.Text(
		string='Extra Category ID(s)',
		help = "Format of the  should be like this :-> C1,C2,C3"
	)

	type                 = fields.Char('Product Type',default='product')
	list_price           = fields.Char('List Price')
	default_code         = fields.Char('Default Code/SKU')
	barcode              = fields.Char('Barcode/Ean13/UPC or ISBN')
	description_sale     = fields.Text('Sale Description')
	description_purchase = fields.Text('Purchase Description')
	standard_price       = fields.Char('Standard Price')
	sale_delay           = fields.Char('Sale Delay')
	qty_available        = fields.Char('Qty')
	weight               = fields.Char('Weight')
	weight_unit          = fields.Char('Weight Unit')
	length               = fields.Char('Length')
	width                = fields.Char('Width')
	height               = fields.Char('Height')
	dimensions_unit      = fields.Char('Dimensions Unit Name')
	feed_templ_id        = fields.Many2one('product.feed','Template ID',ondelete='cascade')
	wk_product_id_type   = fields.Char('Product ID Type')
	image                = fields.Binary('Image')
	image_url            = fields.Char('Image Url')
	hs_code              = fields.Char('HS Code')
