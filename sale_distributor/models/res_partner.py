# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import fields, models, api, _
from datetime import datetime


class ResPartner(models.Model):
    _inherit = 'res.partner'

    vendor_stock_master_line = fields.One2many("vendor.stock.master.line", "res_partner_id",
                                               "Vendor Stock Line")
    sequence_name = fields.Char(string="Unique No.")

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        # TDE FIXME: strange
        if self._context.get('search_default_sequence_name'):
            args.append((('categ_id', 'child_of', self._context['search_default_sequence_name'])))
        return super(ResPartner, self)._search(args, offset=offset, limit=limit, order=order, count=count,
                                                   access_rights_uid=access_rights_uid)

    def name_get(self):
        result = []
        for s in self:
            if s.sequence_name:
                name = '[' + str(s.sequence_name) + '] ' + str(s.name)
                result.append((s.id, name))
            else:
                name = str(s.name)
                result.append((s.id, name))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('name', operator, name), ('sequence_name', operator, name)]
        partner = self.search(domain + args, limit=limit)
        return partner.name_get()

    @api.model
    def create(self, vals):
        vals['sequence_name'] = self.env['ir.sequence'].next_by_code('res.partner') or _('New')
        return super(ResPartner, self).create(vals)


class VendorStockMasterLine(models.Model):
    _name = 'vendor.stock.master.line'
    _description = 'Vendor Stock Line'

    res_partner_id = fields.Many2one('res.partner', string='Vendor')
    # location_id = fields.Many2one('stock.location', string='Location')
    location_id = fields.Char(string='Name')
    product_id = fields.Many2one('product.product', string="Product")
    case_qty = fields.Float(string="Stock")
    state = fields.Char('State')
    abbreviation = fields.Char('Abbv.')
    hub = fields.Char('HUB')
    zip = fields.Char('Zip')
    phone = fields.Char('Phone#')
