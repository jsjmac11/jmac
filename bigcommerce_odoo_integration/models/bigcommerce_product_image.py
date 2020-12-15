from odoo import fields,models,api
from odoo.exceptions import ValidationError
import requests
import json
import base64
import logging
_logger = logging.getLogger("Bigcommerce")

class BigcommerceProductImage(models.Model):
    _name = "bigcommerce.product.image"

    bigcommerce_product_image_id = fields.Char(string="Product Image Id")
    bigcommerce_product_image = fields.Binary(string="Bigcommerce Product Image")
    bigcommerce_product_id = fields.Char(string='BigCommerce Product Id')
    product_template_id = fields.Many2one('product.template',string = "Product")

    def bigcommerce_to_odoo_import_image(self,warehouse_id=False, bigcommerce_store_ids=False):
        """
        This Method Is Used For Import Product Image From Bigcommerce
        :param warehouse_id:
        :param bigcommerce_store_ids:
        :return: ImageId
        """
        bigcommerce_products_ids = self.env['product.template'].search([('bigcommerce_product_id','!=',False)])
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Auth-Client': '{}'.format(bigcommerce_store_ids.bigcommerce_x_auth_client),
            'X-Auth-Token': "{}".format(bigcommerce_store_ids.bigcommerce_x_auth_token)
        }

        for product_id in bigcommerce_products_ids:
            api_url = "%s%s/v3/catalog/products/%s/images"%(bigcommerce_store_ids.bigcommerce_api_url,bigcommerce_store_ids.bigcommerce_store_hash,product_id.bigcommerce_product_id)
            try:
                response = requests.get(url=api_url,headers=headers)
                _logger.info("Sending Get Request To {}".format(api_url))
            except Exception as e:
                raise ValidationError(e)
            if response.status_code in [200,201]:
                _logger.info("Get Successfull Response")
                response = response.json()
                for data in response.get('data'):
                    if not self.search([('bigcommerce_product_image_id', '=', data.get('id'))]):
                        image_id = data.get('id')
                        image_url = data.get('url_standard')
                        image_data = base64.b64encode(requests.get(image_url).content)
                        values = {
                            'bigcommerce_product_image_id': image_id,
                            'bigcommerce_product_image': image_data,
                            'bigcommerce_product_id': data.get('product_id'),
                            'product_template_id': product_id.id,
                        }
                        self.create(values)
                        self._cr.commit()
                        _logger.info("Successfully Import Images {}".format(image_id))
                    else:
                        image_id = data.get('id')
                        image_url = data.get('url_standard')
                        image_data = base64.b64encode(requests.get(image_url).content)
                        values = {
                            'bigcommerce_product_image_id': image_id,
                            'bigcommerce_product_image': image_data,
                            'bigcommerce_product_id': data.get('product_id'),
                            'product_template_id': product_id.id,
                        }
                        self.write(values)
                        self._cr.commit()
                        _logger.info("Successfully Update Images{}".format(image_id))
                    if not product_id.image_1920:
                        product_id.image_1920 = image_data
            else:
                _logger.info("Get Some Error {}".format(response))
        bigcommerce_store_ids.bigcommerce_operation_message =" Import Product Image Process Complete "
        self._cr.commit()

        return {
            'effect': {
                'fadeout': 'slow',
                'message': "Yeah! Successfully Import Image",
                'img_url': '/web/static/src/img/smile.svg',
                'type': 'rainbow_man',
            }
        }


    def bigcommerce_to_odoo_import_variant_product_image(self,warehouse_id=False, bigcommerce_store_ids=False):
        bigcommerce_products_ids = self.env['product.template'].search([('bigcommerce_product_id', '!=', False),('bigcommerce_store_id','=',bigcommerce_store_ids.id)])
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Auth-Client': '{}'.format(bigcommerce_store_ids.bigcommerce_x_auth_client),
            'X-Auth-Token': "{}".format(bigcommerce_store_ids.bigcommerce_x_auth_token)
        }
        for product_id in bigcommerce_products_ids:
            api_url = "%s%s/v3/catalog/products/%s/variants"%(bigcommerce_store_ids.bigcommerce_api_url,bigcommerce_store_ids.bigcommerce_store_hash, product_id.bigcommerce_product_id)
            try:
                response = requests.get(url=api_url,headers=headers)
                _logger.info("Sending Request To {}".format(api_url))
                if response.status_code in [200, 201]:
                    response = response.json()
                    for product_variant_id in response.get('data'):
                        if product_variant_id.get('image_url',''):
                            variant_product_img_url = product_variant_id.get('image_url')
                            image = base64.b64encode(requests.get(variant_product_img_url).content)
                            variant_product_obj = self.env['product.product'].search(
                                [('bigcommerce_product_variant_id', '=', str(product_variant_id.get('id')))])
                            variant_product_obj.image_1920 = image
                            self._cr.commit()
                            _logger.info("Suceessfully Image Import")
                        else:
                            _logger.info("Image Not Found at {}".format(product_variant_id))
                else:
                    _logger.info("Something Wrong  {}".format(response.content))
            except Exception as e:
                raise ValidationError(e)
        bigcommerce_store_ids.bigcommerce_operation_message = " Import Product Variant Image Process Complete "
        self._cr.commit()
    
    def import_multiple_product_image(self,bigcommerce_store_ids,product_id):
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Auth-Client': '{}'.format(bigcommerce_store_ids.bigcommerce_x_auth_client),
            'X-Auth-Token': "{}".format(bigcommerce_store_ids.bigcommerce_x_auth_token)
        }
        api_url = "%s%s/v3/catalog/products/%s/images"%(bigcommerce_store_ids.bigcommerce_api_url,bigcommerce_store_ids.bigcommerce_store_hash,product_id.bigcommerce_product_id)
        try:
            response = requests.get(url=api_url,headers=headers)
            _logger.info("Sending Get Request To {}".format(api_url))
        except Exception as e:
            raise _logger.info("Issue in Get Request Response{}".format(e))
        if response.status_code in [200,201]:
            _logger.info("Get Successfull Response")
            response = response.json()
            for data in response.get('data'):
                image_id = data.get('id')
                image_url = data.get('url_standard')
                image_data = base64.b64encode(requests.get(image_url).content)
                values = {
                    'bigcommerce_product_image_id': image_id,
                    'bigcommerce_product_image': image_data,
                    'bigcommerce_product_id': data.get('product_id'),
                    'product_template_id': product_id.id,
                }
                if not self.search([('bigcommerce_product_image_id', '=', data.get('id'))]):
                    self.create(values)
                    _logger.info("Successfully Image Added{0}".format(product_id.id))
                else:
                    self.write(values)
                    _logger.info("Successfully Image Updated : {0}".format(product_id.id))
                product_id.image_1920 = image_data
                self._cr.commit()
                _logger.info("Successfully Import Images {}".format(image_id))
        else:
            _logger.info("Get Some Error {}".format(response))