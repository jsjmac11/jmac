# -*- coding: utf-8 -*-

from odoo import fields, models


class SaleReport(models.Model):
    _inherit = "sale.report"

    amz_instance_id = fields.Many2one('amazon.instance.ept', 'Amazon Instances', readonly=True)
    amz_seller_id = fields.Many2one('amazon.seller.ept', 'Amazon Sellers', readonly=True)
    amz_fulfillment_by = fields.Selection([('FBA', 'Fulfilled By Amazon'),
                                           ('FBM', 'Fulfilled By Merchant')],
                                          string='Fulfillment By', readonly=True)

    def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
        fields['amz_instance_id'] = ", s.amz_instance_id as amz_instance_id"
        fields['amz_seller_id'] = ", s.amz_seller_id as amz_seller_id"
        fields['amz_fulfillment_by'] = ", s.amz_fulfillment_by as amz_fulfillment_by"
        groupby += ', s.amz_instance_id, s.amz_seller_id, s.amz_fulfillment_by'
        return super(SaleReport, self)._query(with_clause, fields, groupby, from_clause)
