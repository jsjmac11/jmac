from odoo import fields, models, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    global_channel_id = fields.Many2one('global.channel.ept', string='Global Channel')
    line_tax_amount_percent = fields.Float(digits='Line Tax Amount', string="Tax amount in per(%)")

    @api.onchange('amount_currency', 'currency_id', 'debit', 'credit',
                  'tax_ids', 'account_id',
                  'analytic_account_id', 'analytic_tag_ids',
                  'line_tax_amount_percent', 'price_unit')
    def _onchange_mark_recompute_taxes(self):
        """
        Use: Super method Override and Add Line tax amount in onchange as Parameter
        set recompute_tax_line boolean as true which has not tax repartition line id for compute tax
        Params: {}
        Return: {}
        """
        ''' Recompute the dynamic onchange based on taxes.
        If the edited line is a tax line, don't recompute anything as the user must be able to
        set a custom value.
        '''
        for line in self:
            context = dict(self._context or {})
            context.update({'tax_computation_context': {'line_tax_amount_percent': line.line_tax_amount_percent}})
            super(AccountMoveLine, self.with_context({'tax_computation_context': {
                'line_tax_amount_percent': line.line_tax_amount_percent}}))._onchange_mark_recompute_taxes()

    @api.onchange('quantity', 'discount', 'price_unit', 'tax_ids',
                  'line_tax_amount_percent')
    def _onchange_price_subtotal(self):
        """
        Use: Super method Override and Pass Line tax amount in onchange as Parameter
        Params: {}
        Return: {}
        """
        for line in self:
            context = dict(self._context or {})
            context.update({'tax_computation_context': {'line_tax_amount_percent': line.line_tax_amount_percent}})
            super(AccountMoveLine, line.with_context(context))._onchange_price_subtotal()

    @api.model
    def _get_price_total_and_subtotal_model(self, price_unit, quantity,
                                            discount, currency,
                                            product, partner, taxes, move_type):
        context = taxes._context
        if context:
            context = dict(context)
        else:
            context = {}
        line_tax_details = context.get('line_tax_details', {})
        if line_tax_details:
            context.update(
                {'tax_computation_context': {
                    'line_tax_amount_percent': line_tax_details.get(product.id, 0.0)}})
        else:
            context.update(
                {'tax_computation_context': {
                    'line_tax_amount_percent': self.line_tax_amount_percent}})

        taxes = taxes.with_context(context)
        if line_tax_details:
            return super(AccountMoveLine,
                         self.with_context({'tax_computation_context': {
                             'line_tax_amount_percent': line_tax_details.get(product.id, 0.0)}})). \
                _get_price_total_and_subtotal_model(price_unit, quantity, discount,
                                                    currency, product,
                                                    partner, taxes, move_type)
        else:
            return super(AccountMoveLine, self.with_context(
                {'tax_computation_context': {'line_tax_amount_percent': self.line_tax_amount_percent}})). \
                _get_price_total_and_subtotal_model(price_unit, quantity, discount,
                                                    currency, product,
                                                    partner, taxes, move_type)

    @api.model_create_multi
    def create(self, vals_list):
        context = dict(self._context or {})
        line_tax_details = {}
        for vals in vals_list:
            line_tax_details.update({vals.get('product_id'): vals.get('line_tax_amount_percent') or 0.0})
        context.update({'line_tax_details': line_tax_details})
        return super(AccountMoveLine, self.with_context(context)).create(vals_list)
