from odoo import models, fields,_
from odoo.tools.float_utils import float_compare, float_round
import time
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from ..endpoint import DEFAULT_ENDPOINT
from odoo.addons.iap.models import iap
import base64

label_preference_help = """     
        SELLER_LABEL - Seller labels the items in the inbound shipment when labels are required.
        AMAZON_LABEL_ONLY - Amazon attempts to label the items in the inbound shipment when 
                            labels are required. If Amazon determines that it does not have the 
                            information required to successfully label an item, that item is not 
                            included in the inbound shipment plan
        AMAZON_LABEL_PREFERRED - Amazon attempts to label the items in the inbound shipment when 
                                labels are required. If Amazon determines that it does not have the 
                                information required to successfully label an item, that item is 
                                included in the inbound shipment plan and the seller must label it.                    
    """

shipment_status_help = """ 
        InboundShipmentHeader is used with the CreateInboundShipment operation: 
            *.WORKING - The shipment was created by the seller, but has not yet shipped.
            *.SHIPPED - The shipment was picked up by the carrier. 

        The following is an additional ShipmentStatus value when InboundShipmentHeader is used with 
        the UpdateInboundShipment operation
            *.CANCELLED - The shipment was cancelled by the seller after the shipment was 
            sent to the Amazon fulfillment center."""


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_total_received_qty_amazon_ept(self):
        for picking in self:
            total_shipped_qty = 0.0
            total_received_qty = 0.0
            for move in picking.move_lines:
                if move.state == 'done':
                    total_received_qty += move.product_qty
                    total_shipped_qty += move.product_qty
                if move.state not in ['draft', 'cancel']:
                    #                     for quant in move.reserved_quant_ids:
                    #                         total_shipped_qty+=quant.qty
                    total_shipped_qty += move.reserved_availability

            picking.total_received_qty = total_received_qty
            picking.total_shipped_qty = total_shipped_qty

    stock_adjustment_report_id = fields.Many2one('amazon.stock.adjustment.report.history',
                                                 string="Stock Adjustment Report")
    removal_order_id = fields.Many2one("amazon.removal.order.ept", string="Removal Order")
    updated_in_amazon = fields.Boolean("Updated In Amazon", default=False, copy=False)
    is_fba_wh_picking = fields.Boolean("Is FBA Warehouse Picking", default=False)
    seller_id = fields.Many2one("amazon.seller.ept", "Seller")
    removal_order_report_id = fields.Many2one('amazon.removal.order.report.history', string="Report")
    ship_plan_id = fields.Many2one('inbound.shipment.plan.ept', readonly=True, default=False,
                                   copy=True, string="Shiment Plan")
    odoo_shipment_id = fields.Many2one('amazon.inbound.shipment.ept', string='Shipment', copy=True)
    amazon_shipment_id = fields.Char(size=120, string='Amazon Shipment ID', default=False,
                                     help="Shipment Item ID provided by Amazon when we integrate "
                                          "shipment report from Amazon")
    fulfill_center = fields.Char(size=120, string='Amazon Fulfillment Center ID', readonly=True,
                                 default=False, copy=True,
                                 help="Fulfillment Center ID provided by Amazon when we send "
                                      "shipment Plan to Amazon")
    ship_label_preference = fields.Selection(
            [('NO_LABEL', 'NO_LABEL'), ('SELLER_LABEL', 'SELLER_LABEL'),
             ('AMAZON_LABEL_ONLY', 'AMAZON_LABEL_ONLY'),
             ('AMAZON_LABEL_PREFERRED', 'AMAZON_LABEL_PREFERRED'), 
             ('AMAZON_LABEL', 'AMAZON_LABEL')], default='SELLER_LABEL',
            string='LabelPrepType', help=label_preference_help)
    total_received_qty = fields.Float(compute="_get_total_received_qty_amazon_ept", string="Total Received Qty")
    total_shipped_qty = fields.Float(compute="_get_total_received_qty_amazon_ept", string="Total Shipped Qty")
    inbound_ship_data_created = fields.Boolean('Inbound Shipment Data Created', default=False)
    are_cases_required = fields.Boolean("AreCasesRequired", default=False,
                                        help="Indicates whether or not an inbound shipment contains "
                                             "case-packed boxes. A shipment must either contain all "
                                             "case-packed boxes or all individually packed boxes")
    shipment_status = fields.Selection(
            [('WORKING', 'WORKING'), ('SHIPPED', 'SHIPPED'), ('CANCELLED', 'CANCELLED')],
            string="Shipment Status", help=shipment_status_help)
    estimated_arrival_date = fields.Datetime("Estimate Arrival Date")
    amazon_shipment_date = fields.Datetime("Shipment Date")
    amazon_purchase_date = fields.Datetime("Purchase Date")
    inbound_ship_updated = fields.Boolean('Inbound Shipment Updated', default=False)
    feed_submission_id = fields.Many2one('feed.submission.history', string="Feed Submission History Id", readonly=True)

    def _amz_stock_picking_put_in_pack_ept(self, operation):
        operation_ids = self.env['stock.move.line']
        if float_compare(operation.qty_done, operation.product_uom_qty,
                         precision_rounding=operation.product_uom_id.rounding) >= 0:
            operation_ids |= operation
        else:
            quantity_left_todo = float_round(
                operation.product_uom_qty - operation.qty_done,
                precision_rounding=operation.product_uom_id.rounding,
                rounding_method='UP')
            new_operation = operation.copy(
                default={'product_uom_qty': operation.qty_done, 'qty_done': operation.qty_done})
            operation.write({'product_uom_qty': quantity_left_todo, 'qty_done': 0.0})
            operation_ids |= new_operation
        return True

    def check_amazon_shipment_status_ept(self, items, job_id):
        log_obj = self.env['common.log.book.ept']        
        log_line_obj = self.env['common.log.lines.ept']
        stock_move_line_obj = self.env['stock.move.line']
        if self.ids:
            pickings = self

        # Commented By: Dhaval Sanghani [11-Jun-2020]
        # Unused Code
        # else:
        #     pickings = self.search([('state', 'in', ['partially_available', 'assigned']),
        #                             ('odoo_shipment_id', '!=', False),
        #                             ('amazon_shipment_id', '!=', False),
        #                             ('is_fba_wh_picking', '=', True)])

        move_obj = self.env['stock.move']
        amazon_product_obj = self.env['amazon.product.ept']

        amazon_shipment_ids = []
        for picking in pickings:
            pack_op_ids = []
            amazon_shipment_ids.append(picking.odoo_shipment_id.id)
            instance = picking.odoo_shipment_id and picking.odoo_shipment_id.instance_id_ept or \
                       picking.ship_plan_id and picking.ship_plan_id.instance_id

            process_picking=False
            for item in items:
                sku = item.get('SellerSKU', {}).get('value', '')
                asin = item.get('FulfillmentNetworkSKU', {}).get('value')
                shipped_qty = item.get('QuantityShipped', {}).get('value')
                received_qty = float(item.get('QuantityReceived', {}).get('value', 0.0))

                if received_qty <= 0.0:
                    continue
                amazon_product = amazon_product_obj.search_amazon_product(instance.id, sku, 'FBA')
                if not amazon_product:
                    amazon_product = amazon_product_obj.search(
                            [('product_asin', '=', asin), ('instance_id', '=', instance.id),
                             ('fulfillment_by', '=', 'FBA')], limit=1)
                if not amazon_product:
                    if not job_id:
                        job_id = log_obj.create({'module':'amazon_ept', 'type':'import'})
                    vals = {
                            'message':"""Product not found in ERP ||| 
                                                    FulfillmentNetworkSKU : %s
                                                    SellerSKU : %s  
                                                    Shipped Qty : %s
                                                    Received Qty : %s                          
                                                 """ % (asin, sku, shipped_qty, received_qty),
                            'model_id':log_line_obj.get_model_id('amazon.inbound.shipment.ept'),
                            'res_id':picking.odoo_shipment_id.id,
                            'log_line_id':job_id.id
                            }
                    log_line_obj.create(vals)
                    continue

                inbound_shipment_plan_line = picking.odoo_shipment_id.odoo_shipment_line_ids.\
                                                   filtered(lambda line: line.amazon_product_id.id == amazon_product.id)

                if inbound_shipment_plan_line:
                    inbound_shipment_plan_line[0].received_qty = received_qty or 0.0

                else:
                    vals = {
                        'amazon_product_id': amazon_product.id,
                        'quantity': shipped_qty or 0.0,
                        'odoo_shipment_id': picking.odoo_shipment_id.id,
                        'fn_sku': asin,
                        'received_qty': received_qty,
                        'is_extra_line': True
                    }
                    inbound_shipment_plan_line.create(vals)

                odoo_product_id = amazon_product and amazon_product.product_id.id or False

                done_moves=picking.odoo_shipment_id.picking_ids.filtered(lambda r:r.is_fba_wh_picking==True and r.amazon_shipment_id==picking.amazon_shipment_id).mapped('move_lines').filtered(
                                                            lambda r:r.product_id.id==odoo_product_id and r.state=='done')
                source_location_id = picking.location_id.id
                # source_location_id = done_moves and done_moves[0].location_id.id
                for done_move in done_moves:
                    if done_move.location_dest_id.id != source_location_id:
                        received_qty = received_qty - done_move.product_qty
                    else:
                        received_qty = received_qty + done_move.product_qty
                if received_qty <= 0.0:
                    continue

                move_lines = picking.move_lines.filtered(lambda
                                                             move_lines:move_lines.product_id.id == odoo_product_id and move_lines.state not in (
                'draft', 'done', 'cancel', 'waiting'))

                if not move_lines:
                    move_lines = picking.move_lines.filtered(lambda
                                                                 move_line:move_line.product_id.id == odoo_product_id and move_line.state not in (
                    'draft', 'done', 'cancel'))

                waiting_moves=move_lines and move_lines.filtered(lambda r:r.state=='waiting')
                waiting_moves and waiting_moves.write({'state':'assigned'})

                if not move_lines:
                    process_picking = True
                    # Commented By: Dhaval Sanghani [16-Jun-2020]
                    # Purpose: No use in code
                    # move = picking.move_lines[0]
                    odoo_product = amazon_product.product_id
                    new_move = move_obj.create({
                        'name':_('New Move:') + odoo_product.display_name,
                        'product_id':odoo_product.id,
                        'product_uom_qty':received_qty,
                        'product_uom':odoo_product.uom_id.id,
                        'location_id':picking.location_id.id,
                        'location_dest_id':picking.location_dest_id.id,
                        'picking_id':picking.id,
                    })
                    stock_move_line_obj.create(
                            {
                                # Commented By: Dhaval Sanghani [16-Jun-2020]
                                # Purpose: Set product_id of amazon_product.product_id not move.product_id
                                # 'product_id':move.product_id.id,
                                # 'product_uom_id':move.product_id.uom_id.id,
                                'product_id': odoo_product.id,
                                'product_uom_id': odoo_product.uom_id.id,
                                'picking_id':picking.id,
                                'qty_done':float(received_qty) or 0,
                                # Commented and Added By: Dhaval Sanghani [04-Jun-2020]
                                # Purpose: No field 'ordered_qty' in stock.move.line
                                # 'ordered_qty':float(received_qty) or 0,
                                'location_id':picking.location_id.id,
                                'location_dest_id':picking.location_dest_id.id,
                                'move_id':new_move.id,
                            })

                qty_left = received_qty
                for move in move_lines:
                    process_picking = True
                    if move.state == 'waiting':
                        move.write({'state':'assigned'})
                    if qty_left <= 0.0:
                        break
                    move_line_remaning_qty = (move.product_uom_qty) - (
                        sum(move.move_line_ids.mapped('qty_done')))
                    operations = move.move_line_ids.filtered(lambda o:o.qty_done <= 0)
                    for operation in operations:
                        if operation.product_uom_qty <= qty_left:
                            op_qty = operation.product_uom_qty
                        else:
                            op_qty = qty_left

                        # Commented and Added By: Dhaval Sanghani [04-Jun-2020]
                        move._set_quantity_done(op_qty)
                        # operation.write({'qty_done':op_qty})
                        # self._amz_stock_picking_put_in_pack_ept(operation)
                        qty_left = float_round(qty_left - op_qty,
                                               precision_rounding=operation.product_uom_id.rounding,
                                               rounding_method='UP')
                        move_line_remaning_qty = move_line_remaning_qty - op_qty
                        if qty_left <= 0.0:
                            break
                    if qty_left > 0.0 and move_line_remaning_qty > 0.0 and move.product_id.tracking =='none':
                        # process_picking = False
                        if move_line_remaning_qty <= qty_left:
                            op_qty = move_line_remaning_qty
                        else:
                            op_qty = qty_left
                        stock_move_line_obj.create(
                                {
                                    'product_id':move.product_id.id,
                                    'product_uom_id':move.product_id.uom_id.id,
                                    'picking_id':picking.id,
                                    'qty_done':float(op_qty) or 0,
                                    # Commented and Added By: Dhaval Sanghani [04-Jun-2020]
                                    # Purpose: No field 'ordered_qty' in stock.move.line
                                    # 'ordered_qty':float(op_qty) or 0,
                                    'result_package_id':False,
                                    'location_id':picking.location_id.id,
                                    'location_dest_id':picking.location_dest_id.id,
                                    'move_id':move.id,
                                })
                        qty_left = float_round(qty_left - op_qty,
                                               precision_rounding=move.product_id.uom_id.rounding,
                                               rounding_method='UP')
                        if qty_left <= 0.0:
                            break
                move = move_lines[0] if move_lines else new_move
                if qty_left > 0.0 and move.product_id.tracking =='none':
                    # process_picking = False
                    stock_move_line_obj.create(
                            {
                                'product_id':move.product_id.id,
                                'product_uom_id':move.product_id.uom_id.id,
                                'picking_id':picking.id,
                                # Commented and Added By: Dhaval Sanghani [04-Jun-2020]
                                # Purpose: No field 'ordered_qty' in stock.move.line
                                # 'ordered_qty':float(qty_left) or 0,
                                'qty_done':float(qty_left) or 0,
                                'result_package_id':False,
                                'location_id':picking.location_id.id,
                                'location_dest_id':picking.location_dest_id.id,
                                'move_id':move.id,
                            })
            if process_picking:
                try:
                    picking.with_context({'auto_processed_orders_ept':True}).action_done()
                except Exception as e:
                    if not job_id:
                        job_id = log_obj.create({'module': 'amazon_ept', 'type': 'import'})
                    vals = {
                        # 'message': """Picking [%s] has Product with Lot/Serial NUmber"""%(picking.display_name) ,
                        'message': "%s" % str(e),
                        'model_id': log_line_obj.get_model_id('amazon.inbound.shipment.ept'),
                        'res_id': picking.odoo_shipment_id.id,
                        'log_line_id': job_id.id
                    }
                    log_line_obj.create(vals)
        return True

    def check_qty_difference_and_create_return_picking_ept(self,amazon_shipment_id,odoo_shipment_id,instance,items):
        pickings=odoo_shipment_id.picking_ids.filtered(lambda picking:picking.state == 'done' and picking.amazon_shipment_id == amazon_shipment_id and picking.is_fba_wh_picking == True)
        if not pickings:
            return True
        location_id = pickings[0].location_id.id
        location_dest_id = pickings[0].location_dest_id.id
        # move_obj = self.env['stock.move']
        return_picking = False
        amazon_product_obj = self.env['amazon.product.ept']
        for item in items:
            sku = item.get('SellerSKU',{}).get('value','')
            asin=item.get('FulfillmentNetworkSKU',{}).get('value')
            received_qty = float(item.get('QuantityReceived',{}).get('value',0.0))
            amazon_product = amazon_product_obj.search_amazon_product(instance.id,sku,'FBA')
            if not amazon_product:
                amazon_product=amazon_product_obj.search([('product_asin','=',asin),
                                                          ('instance_id','=',instance.id),
                                                          ('fulfillment_by','=','FBA')],limit=1)
            if not amazon_product:
                continue

            done_moves=odoo_shipment_id.picking_ids.filtered(lambda r:r.is_fba_wh_picking==True and
                                                            r.amazon_shipment_id==amazon_shipment_id).mapped('move_lines').filtered(lambda
                                                            r:r.product_id.id == amazon_product.product_id.id and
                                                              r.state == 'done' and r.location_id.id == location_id
                                                              and r.location_dest_id.id == location_dest_id)

            if received_qty <=0.0 and (not done_moves):
                continue
            for done_move in done_moves:
                received_qty=received_qty-done_move.product_qty

            if received_qty <0.0:
                return_moves=odoo_shipment_id.picking_ids.filtered(lambda r:r.is_fba_wh_picking==True and
                                                                r.amazon_shipment_id == amazon_shipment_id).mapped(
                                                                'move_lines').filtered(lambda r:r.product_id.id==amazon_product.product_id.id
                                                                and r.state == 'done' and r.location_id.id==location_dest_id and r.location_dest_id.id==location_id)

                for return_move in return_moves:
                    received_qty=received_qty+return_move.product_qty
                if received_qty>=0.0:
                    continue
                if not return_picking:
                    pick_type_id = pickings[0].picking_type_id.return_picking_type_id and pickings[0].picking_type_id.return_picking_type_id.id or pickings[0].picking_type_id.id
                    return_picking = pickings[0].copy({
                        'move_lines': [],
                        'picking_type_id': pick_type_id,
                        'state': 'draft',
                        'origin': amazon_shipment_id,
                        'date_done':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                    })
                received_qty=abs(received_qty)
                for move in done_moves:
                    if move.product_qty<=received_qty:
                        return_qty=move.product_qty
                    else:
                        return_qty=received_qty
                    move.copy({
                        'product_id':move.product_id.id,
                        'product_uom_qty':abs(received_qty),
                        'picking_id':return_picking.id,
                        'state':'draft',
                        'location_id':move.location_dest_id.id,
                        'location_dest_id':move.location_id.id,
                        'picking_type_id':pick_type_id,
                        'warehouse_id':pickings[0].picking_type_id.warehouse_id.id,
                        'origin_returned_move_id':move.id,
                        'procure_method':'make_to_stock',
                        'move_dest_ids':[],
                    })
                    received_qty=received_qty-return_qty
                    if received_qty<=0.0:
                        break
        if return_picking:
            return_picking.action_confirm()
            return_picking.action_assign()
            self.env['stock.immediate.transfer'].create({'pick_ids':[(4, return_picking.id)]}).process()
        return True


    def check_amazon_shipment_status(self):
        if self.ids:
            pickings = self
        move_obj = self.env['stock.move']
        amazon_product_obj = self.env['amazon.product.ept']
        stock_move_line_obj = self.env['stock.move.line']
        inbound_shipment_plan_line_obj = self.env['inbound.shipment.plan.line']
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        amazon_shipment_ids = []
        for picking in pickings:
            odoo_shipment_id = picking.odoo_shipment_id and picking.odoo_shipment_id.id
            amazon_shipment_ids.append(odoo_shipment_id)
            instance = picking.odoo_shipment_id.get_instance(picking.odoo_shipment_id)
            kwargs = {'merchant_id':instance.merchant_id and str(instance.merchant_id) or False,
                      'auth_token':instance.auth_token and str(instance.auth_token) or False,
                      'app_name':'amazon_ept',
                      'account_token':account.account_token,
                      'emipro_api':'check_amazon_shipment_status_v13',
                      'dbuuid':dbuuid,
                      'amazon_marketplace_code':instance.country_id.amazon_marketplace_code or
                                                instance.country_id.code,
                      'amazon_shipment_id':picking.amazon_shipment_id, }

            response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
            if response.get('reason'):
                raise Warning(response.get('reason'))
            else:
                items = response.get('items')
                datas = response.get('datas')
            for data in datas:
                file_name = 'inbound_shipment_report_%s.xml' % (picking.id)
                attachment = self.env['ir.attachment'].create({
                    'name':file_name,
                    'datas':base64.b64encode((data.get('origin')).encode('utf-8')),
                    'res_model':'mail.compose.message',
                })
                picking.message_post(body=_("<b> Inbound Shipment Report Downloaded </b>"),
                                     attachment_ids=attachment.ids)

            process_picking = False
            for item in items:
                sku = item.get('SellerSKU', {}).get('value', '')
                asin = item.get('FulfillmentNetworkSKU', {}).get('value', '')
                shipped_qty = item.get('QuantityShipped', {}).get('value')
                received_qty = float(item.get('QuantityReceived', {}).get('value', 0.0))
                if received_qty <= 0.0:
                    continue
                amazon_product = amazon_product_obj.search_amazon_product(instance.id, sku, 'FBA')
                if not amazon_product:
                    amazon_product = amazon_product_obj.search(
                            [('product_asin', '=', asin), ('instance_id', '=', instance.id),
                             ('fulfillment_by', '=', 'FBA')], limit=1)
                if not amazon_product:
                    picking.message_post(body=_("""Product not found in ERP ||| 
                                                FulfillmentNetworkSKU : %s
                                                SellerSKU : %s  
                                                Shipped Qty : %s
                                                Received Qty : %s                          
                                             """ % (asin, sku, shipped_qty, received_qty)))
                    continue
                inbound_shipment_plan_line_id = picking.odoo_shipment_id.odoo_shipment_line_ids.\
                    filtered(lambda line: line.amazon_product_id.id == amazon_product.id)
                if inbound_shipment_plan_line_id:
                    inbound_shipment_plan_line_id[0].received_qty = received_qty or 0.0
                else:
                    vals = {
                        'amazon_product_id':amazon_product.id,
                        'quantity':shipped_qty or 0.0,
                        'odoo_shipment_id':odoo_shipment_id,
                        'fn_sku':asin,
                        'received_qty':received_qty,
                        'is_extra_line':True
                    }
                    inbound_shipment_plan_line_obj.create(vals)
                odoo_product_id = amazon_product and amazon_product.product_id.id or False
                done_moves=picking.odoo_shipment_id.picking_ids.filtered(lambda r:r.amazon_shipment_id==picking.amazon_shipment_id and
                                                                        r.is_fba_wh_picking == True).mapped(
                                                                        'move_lines').filtered(lambda r:r.product_id.id==odoo_product_id and r.state=='done')
                # source_location_id = done_moves and done_moves[0].location_id.id
                source_location_id = picking.location_id.id
                for done_move in done_moves:
                    if done_move.location_dest_id.id != source_location_id:
                        received_qty = received_qty - done_move.product_qty
                    else:
                        received_qty = received_qty + done_move.product_qty
                if received_qty <= 0.0:
                    continue
                move_lines=picking.move_lines.filtered(lambda r:r.product_id.id==odoo_product_id
                                            and r.state not in ('draft', 'done', 'cancel','waiting'))
                if not move_lines:
                    move_lines = picking.move_lines.filtered(
                        lambda r:r.product_id.id == odoo_product_id
                                 and r.state not in ('draft', 'done', 'cancel'))
                waiting_moves=move_lines and move_lines.filtered(lambda r:r.state=='waiting')
                waiting_moves and waiting_moves.write({'state':'assigned'})
                if not move_lines :
                    process_picking = True
                    odoo_product = amazon_product.product_id
                    new_move = move_obj.create({
                        'name':_('New Move:') + odoo_product.display_name,
                        'product_id':odoo_product.id,
                        'product_uom_qty':received_qty,
                        'product_uom':odoo_product.uom_id.id,
                        'location_id':picking.location_id.id,
                        'location_dest_id':picking.location_dest_id.id,
                        'picking_id':picking.id,
                    })
                    stock_move_line_obj.create(
                            {
                                # Purpose: Set product_id of amazon_product.product_id not move.product_id
                                'product_id': odoo_product.id,
                                'product_uom_id': odoo_product.uom_id.id,
                                'picking_id':picking.id,
                                'qty_done':float(received_qty) or 0,
                                'location_id':picking.location_id.id,
                                'location_dest_id':picking.location_dest_id.id,
                                'move_id':new_move.id,
                            })
                qty_left = received_qty
                for move in move_lines:
                    process_picking = True
                    if move.state == 'waiting':
                        move.write({'state':'assigned'})
                    if qty_left <= 0.0:
                        break
                    move_line_remaning_qty = (move.product_uom_qty) - (
                        sum(move.move_line_ids.mapped('qty_done')))
                    operations = move.move_line_ids.filtered(lambda o:o.qty_done <= 0)
                    for operation in operations:
                        if operation.product_uom_qty <= qty_left:
                            op_qty = operation.product_uom_qty
                        else:
                            op_qty = qty_left
                        # Commented and Added By: Dhaval Sanghani [04-Jun-2020]
                        move._set_quantity_done(op_qty)
                        # operation.write({'qty_done':op_qty})
                        # self._amz_stock_picking_put_in_pack_ept(operation)
                        qty_left = float_round(qty_left - op_qty,
                                               precision_rounding=operation.product_uom_id.rounding,
                                               rounding_method='UP')
                        move_line_remaning_qty = move_line_remaning_qty - op_qty
                        if qty_left <= 0.0:
                            break
                    if qty_left > 0.0 and move_line_remaning_qty > 0.0 and move.product_id.tracking =='none':
                        if move_line_remaning_qty <= qty_left:
                            op_qty = move_line_remaning_qty
                        else:
                            op_qty = qty_left
                        stock_move_line_obj.create(
                                {
                                    'product_id':move.product_id.id,
                                    'product_uom_id':move.product_id.uom_id.id,
                                    'picking_id':picking.id,
                                    'qty_done':float(op_qty) or 0,
                                    'result_package_id':False,
                                    'location_id':picking.location_id.id,
                                    'location_dest_id':picking.location_dest_id.id,
                                    'move_id':move.id,
                                })
                        qty_left = float_round(qty_left - op_qty,
                                               precision_rounding=move.product_id.uom_id.rounding,
                                               rounding_method='UP')
                        if qty_left <= 0.0:
                            break
                move = move_lines[0] if move_lines else new_move
                if qty_left > 0.0 and move.product_id.tracking =='none':
                    stock_move_line_obj.create(
                        {
                            'product_id':move.product_id.id,
                            'product_uom_id':move.product_id.uom_id.id,
                            'picking_id':picking.id,
                            'qty_done':float(qty_left) or 0,
                            'result_package_id':False,
                            'location_id':picking.location_id.id,
                            'location_dest_id':picking.location_dest_id.id,
                            'move_id':move.id,
                        })
            process_picking and picking.with_context({'auto_processed_orders_ept':True}).action_done()
        return True

    def update_shipment_quantity(self):
        amazon_product_obj = self.env['amazon.product.ept']
        plan_line_obj = self.env['inbound.shipment.plan.line']

        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo(
        ).get_param('database.uuid')

        for picking in self:
            odoo_shipment = picking.odoo_shipment_id
            ship_plan = picking.ship_plan_id
            instance = ship_plan.instance_id
            shipment_status = 'WORKING'
            destination = odoo_shipment.shipment_plan_id.ship_to_country.code
            if not odoo_shipment.shipment_id or not odoo_shipment.fulfill_center_id:
                raise Warning('You must have to first create Inbound Shipment Plan.')

            # Added By: Dhaval Sanghani [11-Jun-2020]
            label_prep_type = odoo_shipment.label_prep_type
            if label_prep_type == 'NO_LABEL':
                label_prep_type = 'SELLER_LABEL'
            elif label_prep_type == 'AMAZON_LABEL':
                label_prep_type = ship_plan.label_preference

            for x in range(0, len(picking.move_lines), 20):
                move_lines = picking.move_lines[x:x + 20]
                sku_qty_dict = {}
                for move in move_lines:
                    amazon_product = amazon_product_obj.search(
                            [('product_id', '=', move.product_id.id),
                             ('instance_id', '=', instance.id),
                             ('fulfillment_by', '=', 'FBA')], limit=1)
                    if not amazon_product:
                        raise Warning("Amazon Product is not available for this %s product code" % (
                            move.product_id.default_code))

                    line = plan_line_obj.search([('odoo_shipment_id', '=', odoo_shipment.id),
                                                 ('amazon_product_id', 'in', amazon_product.ids)])
                    sku_qty_dict.update({str(
                            line and line.seller_sku or amazon_product[0].seller_sku):str(
                            int(move.reserved_availability))})

                    kwargs = {
                        'merchant_id':instance.merchant_id and str(instance.merchant_id) or False,
                        'auth_token':instance.auth_token and str(instance.auth_token) or False,
                        'app_name':'amazon_ept',
                        'account_token':account.account_token,
                        'emipro_api':'update_shipment_in_amazon_v13',
                        'dbuuid':dbuuid,
                        'amazon_marketplace_code':instance.country_id.amazon_marketplace_code or
                                                  instance.country_id.code,
                        'shipment_name':odoo_shipment.name,
                        'shipment_id':odoo_shipment.shipment_id,
                        'labelpreppreference': label_prep_type,
                        'shipment_status': shipment_status,
                        'inbound_box_content_status': odoo_shipment.intended_boxcontents_source,
                        'cases_required':odoo_shipment.are_cases_required,
                        'destination':destination,}

                    response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
                    if response.get('reason'):
                        raise Warning(response.get('reason'))

            picking.write({'inbound_ship_updated':True})
        return True

    def check_qty_difference_and_create_return_picking(self, amazon_shipment_id, odoo_shipment_id, instance):
        pickings = self.search([('state', '=', 'done'),
                                ('odoo_shipment_id', '=', odoo_shipment_id),
                                ('amazon_shipment_id', '=', amazon_shipment_id),
                                ('is_fba_wh_picking', '=', True)], order="id")
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        stock_immediate_transfer_obj = self.env['stock.immediate.transfer']
        amazon_product_obj = self.env['amazon.product.ept']
        location_id = pickings[0].location_id.id
        location_dest_id = pickings[0].location_dest_id.id
        # move_obj = self.env['stock.move']
        return_picking = False
        attachment_ids = []
        kwargs = {'merchant_id':instance.merchant_id and str(instance.merchant_id) or False,
                  'auth_token':instance.auth_token and str(instance.auth_token) or False,
                  'app_name':'amazon_ept',
                  'account_token':account.account_token,
                  'emipro_api':'check_amazon_shipment_status_v13',
                  'dbuuid':dbuuid,
                  'amazon_marketplace_code':instance.country_id.amazon_marketplace_code or
                                            instance.country_id.code,
                  'amazon_shipment_id':amazon_shipment_id}
        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(response.get('reason'))
        else:
            items = response.get('items')
            datas = response.get('datas')
        for data in datas:
            file_name = 'inbound_shipment_report_%s.xml' % (amazon_shipment_id)
            # if data.get('next_tone'):
            #     file_name = 'inbound_shipment_report_%s_%s.xml' % (amazon_shipment_id, str(data.get('next_token')))
            attachment = self.env['ir.attachment'].create({
                'name':file_name,
                'datas':base64.b64encode((data.get('origin')).encode('utf-8')),
                #'datas_fname':file_name,
                'res_model':'mail.compose.message',
            })
            attachment_ids.append(attachment.id)

        for item in items:
            sku = item.get('SellerSKU', {}).get('value', '')
            asin = item.get('FulfillmentNetworkSKU', {}).get('value')
            received_qty = float(item.get('QuantityReceived', {}).get('value', 0.0))
            amazon_product = amazon_product_obj.search_amazon_product(instance.id, sku, 'FBA')
            if not amazon_product:
                amazon_product = amazon_product_obj.search(
                        [('product_asin', '=', asin), ('instance_id', '=', instance.id),
                         ('fulfillment_by', '=', 'FBA')], limit=1)
            if not amazon_product:
                continue
            shipment_pickings=self.search([('odoo_shipment_id','=',odoo_shipment_id), ('is_fba_wh_picking','=',True),
                                           ('amazon_shipment_id','=',amazon_shipment_id)])
            done_moves=shipment_pickings.mapped('move_lines').filtered(lambda r:r.state=='done'and
                                                                    r.product_id.id == amazon_product.product_id.id and
                                                                    r.location_dest_id.id==location_dest_id and r.location_id.id==location_id)
            if received_qty <= 0.0 and (not done_moves):
                continue
            for done_move in done_moves:
                received_qty = received_qty - done_move.product_qty
            if received_qty < 0.0:
                return_moves=shipment_pickings.move_lines.filtered(lambda r:r.product_id.id==amazon_product.product_id.id and
                                                                    r.state=='done' and r.location_id.id==location_dest_id
                                                                    and r.location_dest_id.id==location_id)
                for return_move in return_moves:
                    received_qty = received_qty + return_move.product_qty
                if received_qty >= 0.0:
                    continue
                if not return_picking:
                    pick_type_id = pickings[0].picking_type_id.return_picking_type_id and pickings[
                        0].picking_type_id.return_picking_type_id.id or pickings[0].picking_type_id.id
                    return_picking = pickings[0].copy({
                        'move_lines':[],
                        'picking_type_id':pick_type_id,
                        'state':'draft',
                        'origin':amazon_shipment_id,
                        'location_id':done_moves[0].location_dest_id.id,
                        'location_dest_id':done_moves[0].location_id.id,
                    })
                    return_picking.message_post(
                            body=_("<b> Inbound Shipment Report Downloaded </b>"),
                            attachment_ids=attachment_ids)
                received_qty = abs(received_qty)
                for move in done_moves:
                    if move.product_qty <= received_qty:
                        return_qty = move.product_qty
                    else:
                        return_qty = received_qty
                    move.copy({
                        'product_id':move.product_id.id,
                        'product_uom_qty':abs(received_qty),
                        'picking_id':return_picking.id,
                        'state':'draft',
                        'location_id':move.location_dest_id.id,
                        'location_dest_id':move.location_id.id,
                        'picking_type_id':pick_type_id,
                        'warehouse_id':pickings[0].picking_type_id.warehouse_id.id,
                        'origin_returned_move_id':move.id,
                        'procure_method':'make_to_stock',
                        'move_dest_ids':[],
                    })
                    received_qty = received_qty - return_qty
                    if received_qty <= 0.0:
                        break
        if return_picking:
            return_picking.action_confirm()
            return_picking.action_assign()
            stock_immediate_transfer_obj.create({'pick_ids':[(4, return_picking.id)]}).process()
        else:
            attachments = self.env['ir.attachment'].browse(attachment_ids)
            attachments.unlink()
        return True