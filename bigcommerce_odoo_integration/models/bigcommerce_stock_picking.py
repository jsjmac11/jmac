from odoo import fields,models,api
from odoo.exceptions import ValidationError
from requests import request
import requests
import json
import logging
_logger = logging.getLogger("Bigcommerce")


class BigcommerceOrderShimpentStatus(models.Model):
    _inherit = 'stock.picking'

    bigcommerce_shimpment_id = fields.Char(string="Bigcommerce Shipment Numebr")

    def get_shipment_status(self):
        """
        This Method Used To Get Status Of Bigcommerce Order Status
        :return:  If Order Is Shipped return
        """

        sale_order_id = self.env['sale.order'].search([('id','=',self._context.get('active_id'))])
        bigcommerce_store_id = sale_order_id.warehouse_id.bigcommerce_store_ids
        bigcommerce_order_id = sale_order_id.big_commerce_order_id
        api_url ='%s%s/v2/orders/%s/shipments'%(bigcommerce_store_id.bigcommerce_api_url,bigcommerce_store_id.bigcommerce_store_hash,
                                                str(bigcommerce_order_id))
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Auth-Client': '{}'.format(bigcommerce_store_id.bigcommerce_x_auth_client),
            'X-Auth-Token': "{}".format(bigcommerce_store_id.bigcommerce_x_auth_token)
        }
        try:
            response = requests.get(url=api_url,headers=headers)
            _logger.info("Sending Get Request To {}".format(response))
            if response.status_code in [200,201]:
                _logger.info("Get Successfully Response")
                response = response.json()
                traking_number =response.get('tracking_number')
                self.bigcommerce_shimpment_id = traking_number
                sale_order_id.bigcommerce_store_status = 'Shipped'

            elif response.status_code in [204]:
                sale_order_id.bigcommerce_shipment_order_status = 'Updating. . .'
            else:
                raise ValidationError("Getting Some Error {}".format(response.text))
        except Exception as e:
            raise ValidationError(e)

    def export_tracking_odoo_to_bigcommerce(self):
        sale_order_id = self.env['sale.order'].search([('id','=',self._context.get('active_id'))])
        bigcommerce_store_id = sale_order_id.warehouse_id.bigcommerce_store_ids
        bigcommerce_order_id = sale_order_id.big_commerce_order_id

        try:
            if not bigcommerce_store_id:
                raise ValidationError("Big commerce store not found fot this order.")
            api_url ='%s%s/v2/orders/%s/shipments/%s'%(bigcommerce_store_id.bigcommerce_api_url,bigcommerce_store_id.bigcommerce_store_hash,
                                                str(bigcommerce_order_id), self.bigcommerce_shimpment_id)
            request_data ={"tracking_number": self.carrier_tracking_ref}
            headers = {"Accept": "application/json",
                       "X-Auth-Client": "{}".format(bigcommerce_store_id and bigcommerce_store_id.bigcommerce_x_auth_client),
                       "X-Auth-Token": "{}".format(bigcommerce_store_id and bigcommerce_store_id.bigcommerce_x_auth_token),
                       "Content-Type": "application/json"}
            data = json.dumps(request_data)
            url = "{0}".format(api_url)
            try:
                _logger.info("Send PUT Request From odoo to BigCommerce: {0}".format(url))
                response_data =  request(method='PUT', url=api_url, data=data, headers=headers)
            except Exception as e:
                _logger.info("Getting an Error in POST Req odoo to BigCommerce: {0}".format(e))
                raise ValidationError(e)
            if response_data.status_code in [200, 201]:
                response_data = response_data.json()
                return {
                    'effect': {
                        'fadeout': 'slow',
                        'message': 'Tracking Reference Exported : %s' % (self.carrier_tracking_ref),
                        'img_url': '/web/static/src/img/smile.svg',
                        'type': 'rainbow_man',
                    }
                }
            else:
                response_data = response_data.json()
                error_msg = "{0} : {1}".format(response_data)
                raise ValidationError(error_msg)
        except Exception as e:
            raise ValidationError("Process Is Not Completed Yet!  {}".format(e))
