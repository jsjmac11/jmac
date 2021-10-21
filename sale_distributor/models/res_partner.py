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
    email_cc = fields.Char(string="Email CC")
    email_bcc = fields.Char(string="Email BCC")
    dropship_selection = fields.Selection([('Yes', 'Yes'), ('No', 'No')], string='Dropships')
    dropship_fee = fields.Float(string="Dropship Fee")
    order_min = fields.Char(string="Order Minimum")
    below_min_fee = fields.Float(string="Below Minimum Fee")
    free_freight_level = fields.Char(string="Free Freight Level")
    ships_from = fields.Char(string="Ship From")
    ship_cutoff_time = fields.Char(string="Shipping Cutoff Time")
    note = fields.Text(string="Note")

    def read(self, fields=None, load='_classic_read'):
        res =  super(ResPartner, self).read(fields=fields, load=load)
        if self.env.context.get('send_by_email'):
            for data in res:
                if data.get('display_name'):
                    data['display_name'] = data['email']
        return res

    def _get_default_country(self):
        return self.env.ref('base.us').id
        
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict', default=_get_default_country)

    def _get_default_customer_payment_term(self):
        return self.env.ref('account.account_payment_term_immediate').id

    property_payment_term_id = fields.Many2one('account.payment.term', company_dependent=True,
        string='Customer Payment Terms',
        default=_get_default_customer_payment_term,
        help="This payment term will be used instead of the default one for sales orders and customer invoices")
    

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        # TDE FIXME: strange
        if self._context.get('search_default_sequence_name'):
            args.append((('categ_id', 'child_of', self._context['search_default_sequence_name'])))
        return super(ResPartner, self)._search(args, offset=offset, limit=limit, order=order, count=count,
                                                   access_rights_uid=access_rights_uid)

    def _get_name(self):
        partner = self
        name = super(ResPartner, self)._get_name()
        full_name = ''
        if partner.sequence_name:
            full_name = '[' + str(partner.sequence_name) + '] '
        address = partner._display_address(without_company=True)
        if not address.strip() and self._context.get('show_address_only'):
            name = full_name + str(partner.name)   
        if not self._context.get('show_address_only'):
            name = full_name + name      
        if self.env.context.get('force_email') and partner.email:
            name = str(partner.email)
        return name

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
        if vals.get('parent_id'):
            parent_id = self.browse(vals.get('parent_id'))
            vals['sequence_name'] = parent_id.sequence_name
        else:
            vals['sequence_name'] = self.env['ir.sequence'].next_by_code('res.partner') or _('New')
        return super(ResPartner, self).create(vals)

class MailComposer(models.TransientModel):
    _inherit = 'mail.compose.message'

    @api.model
    def default_get(self, fields):
        result = super(MailComposer, self).default_get(fields)
        if self.env.context.get('active_model') == 'sale.order':
            active_id = self.env.context.get('active_id')
            order_id = self.env[self.env.context.get('active_model')].browse(active_id)
            result["email_cc"]= order_id.partner_id.email_cc
            result["email_bcc"]= order_id.partner_id.email_bcc
        return result


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
