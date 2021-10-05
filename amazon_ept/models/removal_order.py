import base64
import time
from odoo import models, fields, api, _
from tempfile import NamedTemporaryFile
from odoo.exceptions import Warning
from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT


class removal_order(models.Model):
    _name = "amazon.removal.order.ept"
    _description = "Removal Order"
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char("Name")
    removal_disposition = fields.Selection([('Return', 'Return'), ('Disposal', 'Disposal')], default='Return',
                                           required=True, help="This Fields relocates type of disposition.")
    ship_address_id = fields.Many2one('res.partner', string='Ship Address', readonly=True,
                                      states={'draft': [('readonly', False)]}, help="This Fields relocates partner.")
    shipping_notes = fields.Text("Notes", help="This Fields relocates shipping notes.")
    instance_id = fields.Many2one('amazon.instance.ept', string='Instance', required=True, readonly=True,
                                  states={'draft': [('readonly', False)]},
                                  help="This Fields relocates amazon instance.")
    warehouse_id = fields.Many2one("stock.warehouse",
                                   string="Destination Warehouse",
                                   help="This Fields relocates stock warehouse.")
    disposition_location_id = fields.Many2one("stock.location",
                                              related="instance_id.fba_warehouse_id.unsellable_location_id",
                                              readonly=True,
                                              help="This Fields relocates stock destination location.")
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True,
                                 states={'draft': [('readonly', False)]},
                                 help="This Fields relocates comapny id.")
    state = fields.Selection([('draft', 'Draft'),
                              ('plan_approved', 'Removal Plan Approved'),
                              ('Cancelled', 'Cancelled'),
                              ('In Process', 'In Process'),
                              ('Completed', 'Completed')
                              ], default='draft',
                             string='State', help="This Fields relocates state.")
    removal_order_lines_ids = fields.One2many("removal.orders.lines.ept", 'removal_order_id',
                                              string="Removal Orders Lines",
                                              help="This Fields relocates removal order lines ids.")
    last_feed_submission_id = fields.Char("Feed Submission Id",
                                          help="This Fields relocates last feed submission id.")
    removal_order_picking_ids = fields.One2many("stock.picking", 'removal_order_id', string="Removal Pickings",
                                                help="This Fields relocates removal order picking ids.")
    removal_count = fields.Integer("Removal Order Pickings", compute="removal_count_records",
                                   help="This Fields relocates removal count.")

    def write(self, vals):
        """
        This Method write if removal disposition getting in value.Check type of disposition and write removal disposition and sellable quantity.
        :param vals: This arguments relocates write values getting.
        :return: This Method return call super and write values
        """
        if 'removal_disposition' in vals:
            if vals.get('removal_disposition') == 'Disposal':
                self.removal_order_lines_ids.write({'removal_disposition': 'Disposal', 'sellable_quantity': 0.0})
            else:
                self.removal_order_lines_ids.write({'removal_disposition': 'Return'})
        return super(removal_order, self).write(vals)

    def import_product_for_removal_order(self):

        """
        This Method relocates open wizard to import product csv file.
        File contains only product sku and quantity.
        :return:This Method return call wizard view and open wizard.
        """
        import_obj = self.env['import.product.removal.order.wizard'].create({'removal_order_id': self.id})

        ctx = self._context.copy()
        ctx.update({'removal_order_id': self.id, 'update_existing': False, })
        return import_obj.with_context(ctx).wizard_view()

    def removal_count_records(self):
        """
        This Method relocates removal count records.
        """
        for record in self:
            record.removal_count = len(record.removal_order_picking_ids.ids)

    def get_unsellable_products(self):
        """
        This Method get unsellable product using company.If company false in product .product then get product using user company.
        :return: This Method return Boolean(True/False).
        If Product getting using company and unsellable stock greater than 0 in this cases write unsellable quantity, sellable quantity and removal disposition.
        """
        removal_order_line_obj = self.env['removal.orders.lines.ept']
        odoo_product = self.env['product.product'].search(
            ['|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])
        products = self.env['amazon.product.ept'].search(
            [('product_id', 'in', odoo_product.ids), ('instance_id', '=', self.instance_id.id),
             ('fulfillment_by', '=', 'FBA')])
        for product in products:
            unsellable_stock = product.product_id.with_context(
                {'location': self.instance_id.fba_warehouse_id.unsellable_location_id.id}).qty_available
            if unsellable_stock > 0.0:
                line = removal_order_line_obj.search(
                    [('amazon_product_id', '=', product.id), ('removal_order_id', '=', self.id)])
                if line:
                    line.write({'unsellable_quantity': unsellable_stock, 'sellable_quantity': 0.0,
                                'removal_disposition': self.removal_disposition})
                else:
                    removal_order_line_obj.create({
                        'amazon_product_id': product.id,
                        'unsellable_quantity': unsellable_stock,
                        'removal_order_id': self.id,
                        'removal_disposition': self.removal_disposition
                    })
        return True

    @api.onchange('instance_id', 'warehouse_id')
    def onchange_instance_id(self):
        """
        This Method relocates onchange instance id and warehouse id.
        if removal warehouse id not getting from instance in this cases set instance warehouse id.
        If removal warehouse getting from instance in this cases set removal warehouse id as self warehouse id.
        """
        if self.instance_id:
            warehouse = self.instance_id.removal_warehouse_id
            if not warehouse:
                warehouse = self.instance_id.warehouse_id
            if warehouse:
                self.warehouse_id = warehouse.id
                self.ship_address_id = warehouse.partner_id and warehouse.partner_id.id or False
            self.company_id = self.instance_id.company_id.id

    def list_of_transfer_removal_pickings(self):
        """
        This Method return list of transfer removal pickings.
        :return:This Method return action of pickings.
        """
        action = {
            'domain': "[('id', 'in', " + str(self.removal_order_picking_ids.ids) + " )]",
            'name': 'Removal Order Pickings',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'stock.picking',
            'type': 'ir.actions.act_window',
        }
        return action

    def check_validate_fields(self):
        """
        This Method check validate fields and raise warning.Check all type of validation like check removal order line, check removal order config ids etc..
        :return: This Method return Boolean(True/False).
        """
        address = self.ship_address_id
        if self.removal_disposition == 'Return':
            message = "One of address required fields are not set like street,city,country,state,zip,phone"
        else:
            message = "One of address required fields are not set like street,city,country,state,zip"

        if not (
                address.street or address.street2) or not address.city or not address.country_id or not address.state_id or not address.zip or \
                (self.removal_disposition == 'Return' and not (address.phone or address.mobile)):
            raise Warning(message)
        if not self.removal_order_lines_ids:
            raise Warning("Invalid lines found for request")
        lines = self.env['removal.orders.lines.ept'].search(
            [('sellable_quantity', '<=', 0.0), ('unsellable_quantity', '<=', 0.0),
             ('id', 'in', self.removal_order_lines_ids.ids)])
        seller_skus = [x.seller_sku for x in list(lines)]
        if seller_skus:
            raise Warning("Invalid Lines found for request %s" % (','.join(seller_skus)))
        if self.removal_disposition == 'Disposal' and not self.instance_id.fba_warehouse_id.unsellable_location_id:
            raise Warning("Unsellable Location not found in FBA warehouse")
        if not self.instance_id.removal_order_config_ids:
            raise Warning("Removal order configuration missing in seller")
        config = self.env['removal.order.config.ept'].search(
            [('id', 'in', self.instance_id.removal_order_config_ids.ids),
             ('removal_disposition', '=', self.removal_disposition)])
        if not config:
            raise Warning("Removal Order configuration missing for disposition %s" % (self.removal_disposition))
        if self.removal_disposition == 'Return' and (not config.unsellable_route_id or not config.sellable_route_id):
            raise Warning("Route Configuration is missing in seller")
        if self.removal_disposition == 'Disposal' and (not config.picking_type_id or not config.location_id):
            raise Warning("Location or picking type configuration is missing in seller")
        if self.removal_order_picking_ids.filtered(lambda picking: picking.state != 'cancel'):
            raise Warning("Pickings already exist for removal order first you should cancel all pickings")
        return True

    def create_removal_order(self):
        """
        This Method create removal order prepare csv of removal order for Amazon.
        After create amazon csv create removal order procurement group and create disposal order pickings.
        :return: This Method return Boolean(True/False).
        """
        self.ensure_one()
        amazon_process_job_log_obj = self.env['common.log.book.ept']
        ctx = self._context.copy()
        model_id = self.env['ir.model']._get('amazon.removal.order.ept').id

        job = amazon_process_job_log_obj.search(
                [('model_id', '=', model_id),
                 ('res_id', '=', self.id)])
        if not job:
            job = amazon_process_job_log_obj.create({
                'module': 'amazon_ept',
                'type': 'import',
                'active': True,
                'model_id': model_id,
                'res_id': self.id,
                'log_lines': [(0, 0, {'message': 'Removal order Process '})]
            })
        ctx.update({'job_id': job})

        instance = self.instance_id
        self.check_validate_fields()
        address = self.ship_address_id
        address_field_one = address.street or address.street2
        address_field_two = address.street and address.street2 or ''
        file_order_ship = NamedTemporaryFile(delete=False, mode='w')
        file_order_ship.write("MerchantRemovalOrderID\t%s\n" % (self.name))
        file_order_ship.write("RemovalDisposition\t%s\n" % (self.removal_disposition))
        file_order_ship.write("AddressName\t%s\n" % (address.name))
        file_order_ship.write("AddressFieldOne\t%s\n" % (address_field_one))
        file_order_ship.write("AddressFieldTwo\t%s\n" % (address_field_two))
        file_order_ship.write("AddressCity\t%s\n" % (address.city))
        file_order_ship.write("AddressCountryCode\t%s\n" % (address.country_id.code))
        file_order_ship.write("AddressStateOrRegion\t%s\n" % (address.state_id.code))
        file_order_ship.write("AddressPostalCode\t%s\n" % (address.zip))
        file_order_ship.write("ContactPhoneNumber\t%s\n" % (address.phone or address.mobile))
        file_order_ship.write("ShippingNotes\t%s\n" % (self.shipping_notes or ''))
        file_order_ship.write("\n")
        file_order_ship.write("MerchantSKU\tSellableQuantity\tUnsellableQuantity\n")
        for removal_line in self.removal_order_lines_ids:
            sellable_quantity = 0.0 if removal_line.sellable_quantity < 0.0 else removal_line.sellable_quantity
            unsellable_quantity = 0.0 if removal_line.unsellable_quantity < 0.0 else removal_line.unsellable_quantity
            file_order_ship.write(
                "%s\t%s\t%s\n" % (removal_line.seller_sku, int(sellable_quantity), int(unsellable_quantity)))
        file_order_ship.close()
        fl = open(file_order_ship.name, 'rb')
        data = fl.read()
        file_name = "removal_request_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'

        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')

        kwargs = {'merchant_id': instance.merchant_id and str(instance.merchant_id) or False,
                  'auth_token': instance.auth_token and str(instance.auth_token) or False,
                  'app_name': 'amazon_ept',
                  'account_token': account.account_token,
                  'emipro_api': 'send_removal_order_request_to_amazon_v13',
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': instance.country_id.amazon_marketplace_code or
                                             instance.country_id.code,
                  'marketplaceids': [instance.market_place_id],
                  'instance_id': instance.id,
                  'data': data}
        if self.removal_disposition == 'Return':
            self.removal_order_procurements()
        elif self.removal_disposition == 'Disposal':
            self.with_context(ctx).disposal_order_pickings()

        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise Warning(response.get('reason'))

        self.write({'state': 'plan_approved'})
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'datas': base64.encodebytes(data),
            'res_model': 'mail.compose.message',
            'type': 'binary'
        })
        self.message_post(body=_("<b>Removal Request Created</b>"), attachment_ids=attachment.ids)
        return True

    def disposal_order_pickings(self):
        """
        This Method relocates create disposal order pickings.If sellable quantity get grater that 0 In this cases create stock pickings.
        :return:This Method return Boolean(True/False).
        """
        picking_obj = self.env['stock.picking']
        stock_move_obj = self.env['stock.move']
        config = self.env['removal.order.config.ept'].search(
            [('id', 'in', self.instance_id.removal_order_config_ids.ids),
             ('removal_disposition', '=', self.removal_disposition)])
        if not config:
            message = "Removal Order configuration missing for disposition %s" % (self.removal_disposition)
            if not self._context.get('is_auto_process'):
                raise Warning(message)
            else:
                job = self._context.get('job_id')
                job.write({'log_lines': [(0, 0, {'message': message, 'mismatch_details' : True})]})

        picking_type_id = config.picking_type_id.id
        dest_location_id = config.location_id.id
        unsellable_source_location_id = self.disposition_location_id.id
        sellable_source_location_id = self.instance_id.fba_warehouse_id.lot_stock_id.id
        sellable_picking = False
        unsellable_picking = False
        for removal_line in self.removal_order_lines_ids:
            amazon_product = removal_line.amazon_product_id
            sellable_quantity = 0.0 if removal_line.sellable_quantity < 0.0 else removal_line.sellable_quantity
            unsellable_quantity = 0.0 if removal_line.unsellable_quantity < 0.0 else removal_line.unsellable_quantity
            if sellable_quantity > 0.0:
                if not sellable_picking:
                    vals = self.create_picking_vals(picking_type_id, sellable_source_location_id, dest_location_id)
                    sellable_picking = picking_obj.create(vals)
                vals = self.create_move_vals(sellable_source_location_id, dest_location_id, amazon_product.product_id,
                                             sellable_quantity, sellable_picking.id)
                stock_move_obj.create(vals)
            if unsellable_quantity > 0.0:
                if not unsellable_picking:
                    vals1 = self.create_picking_vals(picking_type_id, unsellable_source_location_id, dest_location_id)
                    unsellable_picking = picking_obj.create(vals1)
                vals = self.create_move_vals(unsellable_source_location_id, dest_location_id, amazon_product.product_id,
                                             unsellable_quantity, unsellable_picking.id)
                stock_move_obj.create(vals)
        sellable_picking and sellable_picking.action_confirm()
        sellable_picking and sellable_picking.action_assign()

        unsellable_picking and unsellable_picking.action_confirm()
        unsellable_picking and unsellable_picking.action_assign()
        return sellable_picking, unsellable_picking

    def create_move_vals(self, location_id, location_dest_id, product_id, qty, picking_id):
        """
        This Method relocates create stock move line values.
        :param location_id: This Arguments relocates sellable source location id.
        :param location_dest_id: This Arguments relocates location destination id.
        :param product_id: This Arguments relocates product_id of amazon.
        :param qty: This Arguments relocates sellable quantity.
        :param picking_id: This Arguments relocates sellable picking.
        :return: This Method prepare value of stock move and return.
        """
        vals = {
            'location_id': location_id,
            'location_dest_id': location_dest_id,
            'product_uom_qty': qty,
            'name': product_id.name,
            'product_id': product_id.id,
            'state': 'draft',
            'picking_id': picking_id,
            'product_uom': product_id.uom_id.id,
            'company_id': self.instance_id.company_id.id
        }
        return vals

    def create_picking_vals(self, picking_type_id, source_location_id, dest_location_id):
        """
        This Method relocates prepare create picking values.
        :param picking_type_id: This Arguments relocates picking type id.
        :param source_location_id: This Arguments relocates source location id.
        :param dest_location_id: This Arguments relocates destination location id.
        :return: This Method prepare create picking value dictionary and return.
        """
        return {
            'picking_type_id': picking_type_id,
            'partner_id': self.ship_address_id.id,
            'removal_order_id': self.id,
            'origin': self.name,
            'company_id': self.instance_id.company_id.id,
            'location_id': source_location_id,
            'location_dest_id': dest_location_id,
            'seller_id': self.instance_id and self.instance_id.seller_id and self.instance_id.seller_id.id or False
        }

    def removal_order_procurements(self):
        """
        This Method create removal order procurements.
        After creating procurement group sellable and unsellable run procurement group.
        :return: This Method return stock pickings.
        """
        proc_group_obj = self.env['procurement.group']
        picking_obj = self.env['stock.picking']
        pull_obj = self.env['stock.rule']
        sell_proc_group = self.create_procurement_group()
        unsell_proc_group = self.create_procurement_group()
        config = self.env['removal.order.config.ept'].search(
            [('id', 'in', self.instance_id.removal_order_config_ids.ids),
             ('removal_disposition', '=', self.removal_disposition)])

        unsellable_rule = pull_obj.search([('route_id', '=', config.unsellable_route_id.id),
                                           ('location_src_id', '!=', self.disposition_location_id.id)], limit=1)

        sellable_rule = pull_obj.search([('route_id', '=', config.sellable_route_id.id),
                                         ('location_src_id.usage', '=', 'transit')], limit=1)

        for removal_line in self.removal_order_lines_ids:
            amazon_product = removal_line.amazon_product_id
            amazon_product_id = amazon_product.product_id
            amazon_product_uom = amazon_product.product_id.uom_id
            amazon_product_name = amazon_product.name or amazon_product.title
            removal_order_name = self.name
            removal_order_instance = self.instance_id.company_id
            sellable_quantity = 0.0 if removal_line.sellable_quantity < 0.0 else removal_line.sellable_quantity
            unsellable_quantity = 0.0 if removal_line.unsellable_quantity < 0.0 else removal_line.unsellable_quantity
            datas = {'company_id': self.instance_id.company_id.id,
                     'warehouse_id': self.warehouse_id,
                     'priority': '1'
                     }

            if unsellable_quantity > 0.0:
                datas.update({
                    'group_id': unsell_proc_group,
                    'route_ids': config.unsellable_route_id,  # [(6,0,config.unsellable_route_id.ids)]
                })
                qty = removal_line.unsellable_quantity
                stock_rule_location_id = unsellable_rule.location_id
                self.run_procurement_group(proc_group_obj, amazon_product_id, qty, amazon_product_uom,
                                           stock_rule_location_id,
                                           amazon_product_name, removal_order_name, removal_order_instance, datas)
            if sellable_quantity > 0.0:
                datas.update({
                    'group_id': sell_proc_group,
                    'route_ids': config.sellable_route_id,
                })
                qty = removal_line.sellable_quantity
                removal_order_warehouse_id_lot_stock_id = sellable_rule.location_id
                self.run_procurement_group(proc_group_obj, amazon_product_id, qty, amazon_product_uom,
                                           removal_order_warehouse_id_lot_stock_id,
                                           amazon_product_name, removal_order_name, removal_order_instance, datas)

        pickings_state_confirm = picking_obj.search([('group_id', 'in', [sell_proc_group.id, unsell_proc_group.id]),
                                                     ('state', 'in', ['confirmed', 'partially_available', 'assigned'])])
        if pickings_state_confirm:
            pickings_state_confirm.write({'is_fba_wh_picking': True, 'removal_order_id': self.id})
        pickings_state_waiting = picking_obj.search(
            [('group_id', 'in', [sell_proc_group.id, unsell_proc_group.id]), ('state', 'in', ['waiting'])])
        if pickings_state_waiting:
            pickings_state_waiting.write({'is_fba_wh_picking': False, 'removal_order_id': self.id})
        pickings = picking_obj.search([('group_id', 'in', [sell_proc_group.id, unsell_proc_group.id])])
        return pickings

    def create_procurement_group(self):
        """
        This Method create procurement group with removal order id.
        :return: This Method return create procurement group object.
        """
        proc_group_obj = self.env['procurement.group']
        return proc_group_obj.create({'removal_order_id': self.id, 'partner_id': self.ship_address_id.id})

    def run_procurement_group(self, proc_group_obj, amazon_product_id, qty, amazon_product_uom, stock_rule_location_id,
                              amazon_product_name, removal_order_name, removal_order_instance, datas):
        """
        This Method relocates run procurement group for sellable quantity and unsellable quantity.
        :param proc_group_obj: This Arguments relocates procurement group object.
        :param amazon_product_id: This Arguments relocates amazon product id.
        :param qty: This Arguments relocates sellable quantity and unsellable quantity.
        :param amazon_product_uom: This Arguments relocates amazon product unit of measure.
        :param stock_rule_location_id: This Arguments relocates stock rule location id.
        :param amazon_product_name: This Arguments relocates amazon product name.
        :param removal_order_name: This Arguments relocates removal order name.
        :param removal_order_instance: This Arguments relocates removal order instance.
        :param datas: This Arguments relocates datas dictionary(Group_ids,route_ids).
        :return:
        """
        proc_group_obj.run([self.env['procurement.group'].Procurement(amazon_product_id,
                                                                      qty,
                                                                      amazon_product_uom,
                                                                      stock_rule_location_id,
                                                                      amazon_product_name,
                                                                      removal_order_name,
                                                                      removal_order_instance,
                                                                      datas)])
        return proc_group_obj

    @api.model
    def create(self, vals):
        """
        This Method create sequence gpr removal order plan.
        :param vals: This Arguments relocates values.
        :return: This Method call super method and create sequence.
        """
        if 'name' not in vals:
            try:
                sequence = self.env.ref('amazon_ept.seq_removal_order_plan')
                if sequence:
                    name = sequence.next_by_id()
                else:
                    name = '/'
            except:
                name = '/'
            vals.update({'name': name})
        return super(removal_order, self).create(vals)
