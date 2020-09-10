# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import fields, models, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _get_name(self):
        if not self.type in ["delivery", "invoice"]:
            return super(ResPartner, self)._get_name()
        self = self.with_context(show_address_only=True)
        self = self.with_context(show_address=False)
        default_name = super(ResPartner, self)._get_name()
        return " ".join(default_name.splitlines()[0:2])
