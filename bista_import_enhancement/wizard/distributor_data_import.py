##############################################################################
#
#    Bista Solutions Pvt. Ltd
#    Copyright (C) 2019 (http://www.bistasolutions.com)
#
##############################################################################

from odoo import fields, models, api, _
from odoo.exceptions import Warning, UserError, ValidationError
from odoo.modules import get_module_resource
import tempfile
import binascii
import xlrd
import base64
import csv
import os
import io

class ProductSupplierinfoImport(models.TransientModel):
    _name = 'product.supplierinfo.import'
    _description = 'Product Supplierinfo Import'

    name = fields.Char(string="name")
    file_upload = fields.Binary(string="Import File")
    import_type = fields.Selection([('dis_price', 'Distributor Pricelist'), ('dis_stock', 'Distributor Stock')], string="Import Type", default='dis_price')

    @api.model
    def csv_validator(self, xml_name):
        name, extension = os.path.splitext(xml_name)
        return True if extension in ['.xls', '.XLS'] or extension in ['.xlsx', '.XLSX'] else False

    def action_import_distributor_pricelist(self):
        csv_data = base64.b64decode(self.file_upload)
        data_file = io.StringIO(csv_data.decode("utf-8"))
        data_file.seek(0)
        file_reader = []
        csv_reader = csv.reader(data_file, delimiter=',')
        file_reader.extend(csv_reader)

        count = 0
        dis_pricelist = []
        for row in file_reader:
            if count == 0:
                count+=1
                continue
            count +=1
            if not row[0] and str(row[0]) == 'Dummy':
                continue
        
            vendor_id = False
            if row[0]:
                vendor_id = self.env['res.partner'].search([('name', '=', str(row[0]).strip())])
            product_id = False
            if row[2]:
                product = row[2]
                product_list = product.split(" ")
                if product_list:
                    product_code = product_list[-1]
                product_id = self.env['product.template'].search([('default_code','=', product_code)])
            currency_id = False
            if row[3]:
                currency_id = self.env['res.currency'].search([('name', '=', str(row[3].strip()))])

            distibutor_pricelist_id = self.env['product.supplierinfo'].search([('name', '=', vendor_id.id), ('product_code', '=', str(row[1].strip()))])
            if distibutor_pricelist_id:
                distibutor_pricelist_id.write({'price': float(row[5]) if row[5] else 0.0})
            else:
                if row[0] and row[1] and row[2]:
                    data_pass = {
                        'name': vendor_id.id or vendor_id[0] or False,
                        'product_code': row[1] if row[1] else False,
                        'product_tmpl_id': product_id.id or vendor_id[0] or False,
                        'currency_id': currency_id.id or currency_id[0] or False,
                        'min_qty': float(row[4]) if row[4] else 0.0,
                        'price': float(row[5]) if row[5] else 0.0,
                        }
                    dis_pricelist = self.env['product.supplierinfo'].create(data_pass)
        return dis_pricelist

    def action_import_distributor_stock(self):
        csv_data = base64.b64decode(self.file_upload)
        data_file = io.StringIO(csv_data.decode("utf-8"))
        data_file.seek(0)
        file_reader = []
        csv_reader = csv.reader(data_file, delimiter=',')
        file_reader.extend(csv_reader)

        count = 0
        dis_stock = []
        for row in file_reader:
            if count == 0:
                count+=1
                continue
            count +=1
            if not row[0] and str(row[0]) == 'Dummy':
                continue

            vendor_id = False
            if row[0]:
                vendor_id = self.env['res.partner'].search([('name', '=', str(row[0]).strip())])
            product_id = False
            if row[1]:
                product = row[1]
                product_list = product.split(" ")
                if product_list:
                    product_code = product_list[-1]
                product_id = self.env['product.template'].search([('default_code','=', product_code)])

            dis_stock_id = self.env['vendor.stock.master.line'].search([('res_partner_id', '=', vendor_id.id), ('product_id', '=', product_id.id)])
            if dis_stock_id:
                dis_stock_id.write({'case_qty': float(row[4]) if row[4] else 0.0})

            else:
                if row[0] and row[1] and row[3] and row[4]:
                    data_pass = {
                        'res_partner_id': vendor_id.id or vendor_id[0] or False,
                        'product_id': product_id.id or vendor_id[0] or False,
                        'abbreviation': row[2] if row[2] else False,
                        'location_id': row[3] if row[3] else False,
                        'case_qty': float(row[4]) if row[4] else 0.0,
                        'hub': row[5] if row[5] else False,
                        'state': row[6] if row[6] else False,
                        'zip': row[7] if row[7] else False,
                        'phone': row[8] if row[8] else False,
                        }
                    dis_stock = self.env['vendor.stock.master.line'].create(data_pass)
        return dis_stock
