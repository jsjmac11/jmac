# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import fields, models, api
from datetime import datetime

from odoo.tools import float_compare


class ProductProduct(models.Model):
    _inherit = "product.product"

    # def _select_seller(self, partner_id=False, quantity=0.0, date=None, uom_id=False, params=False):
	   #  self.ensure_one()
	   #  if date is None:
	   #      date = fields.Date.context_today(self)
	   #  precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

	   #  res = self.env['product.supplierinfo']
	   #  sellers = self._prepare_sellers(params)
	   #  if self.env.context.get('force_company'):
	   #      sellers = sellers.filtered(lambda s: not s.company_id or s.company_id.id == self.env.context['force_company'])
	   #  for seller in sellers:
	   #      # Set quantity in UoM of seller
	   #      quantity_uom_seller = quantity
	   #      if quantity_uom_seller and uom_id and uom_id != seller.product_uom:
	   #          quantity_uom_seller = uom_id._compute_quantity(quantity_uom_seller, seller.product_uom)

	   #      if seller.date_start and seller.date_start > date:
	   #          continue
	   #      if seller.date_end and seller.date_end < date:
	   #          continue
	   #      # Comment to pass any vendor from sale order line
	   #      if partner_id and seller.name not in [partner_id, partner_id.parent_id]:
	   #          continue
	   #      if float_compare(quantity_uom_seller, seller.min_qty, precision_digits=precision) == -1:
	   #          continue
	   #      if seller.product_id and seller.product_id != self:
	   #          continue
	   #      if not res or res.name == seller.name:
	   #          res |= seller
	   #  return res.sorted('price')[:1]