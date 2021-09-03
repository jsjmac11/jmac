# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE URL <https://store.webkul.com/license.html/> for full copyright and licensing details.
#################################################################################
from odoo.exceptions import UserError, RedirectWarning, ValidationError, Warning
from odoo.addons.odoo_multi_channel_sale.tools import DomainVals, MapId
from odoo.addons.amazon_odoo_bridge.tools.tools import CHANNELDOMAIN
from odoo.addons.amazon_odoo_bridge.tools.tools import JoinList as JL
from odoo.addons.amazon_odoo_bridge.tools.tools import extract_item as ET
import xml.etree.ElementTree as ElementTree
from collections import defaultdict
from operator import itemgetter
from odoo import fields, models, _
from odoo import tools, api
import logging
_logger = logging.getLogger(__name__)

REPORT_STATE = [
    ('draft', 'Draft'),
    ('request', 'Request Send'),
    ('generate', 'Report Generated'),
    ('receive', 'Data Received'),
    ('inactive', 'In Active')
]

REPORT_TYPE = [
    ('OPEN_LISTINGS_MERCHANT_LISTINGS', 'Inventory+Active Listings Report'),
    ('_GET_XML_BROWSE_TREE_DATA_', 'Browse Tree Report'),
]

class MWSReports(models.Model):
    _name = "mws.report"
    _description = "MWS Report"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Name'
    )
    report_type = fields.Selection(
        selection=REPORT_TYPE,
        string='Report Type',
        default='OPEN_LISTINGS_MERCHANT_LISTINGS',
        required=1
    )
    state = fields.Selection(
        selection=REPORT_STATE,
        default='draft',
        required=1
    )
    request_id = fields.Char(
        string='Request ID',
        copy=False
    )
    report_id = fields.Char(
        string='Report ID',
        copy=False
    )
    data = fields.Text(
        string='File Data',
        help='Report Data Recived Form Amazon For Report ID',
        copy=False
    )
    ml_request_id = fields.Char(
        string='Listing Request ID',
        help='Request ID Send To Amazon For Active Listing Report',
        copy=False
    )
    ml_report_id = fields.Char(
        string='Listing Report ID',
        help='Report ID Recived For Amazon For Active Listing Report',
        copy=False
    )
    ml_data = fields.Text(
        string='Listing Data',
        help='Merchant Listing Report Data Recived Form Amazon For Active Listing Report ID',
        copy=False
    )
    browse_node_id = fields.Char(
        string='Browse Node ID',
        copy=False
    )
    channel_id = fields.Many2one(
        comodel_name='multi.channel.sale',
        string='Channel',
        required=1,
        domain=CHANNELDOMAIN
    )

    @api.model
    def create(self, vals):
        try:
            vals['name'] = self.env.ref(
                'amazon_odoo_bridge.report_sequence').next_by_id()
        except Exception as e:
            pass
        return super(MWSReports, self).create(vals)

    @staticmethod
    def merge_dict(dict1, dict2):
        """Merge product attribute of same product asin """
        dict1 = dict(filter(itemgetter(0), dict1.items()))
        dict2 = dict(filter(itemgetter(0), dict2.items()))
        data = dict1 and dict1.copy() or dict2.copy()
        for key in dict1:
            data[key].update(dict2.get(key, ''))
        return data

    def get_report_data(self, header=None):
        api_sdk = self.channel_id.get_mws_api_sdk()
        header = header or self.channel_id.get_mws_header()
        merchant_listing = api_sdk.extract_report_data(
            report=self.ml_data, report_header=header
        )
        flat_file = api_sdk.extract_report_data(
            report=self.data, report_header=header
        )
        return self.merge_dict(flat_file, merchant_listing)

    def send_request(self):
        error_report_ids = []
        message = 'Request send successfully.'
        for record in self:
            channel_id = record.channel_id
            api_sdk = channel_id.get_mws_api_sdk()
            if record.report_type == 'OPEN_LISTINGS_MERCHANT_LISTINGS':
                status = False
                request_id = api_sdk.wk_request_report(
                    '_GET_FLAT_FILE_OPEN_LISTINGS_DATA_')
                if request_id:
                    record.request_id = request_id
                    status = True
                if status:
                    ml_request_id = api_sdk.wk_request_report(
                        '_GET_MERCHANT_LISTINGS_DATA_')
                    if ml_request_id:
                        record.ml_request_id = ml_request_id
                        status = True
                    else:
                        status = False
                    if status == True:
                        record.state = 'request'
                    else:
                        error_report_ids += [record]
            else:
                report_options = None
                if record.report_type == '_GET_XML_BROWSE_TREE_DATA_':
                    browse_node_id = record.browse_node_id
                    if browse_node_id:
                        report_options = "BrowseNodeId=%s" % (browse_node_id)
                    else:
                        report_options = "RootNodesOnly=true"
                elif 'ORDER' in record.report_type:
                    report_options = "Scheduled=true"
                request_id = api_sdk.wk_request_report(
                    record.report_type, report_options=report_options)
                if request_id:
                    record.request_id = request_id
                    record.state = 'request'
                else:
                    error_report_ids += [record]

        if len(error_report_ids):
            message = 'Request %s not send properly,please try once again for these report.' % (
                JL(report_ids))
        return self.env['multi.channel.sale'].display_message(message)

    def generate_report(self):
        error_report_ids = []
        message = 'Report generated successfully.'
        for record in self:
            channel_id = record.channel_id
            api_sdk = channel_id.get_mws_api_sdk()

            reportIds = [record.request_id]
            if record.report_type == 'OPEN_LISTINGS_MERCHANT_LISTINGS':
                reportIds += [record.ml_request_id]
            response = api_sdk.wk_get_reportId(reportIds)
            if len(response):
                if type(response) != list:
                    response = [response]
                data = dict(map(lambda item: (
                    ET(item.get('ReportRequestId', {})),
                    ET(item.get('ReportId', {}))), response)
                )
                status = False
                report_id = data.get(record.request_id)
                if report_id:
                    record.report_id = report_id
                    status = True

                if status and record.report_type == 'OPEN_LISTINGS_MERCHANT_LISTINGS':
                    ml_report_id = data.get(record.ml_request_id)
                    if ml_report_id:
                        record.ml_report_id = ml_report_id
                        status = True
                    else:
                        status = False
                if status:
                    record.state = 'generate'
                else:
                    error_report_ids += [record]
            else:
                error_report_ids += [record]
        if len(error_report_ids):
            message = 'Report yet not generated, please try after a while.'
        return self.env['multi.channel.sale'].display_message(message)

    def mws_get_categories_vals(self, node, result_dict=None):
        node_ids = node.findtext('browsePathById')
        node_names = node.findtext('browsePathByName')
        result = []
        result_dict = result_dict or dict()
        if node_ids and node_names:
            ids_list = node_ids.split(',')  # [::-1]
            names_list = node_names.replace(', ','-').split(',')  # [::-1]
            start_mode_index = len(ids_list)-len(names_list)
            last_node_id = None
            for node_id, node_name in zip(ids_list[start_mode_index:], names_list):
                vals = dict(
                    store_id=node_id,
                    name=node_name.replace('-',', ').strip(),
                    parent_id=last_node_id,
                    leaf_category= True if node.findtext('hasChildren')=='false' 
                        and node.findtext('browseNodeId')==node_id else False
                )
                result += [vals]
                result_dict[node_id] = vals
                last_node_id = node_id
            return dict(
                result_dict=result_dict,
                last_node_id=last_node_id,
                result=result
            )

    def mws_import_category(self, category_vals, category_rel_dict, channel_id):
        create_ids = []
        update_ids = []
        for categ_id, categ_val in category_vals.items():
            rel_dict = category_rel_dict.get(categ_id)
            if rel_dict:
                categ_val.update(rel_dict)
            res = channel_id._match_create_product_categ(categ_val)
            feed_id = res.get('data')
            if res.get('update'):
                update_ids.append(feed_id)
            else:
                create_ids.append(feed_id)
        return dict(
            create_ids=create_ids,
            update_ids=update_ids,
        )

    def mws_get_product_type_vals(self, node):
        product_type = node.findtext('productTypeDefinitions')
        result = dict()
        if product_type:
            node_names = product_type.split(',')
            for name in node_names:
                result[name] = name
        return result

    def mws_import_product_type(self, node, channel_id):
        create_ids, update_ids = self.env['mws.product.type'], self.env['mws.product.type']
        vals = self.mws_get_product_type_vals(node)
        Type = self.env['mws.product.type']
        for name in vals:
            domain = [('name', '=', name), ('channel_id', '=', channel_id.id)]
            match = Type.search(domain)
            if match:
                update_ids += match
            else:
                create_ids += Type.create(DomainVals(domain))
        _logger.info("=IMPORT Product Type===%r=====%r" %
                     (update_ids, create_ids))
        return dict(
            create_ids=create_ids,
            update_ids=update_ids,
        )

    def mws_get_product_attribute_vals(self, node):
        attributes = node.findall('refinementsInformation/refinementName')
        result = defaultdict(set)
        if attributes:
            for attribute in attributes:
                name = attribute.get('name')
                store_attribute_id = attribute.findtext(
                    'refinementField/refinementAttribute')
                temp_name = '%s_wkodoo_%s' % (name, store_attribute_id)
                values = attribute.findtext('refinementField/acceptedValues')
                if values:
                    result[temp_name] |= set(values.split(','))
        return result

    def mws_import_attribute_value(self, store_id, name, attribute_id, channel_id):
        match = channel_id.match_attribute_value_mappings(store_id)
        if match:
            return match
        erp_id = channel_id.get_store_attribute_value_id(
            name, attribute_id, create_obj=True)
        return channel_id.create_attribute_value_mapping(
            erp_id=erp_id, store_id=store_id,
            store_attribute_value_name=store_id
        )

    def mws_import_attribute(self, store_id, name, channel_id):
        match = channel_id.match_attribute_mappings(store_id)
        if match:
            return match
        erp_id = channel_id.get_store_attribute_id(store_id, create_obj=True)
        return channel_id.create_attribute_mapping(
            erp_id=erp_id,
            store_id=store_id,
            store_attribute_name=store_id
        )

    def mws_import_attributes(self, node, channel_id):
        create_attr_ids = []
        create_attr_vals_ids = []
        vals = self.mws_get_product_attribute_vals(node)
        result = []
        for name_id, val_list in vals.items():
            if name_id:
                name, store_attribute_id = name_id.split('_wkodoo_')
                attr_vals = dict(
                    name=name.strip(),
                    store_attribute_id=store_attribute_id,
                    store_attribute_name=store_attribute_id,
                    store_attribute_value_name_list=list(val_list)
                )
                result += [attr_vals]
                # attr_map_id = self.mws_import_attribute(
                #     store_attribute_id,name,channel_id)
                # attribute_id = attr_map_id.attribute_name
                # create_attr_ids+=[attribute_id]
                # for val in val_list:
                #     attr_val_map_id = self.mws_import_attribute_value(
                #         store_attribute_id,name,attribute_id.id,channel_id)
                #     create_attr_vals_ids+=[attr_val_map_id.attribute_value_name]
        # _logger.info("=IMPORT ATTRIBUTE===%r=====%r"%(create_attr_ids,create_attr_vals_ids))
        return dict(
            create_attr_ids=create_attr_ids,
            create_attr_vals_ids=create_attr_vals_ids,
            result=result,
        )

    def mws_import_xml_tree_data(self, root_data, channel_id):
        category_vals = dict()
        category_rel_dict = dict()
        for node in root_data.findall('Node'):
            categ_res = self.mws_get_categories_vals(node)
            if categ_res:
                category_vals.update(categ_res.get('result_dict'))

            # attr_res = self.mws_import_attributes(node, channel_id)
            # # type_res = self.mws_import_product_type(node,channel_id)
            # type_vals = self.mws_get_product_type_vals(node)
            # category_rel_dict[categ_res['last_node_id']] = dict(
            #     attribute_ids = attr_res.get('result'),
            #     mws_product_type_ids =[dict(name=type_name) for type_name in type_vals]
            # )
        return self.mws_import_category(category_vals, category_rel_dict, channel_id)

    def create_category(self):
        message = ''
        report_type = '_GET_XML_BROWSE_TREE_DATA_'
        update_ids, create_ids, map_create_ids, map_update_ids = [], [], [], []
        for record in self:
            channel_id = record.channel_id
            root_data = ElementTree.fromstring(record.data)
            feed_res = self.mws_import_xml_tree_data(
                root_data, channel_id=channel_id)
            post_res = self.env['channel.operation'].post_feed_import_process(
                channel_id, feed_res)
            create_ids += post_res.get('create_ids')
            update_ids += post_res.get('update_ids')
            map_create_ids += post_res.get('map_create_ids')
            map_update_ids += post_res.get('map_update_ids')
            message += self.env['multi.channel.sale'].get_feed_import_message(
                'category', create_ids, update_ids, map_create_ids, map_update_ids
            )
        return self.env['multi.channel.sale'].display_message(message)

    def receive_data(self):
        report_ids = []
        message = 'Data received successfully.'
        for record in self:
            channel_id = record.channel_id
            api_sdk = channel_id.get_mws_api_sdk()
            status = False
            report_res = api_sdk.wk_get_report_data(record.report_id)
            message += report_res.get('message')
            report_data = report_res.get('data')
            if report_data:
                if record.report_type == '_GET_XML_BROWSE_TREE_DATA_':
                    data = report_data.original
                    record.data = data
                    record.state = 'receive'
                    status = True
                else:
                    apparent_encoding = report_data.response.apparent_encoding
                    encoding = report_data.response.encoding
                    try:
                        data = report_data.parsed.decode(apparent_encoding)
                    except UnicodeDecodeError as e:
                        data = report_data.parsed.decode(encoding)
                    if data:
                        record.data = data
                        status = True
                    if status and record.report_type == 'OPEN_LISTINGS_MERCHANT_LISTINGS':
                        ml_res = api_sdk.wk_get_report_data(
                            record.ml_report_id)
                        message += ml_res.get('message')
                        ml_data = ml_res.get('data')
                        if ml_data and ml_data.parsed:
                            try:
                                record.ml_data = ml_data.parsed.decode(apparent_encoding)
                            except UnicodeDecodeError as e:
                                record.ml_data = ml_data.parsed.decode(encoding)
                            status = True
                    if status:
                        record.state = 'receive'
                    else:
                        report_ids += [record.id]

        if len(report_ids):
            message = 'Report yet not generated, please try after a while.'
            message = 'Data yet not receive, please verify your report id and try once again.'
            return self.env['multi.channel.sale'].display_message(message)

    def inactive_report(self):
        for record in self:
            record.state = 'inactive'

    @api.model
    def _cron_send_request(self):

        channel_ids = self.env['multi.channel.sale'].search(CHANNELDOMAIN)
        for channel_id in channel_ids:
            if channel_id.mws_imp_product_cron:
                vals = dict(
                    state='draft',
                    channel_id=channel_id.id,
                    report_type='OPEN_LISTINGS_MERCHANT_LISTINGS'
                )
                report_id = self.create(vals)
                report_id.send_request()
        _logger.info("====Cron Send Request Done")

    @api.model
    def _cron_generate_report(self):
        domain = [
            ('state', '=', 'request'),
            ('ml_request_id', '!=', False),
            ('request_id', '!=', False),
            ('report_type', '=', 'OPEN_LISTINGS_MERCHANT_LISTINGS'),
        ]
        for report_id in self.search(domain):
            if report_id.channel_id.mws_imp_product_cron:
                report_id.generate_report()
        _logger.info("====Cron Generate Report Done")

    @api.model
    def _cron_receive_data(self):
        domain = [
            ('state', '=', 'generate'),
            ('ml_report_id', '!=', False),
            ('report_id', '!=', False),
            ('report_type', '=', 'OPEN_LISTINGS_MERCHANT_LISTINGS'),
        ]
        for report_id in self.search(domain):
            if report_id.channel_id.mws_imp_product_cron:
                report_id.receive_data()
        _logger.info("====Cron Receive Report Data Done")
