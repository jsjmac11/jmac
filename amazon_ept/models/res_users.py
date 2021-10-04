from odoo import models, fields, api, _
from odoo import SUPERUSER_ID


class res_users(models.Model):
    _inherit = 'res.users'

    def set_user_fba_fbm_group(self, company_ids):
        self = self.with_user(SUPERUSER_ID)
        amazon_seller_obj = self.env['amazon.seller.ept']
        amazon_fba_group = self.env.ref('amazon_ept.group_amazon_fba_ept')
        amazon_fbm_group = self.env.ref('amazon_ept.group_amazon_fbm_ept')
        amazon_fba_fbm_group = self.env.ref(
            'amazon_ept.group_amazon_fba_and_fbm_ept')
        amazon_user_group = self.env.ref('amazon_ept.group_amazon_user_ept')
        amazon_manager_group = self.env.ref('amazon_ept.group_amazon_manager_ept')
        user_list = list(set(amazon_user_group.users.ids + amazon_manager_group.users.ids))
        amazon_selling_both = amazon_seller_obj.search([('amazon_selling', '=', 'Both')])
        amazon_selling_fba = amazon_seller_obj.search([('amazon_selling', '=', 'FBA')])
        amazon_selling_fbm = amazon_seller_obj.search([('amazon_selling', '=', 'FBM')])
        amazon_selling = 'Both'
        if amazon_selling_fba:
            other_seller_both = amazon_selling_both
            seller_company = other_seller_both.filtered(lambda x: x.company_id.id in company_ids)
            if other_seller_both and seller_company:
                amazon_selling = 'Both'
            else:
                other_seller_fbm = amazon_selling_fbm
                seller_company = other_seller_fbm.filtered(lambda x: x.company_id.id in company_ids)
                if other_seller_fbm and seller_company:
                    amazon_selling = 'Both'
                else:
                    amazon_selling = 'FBA'
        elif amazon_selling_fbm:
            other_seller_both = amazon_selling_both
            seller_company = other_seller_both.filtered(lambda x: x.company_id.id in company_ids)
            if other_seller_both and seller_company:
                amazon_selling = 'Both'
            else:
                other_seller_fba = amazon_selling_fba
                seller_company = other_seller_fba.filtered(lambda x: x.company_id.id in company_ids)
                if other_seller_fba and seller_company:
                    amazon_selling = 'Both'
                else:
                    amazon_selling = 'FBM'

        if amazon_selling == 'FBM':
            amazon_fbm_group.write({'users': [(6, 0, user_list)]})
            amazon_fba_group.write({'users': [(6, 0, [])]})
            amazon_fba_fbm_group.write({'users': [(6, 0, [])]})
        elif amazon_selling == 'FBA':
            amazon_fba_group.write({'users': [(6, 0, user_list)]})
            amazon_fbm_group.write({'users': [(6, 0, [])]})
            amazon_fba_fbm_group.write({'users': [(6, 0, [])]})
        elif amazon_selling == 'Both':
            amazon_fba_fbm_group.write({'users': [(6, 0, user_list)]})
            amazon_fba_group.write({'users': [(6, 0, user_list)]})
            amazon_fbm_group.write({'users': [(6, 0, user_list)]})
        return True

    @api.model
    def create(self, vals):
        user = super(res_users, self).create(vals)
        if user.has_group('amazon_ept.group_amazon_user_ept') or user.has_group('amazon_ept.group_amazon_manager_ept'):
            company_ids = user.company_ids.ids
            self.set_user_fba_fbm_group(company_ids)
        return user

    def write(self, vals):
        res = super(res_users, self).write(vals)
        for user in self:
            if user.has_group('amazon_ept.group_amazon_user_ept') or user.has_group('amazon_ept.group_amazon_manager_ept'):
                company_ids = user.company_ids.ids
                user.set_user_fba_fbm_group(company_ids)
        return res
