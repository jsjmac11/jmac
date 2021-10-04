from odoo import models,fields,api
from odoo.exceptions import Warning
from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT


class amazon_inbound_import_shipment_wizard(models.TransientModel):
    _name="amazon.inbound.import.shipment.ept"
    _description = 'amazon.inbound.import.shipment.ept'

    shipment_id = fields.Char('Shipment Id', required=True)
    instance_id = fields.Many2one('amazon.instance.ept', string='Instance', required=True)
    from_warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse", required=True)
    sync_product = fields.Boolean('Sync Product', default=True,
                                  help="Set to True to if you want before import shipment automatically sync the amazon product.")

    def create_amazon_inbound_shipment_line(self, items, inbound_shipment,instance_id):
        amazon_inbound_shipment_plan_line_obj = self.env['inbound.shipment.plan.line']
        amazon_product_obj = self.env['amazon.product.ept']

        for item in items:
            seller_sku = item.get('SellerSKU', {}).get('value','')
            fn_sku = item.get('FulfillmentNetworkSKU', {}).get('value')
            received_qty = float(item.get('QuantityShipped', {}).get('value', 0.0))
            # Added By: Dhaval Sanghani [26-May-2020]
            quantity_in_case = float(item.get('QuantityInCase', {}).get('value', 0.0))

            amazon_product = amazon_product_obj.search_amazon_product(instance_id.id, seller_sku, 'FBA')
            if not amazon_product:
                amazon_product=amazon_product_obj.search([('product_asin','=',fn_sku),('instance_id','=',instance_id.id)],limit=1)
            if not amazon_product:
                raise Warning("Amazon Product is not found in ERP || Seller SKU %s || Instance %s"%(seller_sku,instance_id.name))
            amazon_inbound_shipment_plan_line_obj.\
                create({'amazon_product_id': amazon_product.id,
                        'seller_sku': seller_sku,
                        'quantity': received_qty,
                        'fn_sku': fn_sku,
                        'odoo_shipment_id': inbound_shipment.id,
                        'quantity_in_case': quantity_in_case
                        })
        return True

    def get_list_inbound_shipment_items(self, shipment_id, instance, inbound_shipment):
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo(
        ).get_param('database.uuid')

        items=[]
        kwargs = {'merchant_id':instance.merchant_id and str(instance.merchant_id) or False,
                  'auth_token':instance.auth_token and str(instance.auth_token) or False,
                  'app_name':'amazon_ept',
                  'account_token':account.account_token,
                  'emipro_api':'check_amazon_shipment_status_v13',
                  'dbuuid':dbuuid,
                  'amazon_marketplace_code':instance.country_id.amazon_marketplace_code or
                                            instance.country_id.code,
                  'amazon_shipment_id':shipment_id, }

        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(response.get('reason'))
        else:
            items = response.get('items')

        return self.create_amazon_inbound_shipment_line(items, inbound_shipment,instance)

    def create_amazon_inbound_shipment(self, results, instance_id, from_warehouse_id, ship_to_address=False):
        inbound_shipment = False
        amazon_inbound_shipment_obj = self.env['amazon.inbound.shipment.ept']
        for result in results:
            ShipmentName = result.get('ShipmentName', {}).get('value', False)
            ShipmentId = result.get('ShipmentId', {}).get('value', False)
            fulfillment_center_id = result.get('DestinationFulfillmentCenterId', {}).get('value', False)
            # Added By: Dhaval Sanghani [26-May-2020]
            label_prep_type = result.get('LabelPrepType', {}).get('value', False)
            are_cases_required = result.get('AreCasesRequired', {}).get('value', False)
            are_cases_required = True if are_cases_required.lower() == 'true' else False

            inbound_shipment = amazon_inbound_shipment_obj.create(
                    {'name': ShipmentName, 'fulfill_center_id': fulfillment_center_id,
                     'shipment_id': ShipmentId, 'from_warehouse_id': from_warehouse_id.id,
                     'is_manually_created': True, 'instance_id_ept': instance_id.id,
                     'address_id': ship_to_address, 'label_prep_type': label_prep_type,
                     'are_cases_required': are_cases_required})
        return inbound_shipment

    def get_inbound_import_shipment(self, instance, warehouse_id, shipmnt_id, ship_to_address=False):
        shipment_ids = shipmnt_id.split(',')

        # Added By: Dhaval Sanghani [11-Jun-2020]
        # No Need to Import Duplicate Inbound Shipment
        inbound_shipment = self.env['amazon.inbound.shipment.ept'].search([('shipment_id', 'in', shipment_ids)])

        if inbound_shipment:
            shipments = ", ".join(str(shipment.shipment_id) for shipment in inbound_shipment)
            raise Warning("Shipment Id %s already exists" % shipments)

        # instance = self.instance_id
        for shipment_id in shipment_ids:
            account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
            dbuuid = self.env['ir.config_parameter'].sudo(
            ).get_param('database.uuid')
            amazon_shipments = []

            kwargs = {'merchant_id':instance.merchant_id and str(instance.merchant_id) or False,
                      'auth_token':instance.auth_token and str(instance.auth_token) or False,
                      'app_name':'amazon_ept',
                      'account_token':account.account_token,
                      'emipro_api':'check_status_v13',
                      'dbuuid':dbuuid,
                      'amazon_marketplace_code':instance.country_id.amazon_marketplace_code or
                                                instance.country_id.code,

                      'shipment_ids':[shipment_id], }

            response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
            if response.get('reason'):
                raise Warning(response.get('reason'))
            else:
                amazon_shipments = response.get('amazon_shipments')

            inbound_shipment = self.create_amazon_inbound_shipment(amazon_shipments, instance, warehouse_id, ship_to_address)
            self.get_list_inbound_shipment_items(shipment_id, instance, inbound_shipment)
            inbound_shipment.create_shipment_picking()
