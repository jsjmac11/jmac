# -*- coding: utf-8 -*-pack
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    # App information
    'name': 'Amazon Odoo Connector',
    'version': '13.3.62',
    'category': 'Sales',
    'license': 'OPL-1',
    'summary': 'Amazon Odoo Connector helps you integrate & manage your Amazon Seller Account '
               'operations from Odoo. '
               'Save time, efforts and avoid errors due to manual data entry to boost your Amazon '
               'sales with this '
               'connector.',
    # Author
    'author': 'Emipro Technologies Pvt. Ltd.',
    'website': 'http://www.emiprotechnologies.com/',
    'maintainer': 'Emipro Technologies Pvt. Ltd.',
    # Dependencies
    'depends': ['iap', 'auto_invoice_workflow_ept', 'common_connector_library', 'rating'],
    # Views
    'data': [
        # cron
        'data/ir_cron.xml',
        'security/res_groups.xml',
        'view/vat_config_ept.xml',
        'view/res_config_view.xml',
        'view/amazon_seller.xml',
        'view/product_view.xml',
        'wizard_views/shipment_report_configure_fulfillment_center_ept.xml',
        'view/shipping_report.xml',
        'wizard_views/amazon_outbound_order_wizard_view.xml',
        'view/sale_view.xml',
        'wizard_views/amazon_process_import_export.xml',
        'view/invoice_view.xml',
        'view/instance_view.xml',
        'view/fbm_sale_order_report_ept.xml',
        'view/stock_warehouse.xml',
        'view/delivery.xml',

        'view/product_ul.xml',

        'wizard_views/amazon_product_mapping.xml',
        'wizard_views/export_product_wizard_view.xml',
        'wizard_views/import_product_removal_order_wizard.xml',
        'wizard_views/queue_process_wizard_view.xml',

        'wizard_views/import_product_inbound_shipment.xml',
        'wizard_views/import_inbound_shipment_report_wizard.xml',
        'wizard_views/inbound_shipment_labels_wizard.xml',

        'wizard_views/fbm_cron_configuration.xml',
        'wizard_views/fba_cron_configuration.xml',
        'wizard_views/global_cron_configuration.xml',

        'data/import_product_attachment.xml',
        'data/res_partner_data.xml',
        'view/stock_adjustment_view.xml',
        'view/amazon_stock_adjustment_config.xml',
        'view/amazon_stock_adjustment_group.xml',
        'view/adjustment_reason.xml',
        'view/stock_view.xml',
        'view/stock_move_view.xml',
        'view/removal_order_config.xml',
        'view/stock_location_route.xml',
        'view/sale_order_return_report.xml',
        'wizard_views/settlement_report_configure_fees_ept.xml',
        'view/settlement_report.xml',
        'view/removal_order_view.xml',
        'view/amazon_removal_order_report.xml',
        'view/sale_order_return_report.xml',
        'view/amazon_fba_live_stock_report_view.xml',
        'view/stock_inventory.xml',
        'view/log_book_menu.xml',
        'view/fulfillment_center_config_view.xml',

        # inbound view
        'view/inbound_shipment_plan.xml',
        'view/inbound_shipment_ept.xml',
        'view/shipment_picking.xml',
        'wizard_views/inbound_shipment_details_wizard.xml',

        # 'view/stock_picking_view.xml',
        # data
        'data/amazon.developer.details.ept.csv',
        'view/cancel_order_wizard_view.xml',
        'view/feed_submission_history.xml',
        'view/shipped_order_data_queue_view.xml',
        'view/active_product_listing.xml',
        'view/rating_report_view.xml',
        'view/rating_view.xml',
        'view/vcs_tax_report.xml',
        'view/res_country_view.xml',
        'view/account_fiscal_position.xml',
        'view/common_log_lines_ept.xml',
        'data/product_data.xml',
        'data/import_removal_order_attachment.xml',

        # load all country name with fulfillment code
        'data/amazon.fulfillment.country.rel.csv',

        'data/ir_sequence.xml',
        'data/email_template.xml',
        'data/amazon.adjustment.reason.group.csv',
        'data/amazon.adjustment.reason.code.csv',
        'data/email_template.xml',
        'data/amazon_transaction_type.xml',
        'data/amazon_return_reason_data.xml',
        'data/res_country_group.xml',
        'data/amz_invoice_data.xml',
        # security
        'security/ir.model.access.csv',
        # 'report/invoice_paperformat.xml',
        # 'report/invoice_report.xml'

    ],
    # Odoo Store Specific
    'images': ['static/description/cover.jpg'],

    # Technical
    'installable': True,
    'auto_install': False,
    'live_test_url': 'https://www.emiprotechnologies.com/free-trial?app=amazon-ept&version=13'
                     '&edition=enterprise',
    'application': True,
    'price': 479.00,
    'currency': 'EUR',
}
