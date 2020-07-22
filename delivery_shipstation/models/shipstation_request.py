# -*- coding: utf-8 -*-
##############################################################################
#
#    Bista Solutions Pvt. Ltd
#    Copyright (C) 2017 (http://www.bistasolutions.com)
##############################################################################

from odoo import models, fields, api, tools, _
import requests
from math import ceil
from xml.etree import ElementTree as etree
import base64
from odoo.exceptions import UserError
from xml.dom.minidom import parseString
import re
import json
from datetime import datetime
import binascii
from odoo.exceptions import ValidationError
import logging

logger = logging.getLogger('Shipstation Request-Response Log')

# This re should match postcodes like 12345 and 12345-6789
ZIP_ZIP4 = re.compile('^[0-9]{5}(-[0-9]{4})?$')


def split_zip(zipcode):
    '''If zipcode is a ZIP+4, split it into two parts.
       Else leave it unchanged '''
    if ZIP_ZIP4.match(zipcode) and '-' in zipcode:
        return zipcode.split('-')
    else:
        return [zipcode, '']


class ShipstationRequest():

    def __init__(self, debug_logger, prod_environment, url, token):
        self.debug_logger = debug_logger
        # Product and Testing
        if prod_environment:
            self.url = url
        else:
            self.url = url
        # Basic detail require to authenticate
        self.token = token

    def _convert_phone_number(self, phone):
        phone_pattern = re.compile(r'''
				# don't match beginning of string, number can start anywhere
				(\d{3})     # area code is 3 digits (e.g. '800')
				\D*         # optional separator is any number of non-digits
				(\d{3})     # trunk is 3 digits (e.g. '555')
				\D*         # optional separator
				(\d{4})     # rest of number is 4 digits (e.g. '1212')
				\D*         # optional separator
				(\d*)       # extension is optional and can be any number of digits
				$           # end of string
				''', re.VERBOSE)
        match = phone_pattern.search(phone)
        if match:
            return ''.join(str(digits_number) for digits_number in match.groups())
        else:
            return False

    def check_required_value(self, recipient, delivery_nature, shipper, order=False, picking=False):
        recipient_required_field = ['city', 'zip', 'country_id']
        if not recipient.street and not recipient.street2:
            recipient_required_field.append('street')
        shipper_required_field = ['city', 'zip', 'phone', 'state_id', 'country_id']
        if not recipient.street and not recipient.street2:
            shipper_required_field.append('street')

        res = [field for field in shipper_required_field if not shipper[field]]
        if res:
            return _("The address of your company is missing or wrong (Missing field(s)) :\n%s") % ", ".join(
                res).replace("_id", "")
        # if shipper.country_id.code != 'US':
        #     return _("Please set country U.S.A in your company address, Service is only available for U.S.A")
        if not ZIP_ZIP4.match(shipper.zip):
            return _("Please enter a valid ZIP code in your Company address")
        if not self._convert_phone_number(shipper.phone):
            return _("Company phone number is invalid. Please insert a US phone number.")
        res = [field for field in recipient_required_field if not recipient[field]]
        if res:
            return _("The recipient address is missing or wrong (Missing field(s)) :\n%s") % ", ".join(res).replace(
                "_id", "")
        if delivery_nature == 'domestic' and not ZIP_ZIP4.match(recipient.zip):
            return _("Please enter a valid ZIP code in recipient address")
        if recipient.country_id.code == "US" and delivery_nature == 'international':
            return _(
                "International Carrier is used only to ship outside of the U.S.A. Please change the delivery method into Domestic Carrier.")
        if recipient.country_id.code != "US" and delivery_nature == 'domestic':
            return _(
                "Domestic Carrier is used only to ship inside of the U.S.A. Please change the delivery method into International Carrier.")
        if order:
            if not order.order_line:
                return _("Please provide at least one item to ship.")
            # for line in order.order_line.filtered(
            #         lambda line: not line.product_id.weight and not line.is_delivery and line.product_id.type not in [
            #             'service', 'digital'] and not line.display_type):
            if not order.order_weight and not order.weight_oz:
                    return _('The estimated price cannot be computed because the weight of your product is missing.')
            if order.order_weight < 0 or order.weight_oz < 0:
                    return _('Weight of the order should not be negative!')
        if picking:
            if not picking.move_lines:
                return _("Please provide at least one item to ship.")
            if not picking.shipping_weight and not picking.shipping_weight_oz:
                    return _('The estimated price cannot be computed because the weight of your product is missing.')
            if picking.shipping_weight < 0 or picking.shipping_weight_oz < 0:
                    return _('Weight of the order should not be negative!')
            # tot_weight = sum([(line.product_id.weight * line.product_qty) for line in order.order_line if
            #                   not line.display_type]) or 0
            # weight_uom_id = order.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
            # weight_in_pounds = weight_uom_id._compute_quantity(tot_weight, order.env.ref('uom.product_uom_lb'))
            # if weight_in_pounds > 4 and order.carrier_id.usps_service == 'First Class':  # max weight of FirstClass Service
            #     return _("Please choose another service (maximum weight of this service is 4 pounds)")
        # if picking and picking.move_lines:
        # 	# https://www.usps.com/business/web-tools-apis/evs-international-label-api.htm
        # 	if max(picking.move_lines.mapped('product_uom_qty')) > 999:
        # 		return _("Quantity for each move line should be less than 1000.")
        return False

    def _convert_to_lbs(self, weight_in_kg):
        # Return weight in LBS as prefered by eShipper
        return round(weight_in_kg * 2.20462, 3)

    # def _shipstation_request_data(self, carrier, order):
    # 	currency = carrier.env['res.currency'].search([('name', '=', 'USD')], limit=1)  # USPS Works in USDollars
    # 	tot_weight = sum([(line.product_id.weight * line.product_qty) for line in order.order_line if not line.display_type]) or 0.0
    # 	total_weight = carrier._usps_convert_weight(tot_weight)
    # 	total_value = sum([(line.price_unit * line.product_uom_qty) for line in order.order_line.filtered(lambda line: not line.is_delivery and not line.display_type)]) or 0.0

    # 	if order.currency_id.name == currency.name:
    # 		price = total_value
    # 	else:
    # 		quote_currency = order.currency_id
    # 		price = quote_currency._convert(
    # 			total_value, currency, order.company_id, order.date_order or fields.Date.today())

    # 	rate_detail = {
    # 			'api': 'RateV4' if carrier.usps_delivery_nature == 'domestic' else 'IntlRateV2',
    # 			'ID': carrier.sudo().usps_username,
    # 			'revision': "2",
    # 			'package_id': '%s%d' % ("PKG", order.id),
    # 			'ZipOrigination': split_zip(order.warehouse_id.partner_id.zip)[0],
    # 			'ZipDestination': split_zip(order.partner_shipping_id.zip)[0],
    # 			'FirstClassMailType': carrier.usps_first_class_mail_type,
    # 			'Pounds': total_weight['pound'],
    # 			'Ounces': total_weight['ounce'],
    # 			'Size': carrier.usps_size_container,
    # 			'Service': carrier.usps_service,
    # 			'Container': carrier.usps_container,
    # 			'DomesticRegularontainer': carrier.usps_domestic_regular_container,
    # 			'InternationalRegularContainer': carrier.usps_international_regular_container,
    # 			'MailType': carrier.usps_mail_type,
    # 			'Machinable': str(carrier.usps_machinable),
    # 			'ValueOfContents': price,
    # 			'Country': order.partner_shipping_id.country_id.name,
    # 			'Width': carrier.usps_custom_container_width,
    # 			'Height': carrier.usps_custom_container_height,
    # 			'Length': carrier.usps_custom_container_length,
    # 			'Girth': carrier.usps_custom_container_girth,
    # 	}

    # 	# Shipping to Canada requires additional information
    # 	if order.partner_shipping_id.country_id == order.env.ref('base.ca'):
    # 		rate_detail.update(OriginZip=order.warehouse_id.partner_id.zip)

    # 	return rate_detail

    def prepare_address(self, partner_id, type="From"):
        name = partner_id.name if not partner_id.parent_id else partner_id.parent_id.name
        address = {
            "name": partner_id.name,
            "company": name,
            "street1": partner_id.street or '',
            "street2": partner_id.street2 or '',
            "street3": '',
            "city": partner_id.city or '',
            "state": partner_id.state_id.code or '',
            "postalCode": partner_id.zip.replace(" ", "") if partner_id.zip else '',
            "country": partner_id.country_id.code or '',
            "phone": partner_id.phone or partner_id.mobile or '',
            "residential": False
        }
        return address

    def _shipstation_shipping_data(self, picking, is_return=False):
        carrier = picking.carrier_id
        itemdetail = []
        order = picking.sale_id
        company = order.company_id or picking.company_id or self.env.company
        shipper_currency = picking.sale_id.currency_id or picking.company_id.currency_id
        USD = carrier.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        quote_currency = picking.env['res.currency'].search([('name', '=', shipper_currency.name)], limit=1)
        for line in picking.move_lines:
            if shipper_currency.name == USD.name:
                price = line.product_id.lst_price * line.product_uom_qty
            else:
                amount = line.product_id.lst_price * line.product_uom_qty
                price = quote_currency._convert(
                    amount, USD, company, order.date_order or fields.Date.today())
        if not is_return:
            gross_weight = carrier._shipstation_convert_weight(picking.shipping_weight)
            weight_in_ounces = 16 * gross_weight['pound'] + gross_weight['ounce']
        else:
            gross_weight = carrier._shipstation_convert_weight(picking.weight)
            weight_in_ounces = picking.weight * 35.274
        if not picking.ship_package_id:
            raise ValidationError(_("Please select package on order %s!" % picking.name))
        if not carrier:
            raise ValidationError(_("Please select carrier on order %s!" % picking.name))
        shipping_detail = {
            "carrierCode": carrier.shipstation_carrier_code,
            "serviceCode": carrier.shipstation_service_code,
            "packageCode": picking.ship_package_id.code,
            "confirmation": picking.confirmation,
            "shipDate": datetime.strftime(picking.scheduled_date.date(), '%Y-%m-%d'),
            "weight": {
                "value": weight_in_ounces,
                "units": "ounces"
            },
            "dimensions": {
                "units": "inches",
                "length": picking.length,
                "width": picking.width,
                "height": picking.height
            },
            "shipFrom": self.prepare_address(picking.picking_type_id.warehouse_id.partner_id),
            "shipTo": self.prepare_address(picking.picking_type_id.warehouse_id.partner_id, type='To'),
            "insuranceOptions": {"provider":picking.insure_package_type if picking.insure_package_type else ''},
            "internationalOptions": '',
            "advancedOptions": '',
            "testLabel": True if not carrier.prod_environment else False
        }
        # if not is_return:
        #     shipping_detail.update({})
        # else:
        #     shipping_detail.update({})

        return shipping_detail

    def shipstation_request(self, picking, delivery_nature, is_return=False):
        ship_detail = self._shipstation_shipping_data(picking, is_return)
        # request_text = picking.env['ir.qweb'].render('delivery_usps.usps_shipping_common', ship_detail)
        # api = self._api_url(delivery_nature, service)
        dict_response = {'tracking_number': 0.0, 'price': '0.0', 'currency': "USD", 'shipmentId': ''}
        headers = {
            'Host': 'ssapi.shipstation.com',
            'Content-Type': 'application/json',
            'Authorization': 'Basic %s' % self.token
        }
        try:
            self.debug_logger(ship_detail, 'shipstation_request')
            url = self.url + '/shipments/createlabel'
            logger.info("ship_detail!!!!!! %s" % ship_detail)
            req = requests.request('POST', url, headers=headers, data=json.dumps(ship_detail))
            response_text = json.loads(req.text)
            self.debug_logger(response_text, 'shipstation_response')
        except requests.exceptions.ConnectionError as e:
            logger.info("ERROR!!!!!! %s" % e)
            raise ValidationError(_("Failed to establish a connection. Please check internet connection"))

        except IOError:
            dict_response['error_message'] = 'Shipstation Server Not Found - Check your connectivity'
        except:
            logger.info("ERROR!!!!!!")
            raise
        logger.info("response_text!!!!!! %s" % response_text)
        if response_text.get('ExceptionMessage'):
            dict_response['error_message'] = response_text.get('ExceptionMessage')
            return dict_response
        else:
            dict_response['tracking_number'] = response_text.get('trackingNumber')
            dict_response['price'] = response_text.get('shipmentCost')
            dict_response['label'] = binascii.a2b_base64(response_text.get('labelData'))
            dict_response['shipmentId'] = response_text.get('shipmentId')
        return dict_response

    def cancel_shipment(self, shipmentId):
        dict_response = {}
        payload = {'shipmentId': shipmentId}
        logger.info("Cancel payload!!!!!! %s" % payload)
        headers = {
            'Host': 'ssapi.shipstation.com',
            'Content-Type': 'application/json',
            'Authorization': 'Basic %s' % self.token
        }
        try:
            self.debug_logger(payload, 'shipstation_request')
            url = self.url + '/shipments/voidlabel'
            req = requests.request('POST', url, headers=headers, data=json.dumps(payload))
            response_text = json.loads(req.text)
            self.debug_logger(response_text, 'shipstation_response')
            logger.info("Cancel Response!!!!!! %s" % response_text)
        except requests.exceptions.ConnectionError as e:
            logger.info("ERROR!!!!!! %s" % e)
            raise ValidationError(_("Failed to establish a connection. Please check internet connection"))
        except IOError:
            dict_response['error_message'] = 'Shipstation Server Not Found - Check your connectivity'
        except:
            logger.info("ERROR!!!!!!")
            raise
        if response_text.get('ExceptionMessage'):
            dict_response['error_message'] = response_text.get('ExceptionMessage')
            return dict_response
        return dict_response

    def rate_response_data(self, response_data, api_config_obj, ship_carrier_id):
        line_ids = []
        service_rate_lst = []
        delivery_obj = api_config_obj.env['delivery.carrier']
        for data in response_data:
            service_id = delivery_obj.search([('shipstation_service_code', '=', data.get('serviceCode'))])
            if not service_id:
                service_id = api_config_obj.get_services(ship_carrier_id)
            pack_name = data.get('serviceName', '').split(' - ')
            pack_id = False
            if pack_name:
                pack_id = api_config_obj.env['shipstation.package'].search([('name', '=', pack_name[1])])
            values = {
                'shipstation_carrier_id': ship_carrier_id.id,
                'service_id': service_id.id,
                'service_name': data.get('serviceName', ''),
                'service_code': data.get('serviceCode', ''),
                'shipping_cost': data.get('shipmentCost', 0),
                'other_cost': data.get('otherCost', 0),
                'rate': data.get('shipmentCost', 0) + data.get('otherCost', 0),
                # 'transit_days': result.get('transitdays', 0),
                'package_id': pack_id.id if pack_id else False,
            }
            service_rate_lst.append(values)
            line_ids.append((0, 0, values))
        min_service = min(service_rate_lst, key=lambda x: x['rate'])
        return {'line_ids': line_ids, 'min_service': min_service}
