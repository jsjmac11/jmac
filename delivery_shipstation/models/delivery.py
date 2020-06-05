# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

from odoo import models, fields, api


class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    package_carrier_type = fields.Selection(selection_add=[('shipstation', 'Shipstation')])


class ProviderShipstation(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[('shipstation', "Shipstation")])
    shipstation_default_packaging_id = fields.Many2one(
        'product.packaging', string='Default Packaging Type', domain=[('package_carrier_type','=','shipstation')])
    shipstation_default_uom = fields.Selection([
            ('imperial', 'Imperial - LBS & Inch'), 
            ('metric', 'Metric - Kgs & Cm')], default='imperial')
    shipstation_carrier_code = fields.Char("Carrier Code")
    shipstation_service_code = fields.Char("Service Code")
    shipstation_carrier_id = fields.Many2one("shipstation.carrier", 'Shipstation Carrier')

class ShipstationCarrier(models.Model):
    _name = 'shipstation.carrier'
    _description = 'Shipstation Carrier'

    name = fields.Char('Carrier')
    code = fields.Char('Code')

class ShipstationPackage(models.Model):
    _name = 'shipstation.package'
    _description = 'Shipstation Packages'

    carrierCode = fields.Char("Carrier Code")
    code = fields.Char("Code")
    name = fields.Char("Name")
    international = fields.Boolean("International")
    domestic = fields.Boolean("Domestic")