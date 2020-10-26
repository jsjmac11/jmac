# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import models, api, _
import pgeocode
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    def get_city_state(self, country_id, zip_code):
        """
        Calls the pgeocode api and get city and state based on zip.
        :param country_id:
        :param zip_code:
        :return:
        """
        state_id = False
        city = ''
        # if self and country_id and zip_code:
        if country_id and zip_code:
            if '-' in zip_code:  # Handles ZIP+4 scenario
                zip_code = zip_code.split('-')[0]
            if len(zip_code) >= 5:
                try:
                    nomi = pgeocode.Nominatim(country_id.code)
                except ValueError:
                    raise UserError(_("Country code %s is not a known country code") % country_id.code)
                except AttributeError:
                    raise UserError(_("Please enter country code for %s") % country_id.name)
                all_data = nomi.query_postal_code(zip_code)  # returns pandas series
                if isinstance(all_data.get(key='country code'), float):  # returns NaN(float datatype) incase of no result
                    raise UserError(_("Maybe you are selecting wrong country."))
                state_id = country_id.state_ids.filtered(lambda x: x.code == all_data.get(key='state_code'))
                if not state_id:  # In-case of wrong state code
                    state_id = country_id.state_ids.filtered(lambda x: x.name == all_data.get(key='state_name'))
                city = all_data.get(key='place_name')
        return city, state_id

    @api.model
    def create(self, vals):
        res = super(ResPartner, self).create(vals)
        warning_message = ''
        if 'city' in vals or 'state_id' in vals or 'country_id' in vals:
            if res.zip and (res.city or res.state_id or res.country_id):
                if res.country_id:  # If country is changing
                    country_id = res.country_id
                else:  # If country is changing to none
                    raise UserError(_('You can not leave country blank.'))
                city, state_id = self.get_city_state(country_id, res.zip)
                if not res.city:
                #     if res.city.lower() != city.lower():
                #         warning_message += "City is wrong.\n"
                #     else:
                #         pass
                # else:
                    warning_message += "You can not leave city blank.\n"
                if res.state_id and state_id:
                    if res.state_id.id != state_id.id:
                        warning_message += "State is wrong."
                if not res.state_id:
                    warning_message += "You can not leave state blank"
                if warning_message:
                    raise UserError(_(warning_message))
        return res

    def write(self, vals):
        res = super(ResPartner, self).write(vals)
        for partner in self:
            warning_message = ''
            if 'city' in vals or 'state_id' in vals or 'country_id' in vals:
                if partner.zip and (partner.city or partner.state_id or partner.country_id):
                    if partner.country_id:  # If country is changing
                        country_id = partner.country_id
                    else:  # If country is changing to none
                        raise UserError(_('You can not leave country blank.'))
                    city, state_id = partner.get_city_state(country_id, partner.zip)
                    if not partner.city:
                    #     if partner.city.lower() != city.lower():
                    #         warning_message += "City is wrong.\n"
                    # else:
                        warning_message += "You can not leave city blank.\n"
                    if partner.state_id and state_id:
                        if partner.state_id.id != state_id.id:
                            warning_message += "State is wrong."
                    if not partner.state_id:
                        warning_message += "You can not leave state blank"
                    if warning_message:
                        raise UserError(_(warning_message))
        return res

    @api.onchange('zip')
    def onchange_zip(self):
        """
        Populate city and state based on zip code.
        :return:
        """
        city, state_id = self.get_city_state(self.country_id, self.zip)
        self.city = city
        if state_id:
            self.state_id = state_id.id
