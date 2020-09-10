# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import fields, models, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def address_get(self, adr_pref=None):
        print(f">>>> Inside Extended Model")
        partners = super(ResPartner, self).address_get(adr_pref)
        print(f">>>> {partners}")
        return partners
        # res = super(SaleOrder, self).create(vals)
