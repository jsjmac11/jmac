# -*- coding: utf-8 -*-
"""
Inherited Res Partner.
"""
from odoo import api, models, fields
from odoo.addons.iap.models import iap
from ..endpoint import DEFAULT_ENDPOINT


class ResPartner(models.Model):
    """
    Inherited for VAT configuration in partner of Warehouse.
    """
    _inherit = "res.partner"

    is_amz_customer = fields.Boolean("Is Amazon Customer?")

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        if not self.env.context.get('is_amazon_partner', False):
            args = [('is_amz_customer', '=', False)] + list(args)
        return super(ResPartner, self)._search(args, offset, limit, order, count, access_rights_uid)

    @api.onchange("country_id")
    def _onchange_country_id(self):
        """
        Inherited for updating the VAT number of the partner as per the VAT configuration.
        @author: Maulik Barad on Date 13-Jan-2020.
        :Updated By: Kishan Sorani on date 07-Sep-2021
        :Mod: Fix Issue in default set VAT number in Partner
        """
        warehouse_obj = self.env["stock.warehouse"]
        vat_config_obj = self.env["vat.config.ept"]
        if self.country_id:
            warehouses = warehouse_obj.search([("company_id", "=", self.env.company.id)])
            warehouse_partner =\
                warehouses.filtered(lambda warehouse: warehouse.partner_id and warehouse.partner_id.id == self._origin.id and not warehouse.partner_id.vat)
            if warehouse_partner:
                vat_config_record = vat_config_obj.search([("company_id", "=", self.env.company.id)])
                vat_config_line = vat_config_record.vat_config_line_ids.filtered(\
                    lambda x: x.country_id == self.country_id)
                if vat_config_line:
                    self.write({"vat": vat_config_line.vat})
        return super(ResPartner, self)._onchange_country_id()

    def auto_delete_customer_pii_details(self):
        """
        Auto Archive Customer's PII Details after 30 days of Import as per Amazon MWS Policies.
        :return:
        """
        if not self.env['amazon.seller.ept'].search([]):
            return True
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        kwargs = {
            'app_name': 'amazon_ept',
            'account_token': account.account_token,
            'dbuuid': dbuuid,
            'updated_records': 'Scheduler for delete PII data has been started.'
        }
        iap.jsonrpc(DEFAULT_ENDPOINT + '/delete_pii', params=kwargs, timeout=1000)

        query = """update res_partner set name='Amazon',commercial_company_name='Amazon', display_name='Amazon', 
                    street=NULL,street2=NULL,email=NULL,city=NULL,state_id=NULL,country_id=NULL,zip=Null,phone=NULL,mobile=NULL
                    from
                    (select r1.id as partner_id,r2.id as partner_invoice_id,r3.id as partner_shipping_id from sale_order
                    inner join res_partner r1 on r1.id=sale_order.partner_id
                    inner join res_partner r2 on r2.id=sale_order.partner_invoice_id
                    inner join res_partner r3 on r3.id=sale_order.partner_shipping_id
                    where amz_instance_id is not null and sale_order.create_date<=current_date-30)T
                    where res_partner.id in (T.partner_id,T.partner_invoice_id,T.partner_shipping_id)
                    """
        self.env.cr.execute(query)

        if self.env.cr.rowcount:
            kwargs.update({'updated_records': 'Archived %d customers' % self.env.cr.rowcount})
            iap.jsonrpc(DEFAULT_ENDPOINT + '/delete_pii', params=kwargs, timeout=1000)
        return True

    def check_amz_vat_validation_ept(self, vat, country, vat_country, instance):
        vat = self._fix_vat_number(vat, country.id)
        if instance.company_id.vat_check_vies:
            check_vat = self.vies_vat_check(vat_country.lower(), vat)
        else:
            check_vat = self.simple_vat_check(vat_country.lower(), vat)
        return check_vat
