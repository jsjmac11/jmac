# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE URL <https://store.webkul.com/license.html/> for full copyright and licensing details.
#################################################################################

from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)


class MwsDomain(models.Model):
    _name = "mws.domain"
    _description = "MWS Domain"
    
    region = fields.Char(string='Region', required=1)
    name = fields.Char(string='Domain', required=1)

    @api.depends('region', 'name')
    def name_get(self):
        res = []
        for record in self:
            name = '{0} ({1}) '.format(record.name, record.region)
            res.append((record.id, name))
        return res

    @api.model
    def create(self, vals):
        if vals.get('name'):
            vals['name'] = vals.get('name').strip('/')
        return super(MwsDomain, self).create(vals)

    def write(self, vals):
        if vals.get('name'):
            vals['name'] = vals.get('name').strip('/')
        return super(MwsDomain, self).write(vals)
