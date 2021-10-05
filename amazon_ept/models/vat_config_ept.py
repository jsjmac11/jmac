# -*- coding: utf-8 -*-
"""
Vat Configuration Class.
"""
from odoo import fields, models, api


class VatConfigEpt(models.Model):
    """
    For Setting VAT number in warehouse partner.
    @author: Maulik Barad on Date 11-Jan-2020.
    updated by : Kishan Sorani on Date 14-Jun-2021
    """
    _name = "vat.config.ept"
    _description = "VAT Configuration EPT"
    _rec_name = "company_id"

    def _get_company_domain(self):
        """
        Creates domain to only allow to select company from allowed companies in switchboard.
        @author: Maulik Barad on Date 11-Jan-2020.
        """
        return [("id", "in", self.env.context.get('allowed_company_ids'))]

    company_id = fields.Many2one("res.company", domain=_get_company_domain)
    vat_config_line_ids = fields.One2many("vat.config.line.ept", "vat_config_id")
    is_union_oss_vat_declaration = fields.Boolean("Are you Participated in Union-OSS VAT Declaration?",
                                                  default=False, help="The Union-OSS scheme is a simplification"
                                                                      "where if you disclose to opt-in you can benefit"
                                                                      "from reporting your EU B2C cross-border Distance"
                                                                      "Sales through a VAT declaration filed in your"
                                                                      "place of establishment.")
    is_auto_create_taxes = fields.Boolean("Auto Create Taxes?", default=False,
                                          help="Mark true for auto create taxes and set into newly "
                                               "created fiscal positions.")
    account_id = fields.Many2one("account.account", string="Account", help="Select account which configure in "
                                                                           " automatic created taxes records")

    _sql_constraints = [
        ("unique_company_vat_config", "UNIQUE(company_id)", "VAT configuration is already added for the company.")]

    def write(self, vals):
        """
        Inherited write method for creating excluded_vat_group countries
        country to country[B2C] fiscal position based on VAT number configuration
        :param: vals: data dict for update record
        @author: Kishan Sorani on Date 25-Jun-2020.
        """
        res = super(VatConfigEpt, self).write(vals)
        if self.is_union_oss_vat_declaration:
            fpos_data = {"company_id": self.company_id.id, "vat_config_id": self.id, "is_amazon_fpos": True}
            self.env['vat.config.line.ept'].create_union_oss_vat_country_fiscal_position(fpos_data)
        return res

    @api.model
    def create(self, vals):
        """
        Inherited create method for creating excluded_vat_group countries
        country to country[B2C] fiscal position based on VAT number configuration
        :param: vals: data dict for create record
        @author: Kishan Sorani on Date 25-Jun-2020.
        """
        res = super(VatConfigEpt, self).create(vals)
        if res and res.is_union_oss_vat_declaration:
            fpos_data = {"company_id": res.company_id.id, "vat_config_id": res.id, "is_amazon_fpos": True}
            self.env['vat.config.line.ept'].create_union_oss_vat_country_fiscal_position(fpos_data)
        return res