from odoo import models, fields, api
from odoo.exceptions import except_orm
from datetime import datetime
import csv
from io import StringIO
import base64

class import_product_inbound_shipment(models.TransientModel):
    _name = 'import.product.inbound.shipment'
    _description = 'Import product through csv file for inbound shipment'

    choose_file = fields.Binary('Choose File', filters='*.csv')
    shipment_id = fields.Many2one('inbound.shipment.plan.ept', 'Shipment Reference')
    update_existing = fields.Boolean('Do you want to update already exist record ?')
    replace_product_qty = fields.Boolean('Do you want to replace product quantity?', help="""
            If you select this option then it will replace product quantity by csv quantity field data, 
            it will not perform addition like 2 quantity is there in line and csv contain 3,
            then it will replace 2 by 3, it won't be updated by 5.

            If you have not selected this option then it will increase (addition) line quantity with 
            csv quantity field data like 2 quantity in line, and csv have 3 quantity then 
            it will update line with 5 quantity. 
        """)
    delimiter = fields.Selection([('tab', 'Tab'), ('semicolon', 'Semicolon'), ('colon', 'Colon')],
                                 "Seperator", default="colon")

    def default_get(self, fields):
        res = super(import_product_inbound_shipment, self).default_get(fields)
        res['shipment_id'] = self._context.get('shipment_id', False)
        return res

    def wizard_view(self):
        view = self.env.ref('amazon_ept.view_inbound_product_import_wizard')

        return {
            'name': 'Import Product',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'import.product.inbound.shipment',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.ids[0],
            'context': self.env.context,
        }

    def download_sample_product_csv(self):
        """
        Download Sample file for Inbound Shipment Plan Products Import
        :return: Dict
        """
        attachment = self.env['ir.attachment'].search([('name', '=', 'inbound_shipment_plan_sample.csv')])
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % (attachment.id),
            'target': 'new',
            'nodestroy': False,
        }

    def read_file(self, name=datetime.strftime(datetime.now(), '%Y%m%d%H%M%S%f')):
        '''
            Read selected file to import order and return Reader to the caller
        '''
        imp_file = StringIO(base64.decodestring(self.choose_file).decode('utf-8'))
        new_file_name = self.get_file_name(name=name)
        #         open(new_file_name,'wb')
        file_write = open(new_file_name, 'w')
        file_write.writelines(imp_file.getvalue())
        file_write.close()

        if self.delimiter == 'semicolon':
            reader = csv.DictReader(open(new_file_name, "rU"), delimiter=";")
        elif self.delimiter == 'colon':
            reader = csv.DictReader(open(new_file_name, "rU"), delimiter=",")
        else:
            reader = csv.DictReader(open(new_file_name, "rU"), delimiter="\t")
        return reader

    def get_file_name(self, name=datetime.strftime(datetime.now(), '%Y%m%d%H%M%S%f')):
        return '/tmp/inbount_shipment_%s_%s.csv' % (self.env.uid, name)

    def validate_fields(self, fieldname):
        '''
            This import pattern requires few fields default, so check it first whether it's there or not.
        '''
        require_fields = ['seller_sku', 'quantity', 'quantity_in_case']
        missing = []
        for field in require_fields:
            if field not in fieldname:
                missing.append(field)

        if len(missing) > 0:
            raise except_orm(('Incorrect format found..!'), (
                    'Please provide all the required fields in file, missing fields => %s.' % (
            missing)))

        return True

    def validate_process(self):
        '''
            Validate process by checking all the conditions and return back with inbound shipment object
        '''
        shipment_obj = self.env['inbound.shipment.plan.ept']

        # Commented By: Dhaval Sanghani [28-May-2020]
        # Purpose: Code is Unusable
        # shipments = []
        # for shipment in shipment_obj.browse(self.env.context.get('active_ids')):
        #     if shipment.state != "draft":
        #         raise except_orm(('Unable to process..!'),
        #                          ('You can process with only draft shipment plan!.'))
        #     shipments.append(shipment)
        #
        # if len(shipment) > 1:
        #     raise except_orm(('Unable to process..!'),
        #                      ('You can process only one shipment plan at a time!.'))
        #
        # shipment_plan = shipments[0]
        # if not shipment_plan:
        #     raise except_orm(('Unable to process..!'), ('Shipment Plan is not found!!!.'))
        if not self.choose_file:
            raise except_orm(('Unable to process..!'), ('Please select file to process...'))

        # Added By: Dhaval Sanghani [28-May-2020]
        shipment_plan = shipment_obj.browse(self._context.get('shipment_id', []))
        # END
        return shipment_plan




    def import_shipment_line(self):
        # line_obj = self.env['inbound.shipment.plan.line']
        amazon_product_obj = self.env['amazon.product.ept']

        shipment_plan = self.validate_process()[0]
        current_date = datetime.strftime(datetime.now(), '%Y%m%d%H%M%S%f')

        reader = self.read_file(name=current_date)
        fieldname = reader.fieldnames

        if self.validate_fields(fieldname):
            for row in reader:
                seller_sku = row.get('seller_sku')
                quantity = row.get('quantity', 0) and float(row.get('quantity', 0)) or 0.0
                quantity_in_case = row.get('quantity_in_case', 0) and float(row.get('quantity_in_case', 0)) or 0.0
                amazon_product = amazon_product_obj.search(
                        [('instance_id', '=', shipment_plan.instance_id.id),
                         ('fulfillment_by', '=', 'FBA'),
                         ('seller_sku', '=', seller_sku)], limit=1)
                if not amazon_product:
                    raise Warning(
                        'Amazon product not found , please check product exist or not for sku %s,instance %s and Fulfillment by amazon' % (
                        seller_sku, shipment_plan.instance_id.name))

                # Commented By: Dhaval Sanghani [28-May-2020]
                # Purpose: Use Filtered() instead of Search Method
                # shipment_plan_line_obj = line_obj.search(
                #         [('amazon_product_id', '=', amazon_product.id),
                #          ('shipment_plan_id', '=', shipment_plan.id)])
                shipment_plan_line_obj = shipment_plan.shipment_line_ids.\
                                                   filtered(lambda line: line.amazon_product_id.id == amazon_product.id)
                try:
                    if not shipment_plan_line_obj:
                        dict_data = {
                            'shipment_plan_id':shipment_plan.id,
                            'amazon_product_id':amazon_product.id,
                            'quantity':quantity,
                            'quantity_in_case': quantity_in_case
                        }
                        shipment_plan_line_obj.create(dict_data)

                    else:
                        # Commented By: Dhaval Sanghani [30-May-2020]
                        # Purpose: Need to add QTY
                        # if not self.update_existing:
                        #     continue

                        # Modified By: Dhaval Sanghani [30-May-2020]
                        if self.update_existing:

                            if self.replace_product_qty:
                                total_qty = quantity

                            else:
                                total_qty = quantity + shipment_plan_line_obj.quantity

                            shipment_plan_line_obj.write({'quantity': total_qty, 'quantity_in_case': quantity_in_case})

                except Exception as e:
                    raise except_orm('Unable to process ..!',
                                     ('Error found while importing products => %s.' % (str(e))))

            return {'type':'ir.actions.act_window_close'}