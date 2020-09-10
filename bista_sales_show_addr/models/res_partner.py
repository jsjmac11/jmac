# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

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
        """
        Overriding the _get_name function from res.partner so that the "invoice address" 
        and "shipping address" fields on the quotes form display the full address, not 
        the standard contact name. Requires that the contact type be set as 'delivery' 
        or 'invoice'.

        One issue is that this command does not seem to be called once a contact is created. 
        """
        if not self.type in ["delivery", "invoice"]:
            return super(ResPartner, self)._get_name()
        self = self.with_context(show_address_only=True)
        self = self.with_context(show_address=False)
        default_name = super(ResPartner, self)._get_name()
        return " ".join(default_name.splitlines()[0:2])
