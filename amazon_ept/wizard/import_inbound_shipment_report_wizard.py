from odoo import models, fields, api
from odoo.exceptions import except_orm
import csv
import base64
import os

try:
    from io import StringIO
except ImportError:
    from StringIO import StringIO
from datetime import datetime

class AmazonInboundShipmentReportWizard(models.TransientModel):
    _name = "amazon.inbound.shipment.report.wizard"
    _description = 'Import In-bound Shipment Report Through CSV File'

    choose_file = fields.Binary(string="Choose File", filters="*.csv",
                                help="Select amazon In-bound shipment file.")
    file_name = fields.Char("Filename", help="File Name")
    delimiter = fields.Selection([('tab', 'Tab'), ('semicolon', 'Semicolon'), ('colon', 'Colon')],
                                 "Separator", default='colon',
                                 help="Select separator type for the separate file data and "
                                      "import into ERP.")

    def get_file_name(self, name=datetime.strftime(datetime.now(), '%Y%m%d%H%M%S%f')):
        return '/tmp/inbount_shipment_report_%s_%s.csv' % (self.env.uid, name)

    def read_file(self, name=datetime.strftime(datetime.now(), '%Y%m%d%H%M%S%f')):
        '''
            Read selected file to import inbound shipment report and return Reader to the caller
        '''
        imp_file = StringIO(base64.decodestring(self.choose_file).decode('utf-8'))
        new_file_name = self.get_file_name(name=name)
        file_write = open(new_file_name, 'w')
        file_write.writelines(imp_file.getvalue())
        file_write.close()
        file_read = open(new_file_name, "rU")
        dialect = csv.Sniffer().sniff(file_read.readline())
        file_read.seek(0)

        if self.delimiter == 'semicolon':
            reader = csv.DictReader(file_read, dialect=dialect, delimiter=';', quoting=csv.QUOTE_NONE)
        elif self.delimiter == 'colon':
            reader = csv.DictReader(file_read, dialect=dialect, delimiter=',', quoting=csv.QUOTE_NONE)
        else:
            reader = csv.DictReader(file_read, dialect=dialect, delimiter='\t', quoting=csv.QUOTE_NONE)

        os.remove(new_file_name)
        return reader

    def download_inbound_shipment_sample_csv(self):
        """
        Download Sample Box Content file for Inbound Shipment Plan Products Import

        :return: Dict
        """
        attachment = self.env['ir.attachment'].search([('name', '=', 'amazon_inbound_shipment_box_content.csv')])
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % (attachment.id),
            'target': 'new',
            'nodestroy': False,
        }

    def check_fields_validation(self, fields_name):
        """
            This import pattern requires few fields default, so check it first whether it's there or not.
        """
        # Modified line By: Dhaval Sanghani [29-May-2020]
        # Purpose: Add Weight as require field
        require_fields = ['Box No', 'Weight Unit', 'Dimension Name', 'Dimension Type', 'Weight']
        missing = []
        for field in require_fields:
            if field not in fields_name:
                missing.append(field)
        if len(missing) > 0:
            raise except_orm(('Incorrect format found..!'),
                             ('Please provide all the required fields in file, missing fields => %s.' % missing))
        return True

    def fill_dictionary_from_file(self, reader):
        inboud_shipment_data_list = []
        for row in reader:
            vals = {
                'box_no': row.get('Box No', ''),
                'weight_value': row.get('Weight'),
                'weight_unit': row.get('Weight Unit', ''),
                'dimension_name': row.get('Dimension Name', ''),
                'dimension_type': row.get('Dimension Type', ''),
                'dimension_unit': row.get('Dimension Unit', ''),
                'hight': row.get('Height', ''),
                'width': row.get('Width', 0.0),
                'length': row.get('Length', 0.0),
                'seller_sku': row.get('Seller SKU', ''),
                'quantity': row.get('Quantity', 0.0),
            }
            inboud_shipment_data_list.append(vals)
        return inboud_shipment_data_list

    # Commented By: Dhaval Sanghani [25-May-2020]
    # Re-Develop Below Method
    # def import_inbound_shipment_report(self):
    #     """
    #         Import inbound shipment excel report.
    #         @return: True
    #     """
    #     if not self.choose_file:
    #         raise except_orm(('Unable to process..!'), ('Please Upload File to Process...'))
    #
    #     amazon_inbound_shipment_obj = self.env["amazon.inbound.shipment.ept"]
    #     product_ul_ept_obj = self.env["product.ul.ept"]
    #     amazon_product_ept = self.env["amazon.product.ept"]
    #     amazon_carton_content_info_obj = self.env["amazon.carton.content.info.ept"]
    #
    #     active_ids = self._context.get('active_ids', [])
    #     inbound_shipment_id = amazon_inbound_shipment_obj.search([('id', '=', active_ids)], limit=1)
    #     if inbound_shipment_id and inbound_shipment_id.partnered_small_parcel_ids and inbound_shipment_id.shipping_type == 'sp':
    #         return True
    #
    #     current_date = datetime.strftime(datetime.now(), '%Y%m%d%H%M%S%f')
    #     reader = self.read_file(name=current_date)
    #     fields_name = reader.fieldnames
    #
    #     if self.check_fields_validation(fields_name):
    #         #inboud_shipment_data_list = self.fill_dictionary_from_file(reader) or []
    #
    #         box_no_list = []
    #         partnered_small_parcel_list = []
    #         partnered_small_parcel_dict = {}
    #         amazon_carton_content_info_dict = {}
    #
    #         for row in reader:
    #             box_no = row.get("Box No", "")
    #             seller_sku = row.get('Seller SKU', '')
    #             quantity = row.get('Quantity', '')
    #             amazon_product = amazon_product_ept.search([("seller_sku", "=", seller_sku)],
    #                                                        limit=1)
    #
    #             if amazon_product:
    #                 amazon_carton_content_info = amazon_carton_content_info_obj.search(
    #                         [("amazon_product_id", "=", amazon_product.id),
    #                          ("seller_sku", "=", seller_sku), ("quantity", "=", quantity)],
    #                         limit=1)
    #                 if not amazon_carton_content_info:
    #                     carton_details_vals = {
    #                         'amazon_product_id':amazon_product.id,
    #                         'seller_sku':seller_sku,
    #                         'quantity':quantity
    #                     }
    #                     amazon_carton_content_info = amazon_carton_content_info_obj.create(
    #                             carton_details_vals)
    #
    #             if box_no in box_no_list:
    #                 if amazon_carton_content_info_dict and amazon_carton_content_info_dict.get(
    #                         box_no) and seller_sku in amazon_carton_content_info_dict.get(box_no):
    #                     continue
    #
    #                 if amazon_carton_content_info_dict and amazon_carton_content_info_dict.get(
    #                         box_no) and seller_sku not in amazon_carton_content_info_dict.get(
    #                     box_no):
    #                     amazon_carton_content_info and amazon_carton_content_info_dict.get(
    #                         box_no).append(amazon_carton_content_info.id)
    #                 elif not amazon_carton_content_info_dict or not amazon_carton_content_info_dict.get(
    #                         box_no):
    #                     amazon_carton_content_info and amazon_carton_content_info_dict.update(
    #                         {box_no: [amazon_carton_content_info.id]})
    #
    #             else:
    #                 box_no_list.append(box_no)
    #                 _dimension_domain = [
    #                     ("type", "=", row.get('Dimension Unit', '')),
    #                     ("dimension_unit", "=", row.get('Dimension Unit', '')),
    #                     ("height", "=", row.get('Height', 0.00)),
    #                     ("width", "=", row.get('Width', 0.00)),
    #                     ("length", "=", row.get('Length', 0.00)),
    #                 ]
    #                 product_ul = product_ul_ept_obj.search(_dimension_domain, limit=1)
    #                 if not product_ul:
    #                     dimension_vals = {
    #                         'name': row.get('Dimension Name', ''),
    #                         'type': row.get('Dimension Type', ''),
    #                         'dimension_unit': row.get('Dimension Unit', ''),
    #                         'height': row.get('Height', 0.00),
    #                         'width': row.get('Width', 0.00),
    #                         'length': row.get('Length', 0.00),
    #                     }
    #                     product_ul_id = product_ul_ept_obj.create(dimension_vals)
    #                 vals = {
    #                     'ul_id':(product_ul.id if product_ul else (
    #                             product_ul_id and product_ul_id.id)) or False,
    #                     'box_no':row.get("Box No", ""),
    #                     'weight_value':row.get("Weight", 0.0),
    #                     'weight_unit':row.get("Weight Unit", "")
    #                 }
    #                 amazon_carton_content_info and amazon_carton_content_info_dict.update(
    #                         {box_no:[amazon_carton_content_info.id]})
    #                 partnered_small_parcel_dict.update({str(box_no):vals})
    #         if partnered_small_parcel_dict and box_no_list:
    #             for parcel_box_no in box_no_list:
    #                 if partnered_small_parcel_dict.get(
    #                         parcel_box_no) and amazon_carton_content_info_dict.get(parcel_box_no):
    #                     partnered_small_parcel_dict.get(parcel_box_no).update({"carton_info_ids": [
    #                         (6, 0, amazon_carton_content_info_dict.get(parcel_box_no))]})
    #                     partnered_small_parcel_list.append(
    #                         (0, 0, partnered_small_parcel_dict.get(parcel_box_no)))
    #                 else:
    #                     partnered_small_parcel_list.append(
    #                         (0, 0, partnered_small_parcel_dict.get(parcel_box_no)))
    #
    #         if inbound_shipment_id.shipping_type == 'sp':
    #             inbound_shipment_id.partnered_small_parcel_ids = partnered_small_parcel_list
    #         else:
    #             inbound_shipment_id.partnered_ltl_ids = partnered_small_parcel_list
    #
    #     return True

    def import_inbound_shipment_report(self):
        """
        Use: Import inbound shipment excel report.
        Added By: Dhaval Sanghani [@Emipro Technologies]
        Added On: 25-May-2020
        @param: {}
        @return: {}
        """
        if not self.choose_file:
            raise except_orm('Unable to process..!', 'Please Upload File to Process...')

        amazon_inbound_shipment_obj = self.env["amazon.inbound.shipment.ept"]
        product_ul_ept_obj = self.env["product.ul.ept"]
        amazon_product_ept = self.env["amazon.product.ept"]

        active_ids = self._context.get('active_ids', [])
        inbound_shipment = amazon_inbound_shipment_obj.browse(active_ids)

        current_date = datetime.strftime(datetime.now(), '%Y%m%d%H%M%S%f')
        reader = self.read_file(name=current_date)
        fields_name = reader.fieldnames

        if self.check_fields_validation(fields_name):

            instance = inbound_shipment.instance_id_ept
            new_boxes = []
            parcel_list = []
            parcel_dict = {}

            for row in reader:
                box_no = row.get("Box No", "")
                seller_sku = row.get('Seller SKU', '')
                quantity = row.get('Quantity', 0.0) and float(row.get('Quantity', 0.0)) or 0.0

                amazon_product = amazon_product_ept.search_amazon_product(instance.id, seller_sku, 'FBA')
                if not amazon_product:
                    raise except_orm('%s Amazon Product Not for %s Instance..!' % (seller_sku, instance.name))

                # shipment_line = inbound_shipment.odoo_shipment_line_ids.\
                #     filtered(lambda line: line.amazon_product_id.id == amazon_product.id)
                #
                # if not shipment_line:
                #     raise except_orm('Box Info Not Imported. %s Product Shipment Line Not Found..!' % seller_sku)

                carton_details_vals = {
                    'amazon_product_id': amazon_product.id,
                    'quantity': quantity
                }

                # Create a New Box Info
                box_no not in new_boxes and new_boxes.append(box_no)

                _dimension_domain = [
                    ("type", "=ilike", row.get('Dimension Type', '')),
                    ("dimension_unit", "=ilike", row.get('Dimension Unit', '')),
                    ("height", "=", row.get('Height', 0.00)),
                    ("width", "=", row.get('Width', 0.00)),
                    ("length", "=", row.get('Length', 0.00)),
                ]
                product_ul = product_ul_ept_obj.search(_dimension_domain, limit=1)

                if not product_ul:
                    dimension_vals = {
                        'name': row.get('Dimension Name', ''),
                        'type': row.get('Dimension Type', ''),
                        'dimension_unit': row.get('Dimension Unit', ''),
                        'height': row.get('Height', 0.00),
                        'width': row.get('Width', 0.00),
                        'length': row.get('Length', 0.00),
                    }
                    product_ul = product_ul_ept_obj.create(dimension_vals)

                vals = {
                    'ul_id': product_ul.id,
                    'box_no': box_no,
                    'weight_value': row.get("Weight", 0.0),
                    'weight_unit': row.get("Weight Unit", ""),
                    'box_expiration_date': row.get('Expiry Date') or False
                }
                if parcel_dict.get(box_no, False):
                    carton_info = parcel_dict.get(box_no, {}).get('carton_info_ids', [])
                    flag = True
                    for item in carton_info:
                        if item[2].get('amazon_product_id', False) == amazon_product.id:
                            total_qty = item[2].get('quantity', 0.0) + quantity
                            item[2].update({'quantity': total_qty})
                            flag = False

                    if flag:
                        parcel_dict.get(box_no, {}).get('carton_info_ids', []).append((0, 0, carton_details_vals))
                else:
                    vals.update({'carton_info_ids': [(0, 0, carton_details_vals)]})
                    parcel_dict.update({box_no: vals})

            [parcel_list.append((0, 0, parcel_dict.get(box_no))) for box_no in new_boxes]
            if parcel_list:
                #if inbound_shipment.shipping_type == 'sp':
                if inbound_shipment.transport_type in ['partnered_small_parcel_data','non_partnered_small_parcel_data', 'non_partnered_ltl_data']:
                    inbound_shipment.partnered_small_parcel_ids = parcel_list
                else:
                    inbound_shipment.partnered_ltl_ids = parcel_list

        return True
