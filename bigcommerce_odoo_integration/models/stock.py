import time
from requests import request
from datetime import datetime
from odoo import models,api,fields,_
import logging

_logger = logging.getLogger("BigCommerce")

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    bc_shipping_provider = fields.Char(string='Shipping Provider', track_visibility='onchange')
    bigcommerce_shimpment_id = fields.Char(string="Bigcommerce Shipment Numebr", track_visibility='onchange')

    def get_order_shipment(self):
        tracking_number = shipping_provider = ''
        shipping_cost = 0.0 
        bigcommerce_store_hash = self.sale_id.bigcommerce_store_id.bigcommerce_store_hash
        bigcommerce_client_seceret  = self.sale_id.bigcommerce_store_id.bigcommerce_x_auth_client
        bigcommerce_x_auth_token = self.sale_id.bigcommerce_store_id.bigcommerce_x_auth_token
        headers = {"Accept": "application/json",
                   "X-Auth-Client": "{}".format(bigcommerce_client_seceret),
                   "X-Auth-Token": "{}".format(bigcommerce_x_auth_token),
                   "Content-Type": "application/json"}
        url = "%s%s/v2/orders/%s/shipments"%(self.sale_id.bigcommerce_store_id.bigcommerce_api_url,bigcommerce_store_hash,self.sale_id.big_commerce_order_id)
        try:
            response = request(method="GET",url=url,headers=headers)
            if response.status_code in [200,201]:
                response = response.json()
                _logger.info("BigCommerce Get Shipment  Response : {0}".format(response))
                for response in response:
                    order_services = self.env['order.service'].search([('name', '=', response.get('shipping_method'))])
                    tracking_number += response.get('tracking_number')
                    shipping_provider += response.get('shipping_provider')
                    shipping_cost += float(response.get('merchant_shipping_cost'))
                    shipment_id = response.get('id')
                    if order_services:
                        self.sale_id.requested_service_id = order_services.id
                self.with_user(1).write({'carrier_price':shipping_cost,'carrier_tracking_ref':tracking_number,'bc_shipping_provider':shipping_provider,'bigcommerce_shimpment_id':shipment_id})
                self.sale_id.with_user(1).bigcommerce_shipment_order_status = 'Shipped'
            else:
                self.with_user(1).message_post(body="Getting an Error in Import Shipment Information : {0}".format(response.content))
        except Exception as e:
            self.with_user(1).message_post(body="Getting an Error in Import Shipment Information : {0}".format(e))

