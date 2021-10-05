from odoo import models, fields, api, _
from odoo.exceptions import Warning
from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT


class inbound_shipment_plan_ept(models.Model):
    _name = "inbound.shipment.plan.ept"
    _description = "Inbound Shipment Plan"
    _inherit = ['mail.thread']
    _order = 'id desc'

    label_preference_help = """     
            SELLER_LABEL - Seller labels the items in the inbound shipment when labels are required.
            AMAZON_LABEL_ONLY - Amazon attempts to label the items in the inbound shipment when labels 
                                are required. If Amazon determines that it does not have the information 
                                required to successfully label an item, that item is not included in the 
                                inbound shipment plan
            AMAZON_LABEL_PREFERRED - Amazon attempts to label the items in the inbound shipment when 
                                     labels are required. If Amazon determines that it does not have 
                                     the information required to successfully label an item, that item 
                                     is included in the inbound shipment plan and the seller must 
                                     label it.    """

    state = fields.Selection([('draft', 'Draft'),
                              ('plan_approved', 'Shipment Plan Approved'),
                              ('cancel', 'Cancelled')
                              ], default='draft',
                             string='State')
    name = fields.Char(size=120, string='Name', readonly=True, required=False, index=True)
    instance_id = fields.Many2one('amazon.instance.ept', string='Instance', required=True,
                                  readonly=True, states={'draft':[('readonly', False)]})
    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse", readonly=True,
                                   states={'draft':[('readonly', False)]})
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True,
                                 states={'draft':[('readonly', False)]})
    ship_from_address_id = fields.Many2one('res.partner', string='Ship From Address', readonly=True,
                                           states={'draft':[('readonly', False)]})

    ship_to_country = fields.Many2one('res.country', string='Ship To Country', readonly=True,
                                      states={'draft':[('readonly', False)]}, help="""
                                            The country code for the country where you want your inbound shipment to be sent. 
                                            Only for sellers in North America and Multi-Country Inventory (MCI) sellers in Europe.
                                            """)
    label_preference = fields.Selection(
            [('SELLER_LABEL', 'SELLER_LABEL'), ('AMAZON_LABEL_ONLY', 'AMAZON_LABEL_ONLY'),
             ('AMAZON_LABEL_PREFERRED', 'AMAZON_LABEL_PREFERRED'), ], default='SELLER_LABEL',
            string='LabelPrepPreference', readonly=True, states={'draft':[('readonly', False)]},
            help=label_preference_help)

    intended_boxcontents_source = fields.Selection(
            [('FEED', 'FEED')], default='FEED',
            help="If your instance is USA then you must set box contect, other wise amazon will "
                 "collect per piece fee",
            string="Intended BoxContents Source", readonly=1)
    is_partnered = fields.Boolean('Is Partnered', default=False, copy=False)
    is_are_cases_required = fields.Boolean(string="Are Cases Required ?", default=False,
                                           help="Indicates whether or not an inbound shipment "
                                                "contains case-packed boxes. Note: A shipment must "
                                                "either contain all case-packed boxes or all "
                                                "individually packed boxes.")
    shipping_type = fields.Selection([('sp', 'SP (Small Parcel)'),
                                      ('ltl', 'LTL (Less Than Truckload/FullTruckload (LTL/FTL))')
                                      ], string="Shipping Type", default="sp")
    shipment_line_ids = fields.One2many('inbound.shipment.plan.line', 'shipment_plan_id',
                                        string='Shipment Plan Items', readonly=True,
                                        states={'draft':[('readonly', False)]},
                                        help="SKU and quantity information for the items in an "
                                             "inbound shipment.")
    ship_to_address_ids = fields.Many2many('res.partner', 'rel_inbound_shipment_plan_res_partner',
                                           'shipment_id', 'partner_id', string='Ship To Addresses',
                                           readonly=True)
    picking_ids = fields.One2many('stock.picking', 'ship_plan_id', string="Picking", readonly=True)
    log_ids = fields.One2many('common.log.lines.ept', compute='get_error_logs')
    odoo_shipment_ids = fields.One2many('amazon.inbound.shipment.ept', 'shipment_plan_id',
                                        string='Amazon Shipments')
    @api.model
    def create(self, vals):
        try:
            sequence = self.env.ref('amazon_ept.seq_inbound_shipment_plan')
            if sequence:
                name = sequence.next_by_id()
            else:
                name = '/'
        except:
            name = '/'
        vals.update({'name':name})
        return super(inbound_shipment_plan_ept, self).create(vals)
    
    def unlink(self):
        """
        Use: Check if Shipment Plan is not in Draft state then it will not Delete.
        Added By: Dhaval Sanghani [@Emipro Technologies]
        Added On: 29-May-2020
        @param: {}
        @return: {}
        """
        for plan in self:
            if plan.state == 'plan_approved':
                raise Warning('You cannot delete Inbound Shipment plan which is not draft.')
        return super(inbound_shipment_plan_ept, self).unlink()

    @api.onchange('instance_id')
    def onchange_instance_id(self):
        if self.instance_id:
            self.company_id = self.instance_id.company_id and self.instance_id.company_id.id
            self.ship_to_country = self.instance_id.country_id and self.instance_id.country_id.id

    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        if self.warehouse_id:
            self.ship_from_address_id = self.warehouse_id.partner_id and \
                                        self.warehouse_id.partner_id.id

    def reset_all_lines(self):
        self.ensure_one()
        plan_line_obj = self.env['inbound.shipment.plan.line']
        self._cr.execute("""select amazon_product_id from inbound_shipment_plan_line 
                            where shipment_plan_id=%s group by amazon_product_id having count(amazon_product_id)>1;""" % (
        self.id))
        result = self._cr.fetchall()
        for record in result:

            duplicate_lines = self.mapped('shipment_line_ids').filtered(lambda r: r.amazon_product_id.id == record[0])
            qty = 0.0
            quantity_in_case=0
            for line in duplicate_lines:
                qty += line.quantity
                quantity_in_case=line.quantity_in_case
            duplicate_lines.unlink()
            plan_line_obj.create(
                {'amazon_product_id': record[0], 'quantity': qty, 'shipment_plan_id': self.id,'quantity_in_case':quantity_in_case})
        return True


    def set_to_draft_ept(self):
        self.write({'state': 'draft'})
        self.odoo_shipment_ids.unlink()
        self.reset_all_lines()
        self.message_post(body=_("<b>Reset to Draft Plan</b>"))
        return True

    def get_error_logs(self):
        common_log_line_ept_obj = self.env['common.log.lines.ept']
        model_id = common_log_line_ept_obj.get_model_id('inbound.shipment.plan.ept')
        logs = common_log_line_ept_obj.search(
            [('model_id', '=', model_id), ('res_id', '=', self.id)])
        self.log_ids = logs and logs.ids

    def import_product_for_inbound_shipment(self):
        """
            Open wizard to import product through csv file.
            File contains only product sku and quantity.
        """
        import_obj = self.env['import.product.inbound.shipment'].create({'shipment_id': self.id})

        ctx = self.env.context.copy()
        ctx.update({'shipment_id': self.id, 'update_existing': False, })
        return import_obj.with_context(ctx).wizard_view()

    @api.model
    def create_procurements(self, odoo_shipments, job=False):
        proc_group_obj = self.env['procurement.group']
        picking_obj = self.env['stock.picking']
        location_route_obj = self.env['stock.location.route']
        log_book_obj = self.env['common.log.book.ept']
        log_line_obj = self.env['common.log.lines.ept']
        group_wh_dict = {}

        for shipment in odoo_shipments:
            proc_group = proc_group_obj.create(
                    {'odoo_shipment_id':shipment.id, 'name':shipment.name})
            fulfill_center = shipment.fulfill_center_id
            ship_plan = shipment.shipment_plan_id
            fulfillment_center = self.env['amazon.fulfillment.center'].search(
                    [('center_code', '=', fulfill_center),
                     ('seller_id', '=', ship_plan.instance_id.seller_id.id)])
            fulfillment_center = fulfillment_center and fulfillment_center[0]
            warehouse = fulfillment_center and fulfillment_center.warehouse_id or ship_plan.instance_id.fba_warehouse_id or ship_plan.instance_id.warehouse_id or False

            if not warehouse:
                if not job:
                    job = log_book_obj.create({'module':'amazon_ept',
                                                 'type':'export',
                                                 })

                error_value = 'No any warehouse found related to fulfillment center %s. Please set ' \
                              'fulfillment center %s in warehouse || shipment %s.' % (
                                  fulfill_center, fulfill_center, shipment.name)
                log_line_obj.create({'message':error_value,
                                    'model_id':log_line_obj.get_model_id(
                                    'amazon.inbound.shipment.ept'),
                                    'res_id':shipment.id,
                                    'log_line_id':job.id})

                continue
            location_routes = location_route_obj.search([('supplied_wh_id', '=', warehouse.id), (
                'supplier_wh_id', '=', ship_plan.warehouse_id.id)])
            if not location_routes:
                if not job:
                    job = log_book_obj.create({'module':'amazon_ept',
                                                 'type':'export',
                                                 })
                error_value = 'Location routes are not found. Please configure routes in warehouse ' \
                              'properly || warehouse %s & shipment %s.' % (
                                  warehouse.name, shipment.name)
                log_line_obj.create({'message':error_value,
                                     'model_id':log_line_obj.get_model_id(
                                             'amazon.inbound.shipment.ept'),
                                     'res_id':shipment.id,
                                     'log_line_id':job.id})
                continue
            location_routes = location_routes[0]
            group_wh_dict.update({proc_group:warehouse})

            for line in shipment.odoo_shipment_line_ids:
                qty = line.quantity
                amazon_product = line.amazon_product_id
                datas = {'route_ids':location_routes,
                         'group_id':proc_group,
                         'company_id':ship_plan.instance_id.company_id.id,
                         'warehouse_id':warehouse,
                         'priority':'1'
                         }
                proc_group_obj.run([self.env['procurement.group'].Procurement(
                        amazon_product.product_id,qty,amazon_product.product_id.uom_id,
                        warehouse.lot_stock_id,amazon_product.product_id.name, shipment.name,
                        ship_plan.instance_id.company_id, datas)])

        if group_wh_dict:
            for group, warehouse in group_wh_dict.items():
                picking = picking_obj.search([('group_id', '=', group.id),
                                              ('picking_type_id.warehouse_id', '=', warehouse.id)])
                if picking:
                    picking.write({'is_fba_wh_picking':True})

        # Added By: Dhaval Sanghani [22-Jun-2020]
        # Purpose: Pickings Assign (WH Stock -> Transit)
        for shipment in odoo_shipments:
            pickings = shipment.mapped('picking_ids').filtered(lambda pick: not pick.is_fba_wh_picking and
                                                                              pick.state not in ['done',
                                                                                                 'cancel'])

            for picking in pickings:
                picking.action_assign()
        return True

    def cancel_entire_inbound_shipment(self, shipment, sku_qty_dict, job):
        log_line_obj = self.env['common.log.lines.ept']
        ship_plan = shipment.shipment_plan_id
        instance = ship_plan.instance_id
        shipment_status = 'CANCELLED'
        # Comment and New Line Added By: Dhaval Sanghani [26-May-2020]
        #label_prep_type = 'SELLER_LABEL' if shipment.label_prep_type == 'NO_LABEL' else shipment.label_prep_type
        label_prep_type = shipment.label_prep_type
        if label_prep_type == 'NO_LABEL':
            label_prep_type = 'SELLER_LABEL'
        elif label_prep_type == 'AMAZON_LABEL':
            label_prep_type = ship_plan.label_preference

        destination = shipment.fulfill_center_id
        cases_required = shipment.shipment_plan_id.is_are_cases_required

        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo(
        ).get_param('database.uuid')

        kwargs = {'merchant_id':instance.merchant_id and str(instance.merchant_id) or False,
                  'auth_token':instance.auth_token and str(instance.auth_token) or False,
                  'app_name':'amazon_ept',
                  'account_token':account.account_token,
                  'emipro_api':'update_shipment_in_amazon_v13',
                  'dbuuid':dbuuid,
                  'amazon_marketplace_code':instance.country_id.amazon_marketplace_code or
                                            instance.country_id.code,
                  'shipment_name':shipment.name,
                  'shipment_id':shipment.shipment_id,
                  'destination':destination,
                  'cases_required':cases_required,
                  'labelpreppreference':label_prep_type,
                  'shipment_status':shipment_status,
                  'inbound_box_content_status':shipment.intended_boxcontents_source,
                  }

        response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            error_value = response.get('reason')
            log_line_obj.create({
                                 'message':error_value,
                                 'model_id':log_line_obj.get_model_id(
                                         'inbound.shipment.plan.ept'),
                                 'res_id':self.id,
                                 'log_line_id':job.id
                                 })
        else:
            shipment.write({'state':'CANCELLED'})

        return True

    def cancel_inbound_shipemnts(self, odoo_shipments, job):
        # Added By: Dhaval Sanghani [30-May-2020]
        shipments = odoo_shipments.filtered(lambda odoo_shipment: odoo_shipment.state != 'CANCELLED')

        # Commented By: Dhaval Sanghani [06-03-2020]
        for shipment in shipments:
             # if shipment.state == 'CANCELLED':
             #     continue
            self.cancel_entire_inbound_shipment(shipment, {}, job)
        return True

    def display_shipment_details(self, shipments):
        view = self.env.ref('amazon_ept.view_inbound_shipment_details_wizard')
        context = dict(self._context)
        context.update({'shipments': shipments,'plan_id':self.id})
        return {
            'name': _('Shipment Details'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'inbound.shipment.details',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context
        }

    def create_inbound_shipment_plan(self):
        #inbound_shipment_line_obj = self.env['inbound.shipment.plan.line']
        log_book_obj = self.env['common.log.book.ept']
        log_line_obj = self.env['common.log.lines.ept']

        address = self.ship_from_address_id
        instance = self.instance_id
        ship_to_country_code = self.ship_to_country and self.ship_to_country.code or False
        is_are_cases_required = self.is_are_cases_required or False

        already_taken = []
        total_shipments = []
        job = False

        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo(
        ).get_param('database.uuid')

        lines = self.shipment_line_ids.filtered(lambda r:r.quantity<=0.0)
        if lines:
            skus = ', '.join(map(str, lines.mapped('seller_sku')))
            raise Warning("Qty must be greater then zero Seller Sku : %s" % skus)

        if is_are_cases_required:
            zero_qty_in_case_list = self.shipment_line_ids.filtered(lambda r:r.quantity_in_case <= 0)
            if zero_qty_in_case_list:
                raise Warning(
                        "If you ticked 'Are Cases Required' then 'Quantity In Case' must be "
                        "greater then zero for this Seller SKU: %s" % (
                            zero_qty_in_case_list.mapped('seller_sku')))

        x = 0
        while True:

            shipment_lines = self.mapped('shipment_line_ids').filtered(lambda r:r.odoo_shipment_id is not set
                                                                              and r.id not in already_taken)

            if not shipment_lines:
                break

            if len(shipment_lines.ids) > 20:
                shipment_line_ids = shipment_lines[x:x + 20]
            else:
                shipment_line_ids = shipment_lines

            already_taken += shipment_line_ids.ids



            sku_qty_dict=[]
            for shipment_line in self.shipment_line_ids:
                if is_are_cases_required:
                    sku_qty_dict.append({'sku':shipment_line.seller_sku,
                                     'quantity':int(shipment_line.quantity),
                                     'quantity_in_case':int(shipment_line.quantity_in_case)})
                else:
                    sku_qty_dict.append({'sku':shipment_line.seller_sku,
                                         'quantity':int(shipment_line.quantity)})

            address_dict={'name':address.name,'address_1':address.street or '',
                          'address_2':address.street2 or '','city':address.city or '',
                          'country':address.country_id and address.country_id.code or '',
                          'state_or_province':address.state_id and address.state_id.code or '','postal_code':address.zip or ''}

            kwargs = {'merchant_id':instance.merchant_id and str(instance.merchant_id) or False,
                      'auth_token':instance.auth_token and str(instance.auth_token) or False,
                      'app_name':'amazon_ept',
                      'account_token':account.account_token,
                      'emipro_api':'create_inbound_shipment_plan_v13',
                      'dbuuid':dbuuid,
                      'amazon_marketplace_code':instance.country_id.amazon_marketplace_code or
                                                instance.country_id.code,
                      'ship_to_country_code':ship_to_country_code,
                      'labelpreppreference':self.label_preference,
                      'sku_qty_dict':sku_qty_dict,
                      'ship_from_address':address_dict
                      }

            response = iap.jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
            if response.get('reason'):
                error_value = response.get('reason')
                """ Here we have canceled all amazon inbound shipment"""
                if not job:
                    job = log_book_obj.create({'module':'amazon_ept',
                                               'type':'export',
                                               })

                log_line_obj.create({
                                     'message':error_value,
                                     'model_id':log_line_obj.get_model_id(
                                             'inbound.shipment.plan.ept'),
                                     'res_id':self.id,
                                     'log_line_id':job.id
                                     })
                # Commented By: Dhaval Sanghani [30-May-2020]
                # Purpose: At this time Shipment Plan has not any Shipments. Because First display Shipment Response and
                # when user confirms it then Shipments are created in Odoo.
                #self.cancel_inbound_shipemnts(self.odoo_shipment_ids, job)
                self.write({'state':'cancel'})
                return True

            shipments = []
            result = response.get('result')
            if not isinstance(result.get('InboundShipmentPlans', {}).get('member', []),
                              list):
                shipments.append(result.get('InboundShipmentPlans', {}).get('member', {}))
            else:
                shipments = result.get('InboundShipmentPlans', {}).get('member', [])

            total_shipments += shipments
        return self.display_shipment_details(total_shipments)