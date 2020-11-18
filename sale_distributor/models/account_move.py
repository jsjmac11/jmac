# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import fields, models, api, _


class AccountMoveLine(models.Model):
	_inherit = "account.move.line"

	product_pack_id = fields.Many2one("product.pack.uom",string="Product Pack")
	pack_quantity = fields.Float(string='Pack Quantity', digits='Product Unit of Measure', required=True, default=1.0)

	@api.onchange('product_pack_id')
	def product_pack_id_change(self):
		self.product_id = False
		if self.product_pack_id:
			self.product_id = self.product_pack_id.product_tmpl_id.product_variant_id.id
			self.quantity = 1.0
			self.pack_quantity = self.product_pack_id.quantity


	# def _get_price_total_and_subtotal(self, price_unit=None, quantity=None, discount=None, currency=None, product=None, partner=None, taxes=None, move_type=None):
	# 	self.ensure_one()
	# 	quantity = quantity or self.quantity
	# 	if self.product_pack_id:
	# 		quantity = self.pack_quantity
	# 	return self._get_price_total_and_subtotal_model(
	# 		price_unit=price_unit or self.price_unit,
	# 		quantity=quantity,
	# 		discount=discount or self.discount,
	# 		currency=currency or self.currency_id,
	# 		product=product or self.product_id,
	# 		partner=partner or self.partner_id,
	# 		taxes=taxes or self.tax_ids,
	# 		move_type=move_type or self.move_id.type,
	# 		)
	@api.model
	def _get_price_total_and_subtotal_model(self, price_unit, quantity, discount, currency, product, partner, taxes, move_type):
		''' This method is used to compute 'price_total' & 'price_subtotal'.

		:param price_unit:  The current price unit.
		:param quantity:    The current quantity.
		:param discount:    The current discount.
		:param currency:    The line's currency.
		:param product:     The line's product.
		:param partner:     The line's partner.
		:param taxes:       The applied taxes.
		:param move_type:   The type of the move.
		:return:            A dictionary containing 'price_subtotal' & 'price_total'.
		'''
		if self.product_pack_id:
			res = {}

			# Compute 'price_subtotal'.
			price_unit_wo_discount = price_unit * (1 - (discount / 100.0))
			subtotal = self.pack_quantity * price_unit_wo_discount

			# Compute 'price_total'.
			if taxes:
				taxes_res = taxes._origin.compute_all(price_unit_wo_discount,
					quantity=self.pack_quantity, currency=currency, product=product, partner=partner, is_refund=move_type in ('out_refund', 'in_refund'))
				res['price_subtotal'] = taxes_res['total_excluded']
				res['price_total'] = taxes_res['total_included']
			else:
				res['price_total'] = res['price_subtotal'] = subtotal
			#In case of multi currency, round before it's use for computing debit credit
			if currency:
				res = {k: currency.round(v) for k, v in res.items()}
		else:
			res = super(AccountMoveLine, self)._get_price_total_and_subtotal_model(
				price_unit,quantity,discount,currency,product,partner,taxes,move_type,)
		return res