class StockInventory(models.Model):
    _inherit = 'stock.inventory'

    def create_bigcommerce_operation(self, operation, operation_type, bigcommerce_store_id, log_message, warehouse_id):
        vals = {
            'bigcommerce_operation': operation,
            'bigcommerce_operation_type': operation_type,
            'bigcommerce_store': bigcommerce_store_id and bigcommerce_store_id.id,
            'bigcommerce_message': log_message,
            'warehouse_id': warehouse_id and warehouse_id.id or False
        }
        operation_id = self.env['bigcommerce.operation'].create(vals)
        return operation_id

    def create_bigcommerce_operation_detail(self, operation, operation_type, req_data, response_data, operation_id,
                                            warehouse_id=False, fault_operation=False, process_message=False):
        bigcommerce_operation_details_obj = self.env['bigcommerce.operation.details']
        vals = {
            'bigcommerce_operation': operation,
            'bigcommerce_operation_type': operation_type,
            'bigcommerce_request_message': '{}'.format(req_data),
            'bigcommerce_response_message': '{}'.format(response_data),
            'operation_id': operation_id.id,
            'warehouse_id': warehouse_id and warehouse_id.id or False,
            'fault_operation': fault_operation,
            'process_message': process_message
        }
        operation_detail_id = bigcommerce_operation_details_obj.create(vals)
        return operation_detail_id

    def bigcommerce_to_odoo_import_inventory(self, warehouse_id=False, bigcommerce_store_ids=False):
        for bigcommerce_store_id in bigcommerce_store_ids:
            product_inventory_message = "Process Completed Successfully!"
            operation_id = self.create_bigcommerce_operation('stock', 'import', bigcommerce_store_id, 'Processing...',warehouse_id)
            self._cr.commit()
            try:
                product_ids = self.env['product.product'].search([('bigcommerce_product_id','!=',False),('is_exported_to_bigcommerce','=',True)])
                #product_ids = self.env['product.product'].search([('bigcommerce_product_id','=',1146)])
                inventroy_line_obj = self.env['stock.inventory.line']
                inventory_name = "BigCommerce_Inventory_%s"%(str(datetime.now().date()))
                inventory_vals = {
                    'name': inventory_name,
              #      'is_inventory_report': True,
                    'location_ids': [(6,0,warehouse_id.lot_stock_id.ids)],
                    'date': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'company_id': warehouse_id.company_id and warehouse_id.company_id.id or False,
                    'filter': 'partial'
                }
                inventory_id = self.create(inventory_vals)
                for product_id in product_ids:
                    try:
                        if product_id.bigcommerce_product_variant_id:
                            api_operation = "/v3/catalog/products/%s/variants/%s" % (product_id.bigcommerce_product_id, product_id.bigcommerce_product_variant_id)
                            response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(
                                api_operation)
                            _logger.info("BigCommerce Get Product  Response : {0}".format(response_data))

                            if response_data.status_code in [200, 201]:
                                response_data = response_data.json()
                                _logger.info("Inventory Response Data : {0}".format(response_data))
                                records = response_data.get('data')
                                available_quantity = records.get('inventory_level')
                                inventory_line = inventroy_line_obj.create({'product_id': product_id.id,
                                                                        'inventory_id': inventory_id and inventory_id.id,
                                                                        'location_id': warehouse_id.lot_stock_id.id,
                                                                        'product_qty': available_quantity,
                                                                        'product_uom_id': product_id.uom_id and product_id.uom_id.id,
                                                                        })
                                inventory_process_message = "%s : Product Inventory Imported!"%(product_id.name)
                                self.create_bigcommerce_operation_detail('stock', 'import', response_data,
                                                                         api_operation, operation_id,
                                                                         warehouse_id, False, inventory_process_message)
                            else:
                                process_message = "%s : Getting an Error In Import Product Responase : {0}".format(
                                    response_data)
                                _logger.info("Getting an Error In Import Product Responase".format(response_data))
                                self.create_bigcommerce_operation_detail('stock', 'import', response_data,
                                                                 api_operation, operation_id,
                                                                 warehouse_id, True, process_message)
                        else:
                            api_operation = "/v3/catalog/products/%s" % (product_id.bigcommerce_product_id)
                            response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(
                                api_operation)
                            _logger.info("BigCommerce Get Product  Response : {0}".format(response_data))
                            if response_data.status_code in [200, 201]:
                                response_data = response_data.json()
                                _logger.info("Inventory Response Data : {0}".format(response_data))
                                records = response_data.get('data')
                                available_quantity = records.get('inventory_level')
                                inventory_line = inventroy_line_obj.create({'product_id': product_id.id,
                                                                            'inventory_id': inventory_id and inventory_id.id,
                                                                            'location_id': warehouse_id.lot_stock_id.id,
                                                                            'product_qty': available_quantity,
                                                                            'product_uom_id': product_id.uom_id and product_id.uom_id.id,
                                                                            })
                                inventory_process_message = "%s : Product Inventory Imported!" % (
                                    product_id.name)
                                self.create_bigcommerce_operation_detail('stock', 'import', response_data,
                                                                         api_operation, operation_id,
                                                                         warehouse_id, False,
                                                                         inventory_process_message)
                                self._cr.commit()
                            else:
                                process_message = "%s : Getting an Error In Import Product Responase : {0}".format(
                                    response_data)
                                _logger.info(
                                    "Getting an Error In Import Product Responase".format(response_data))
                                self.create_bigcommerce_operation_detail('stock', 'import', response_data,
                                                                         api_operation, operation_id,
                                                                         warehouse_id, True, process_message)


                        self._cr.commit()
                    except Exception as e:
                        product_process_message = "%s : Process Is Not Completed Yet! %s" % (product_id.name, e)
                        _logger.info("Getting an Error In Import Product Responase".format(e))
                        self.create_bigcommerce_operation_detail('stock', 'import', "",
                                                                 "", operation_id,
                                                                 warehouse_id, True, product_process_message)
                inventory_id.action_start()
                inventory_id.action_validate()
                self._cr.commit()
            except Exception as e:
                product_process_message = "Process Is Not Completed Yet! %s" % (e)
                _logger.info("Getting an Error In Import Product Responase".format(e))
                self.create_bigcommerce_operation_detail('product', 'import', "", "",
                                                         operation_id, warehouse_id, True, product_process_message)
            operation_id and operation_id.write({'bigcommerce_message': product_inventory_message})
            self._cr.commit()

    @api.model
    def bigcommerce_to_odoo_import_inventory_using_cronjob(self):
        warehouse_ids = self.env['stock.warehouse'].search([])
        for warehouse_id in warehouse_ids:
            if warehouse_id.bigcommerce_store_ids:
                self.bigcommerce_to_odoo_import_inventory(warehouse_id,warehouse_id.bigcommerce_store_ids)
        return True

