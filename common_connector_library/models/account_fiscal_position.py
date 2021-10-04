from odoo import fields, models, api
import logging
_logger = logging.getLogger(__name__)

class AccountFiscalPosition(models.Model):
    _inherit = 'account.fiscal.position'

    origin_country_ept = fields.Many2one('res.country', string='Origin Country',
                                         help="Warehouse country based on sales order warehouse "
                                              "country system will apply fiscal position")

    @api.model
    def _get_fpos_by_region(self, country_id=False, state_id=False, zipcode=False, vat_required=False):
        """
        Search fiscal position based on origin country,
        In context origin_country_ept will get if origin country is from Europe Group.
        updated by : twinkalc
        updated on : 7th jan 2021
        """
        origin_country_ept = self._context.get('origin_country_ept', False)
        if not origin_country_ept:
            return super(AccountFiscalPosition,self)._get_fpos_by_region(country_id=country_id, state_id=state_id,
                                                                         zipcode=zipcode, vat_required=vat_required)
        if not country_id:
            return False
        base_domain = [('auto_apply', '=', True), ('vat_required', '=', vat_required)]
        company_id = self.env.context.get('force_company', self.env.company.id)
        base_domain.append(('company_id', '=', company_id))
        null_state_dom = state_domain = [('state_ids', '=', False)]
        null_zip_dom = zip_domain = [('zip_from', '=', False), ('zip_to', '=', False)]
        if zipcode and zipcode.isdigit():
            zipcode = int(zipcode)
            zip_domain = [('zip_from', '<=', zipcode), ('zip_to', '>=', zipcode)]
        else:
            zipcode = 0

        if state_id:
            state_domain = [('state_ids', '=', state_id)]
        domain_country = base_domain + [('country_id', '=', country_id)]

        # Build domain to search records with exact matching criteria
        fpos = self.search(domain_country + state_domain + zip_domain, limit=1)
        # return records that fit the most the criteria, and fallback on less specific
        # fiscal positions if any can be found
        if not fpos and state_id:
            fpos = self.search(domain_country + null_state_dom + zip_domain, limit=1)
        if not fpos and zipcode:
            fpos = self.search(domain_country + state_domain + null_zip_dom, limit=1)
        if not fpos and state_id and zipcode:
            fpos = self.search(domain_country + null_state_dom + null_zip_dom, limit=1)
        #Check fiscal position  based on origin country
        domain = [\
            ('vat_required', '=', vat_required),
            '|', ('origin_country_ept', '=', origin_country_ept),
            ('origin_country_ept', '=', False)]

        company_id = self.env.context.get('force_company', self.env.company.id)
        domain.append(('company_id', '=', company_id))
        is_amazon_fpos = self._context.get('is_amazon_fpos', False)
        if is_amazon_fpos:
            domain.append(('is_amazon_fpos', '=', is_amazon_fpos))

        is_bol_fiscal_position = self._context.get('is_bol_fiscal_position', False)
        if is_bol_fiscal_position:
            domain.append(('is_bol_fiscal_position', '=', is_bol_fiscal_position))

        # search fpos with auto apply false for bol and amazon order.
        if not is_amazon_fpos and not is_bol_fiscal_position:
            domain = domain + [('auto_apply', '=', True)]

        fiscal_position = self.search(domain + [('country_id', '=', country_id)], limit=1)
        if fiscal_position:
            return fiscal_position
        fiscal_position = self.search(domain + [('country_group_id.country_ids', '=', country_id)], limit=1)
        if fiscal_position:
            return fiscal_position
        fiscal_position = self.search(domain + [('country_id', '=', None), ('country_group_id', '=', None)], limit=1)
        if fiscal_position:
            return fiscal_position
        return fpos or False
