# -*- coding: utf-8 -*-
##############################################################################
#
#    Bista Solutions Pvt. Ltd
#    Copyright (C) 2019 (http://www.bistasolutions.com)
#
##############################################################################
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    ticket_id = fields.Many2one("helpdesk.ticket", string="Ticket")

    @api.model
    def create(self, vals):
        res = super(SaleOrder, self).create(vals)
        if vals.get('ticket_id', False):
            res.ticket_id.is_quotation = True
        return res

    def unlink(self):
        for order in self:
            if order.ticket_id:
                order.ticket_id.is_quotation = False
        super(SaleOrder, self).unlink()

    def action_cancel(self):
        for order in self:
            if order.ticket_id:
                order.ticket_id.is_quotation = False
        return super(SaleOrder, self).action_cancel()

    def action_draft(self):
        ticket = self.filtered(lambda s: s.state in ['cancel', 'sent']).mapped('ticket_id')
        if ticket:
            quot_ids = self.search([('ticket_id', '=', ticket.id), ('state', '!=', 'cancel')])
            if quot_ids:
                raise UserError(_('Quotation already exists for the ticket!'))
            ticket.is_quotation = True
        return super(SaleOrder, self).action_draft()


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    active_quot_creation = fields.Boolean(related='team_id.creat_quot_helpdesk', string='Active Create Quotation')
    sale_count = fields.Integer("Sale Count", compute="_get_sale_count")
    is_quotation = fields.Boolean("Quotation")

    def _get_sale_count(self):
        for rec in self:
            rec.sale_count = self.env['sale.order'].search_count(
                [('ticket_id', '=', self.id)])

    def action_view_sale(self):
        list_view_id = self.env.ref('sale.view_quotation_tree_with_onboarding').id
        return {
            'name': ('Sale Order'),
            'view_mode': 'tree',
            'views': [(list_view_id, "list"), (False, "form")],
            'view_type': 'form',
            'res_model': 'sale.order',
            'domain': [['ticket_id.id', '=', self.id]],
            'type': 'ir.actions.act_window',
            'context': {"create": False, 'export': False}
        }

    def create_new_quotation(self):
        form_view_id = self.env.ref('sale.view_order_form').id
        return {
            'name': ('Sale Order'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.order',
            'view_id': form_view_id,
            'type': 'ir.actions.act_window',
            'context': {'default_ticket_id': self.id, 'default_partner_id': self.partner_id.id}
        }


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    creat_quot_helpdesk = fields.Boolean('Create Quotation')
