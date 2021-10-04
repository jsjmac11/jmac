from odoo import models, fields

class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    settlement_ref = fields.Char(size=350, string='Amazon Settlement Ref')

    def check_confirm_bank(self):
        """
        updated done by twinkalc on 12 Oct, 2020,
        update the state of settlement report to validated.
        """
        if self.settlement_ref:
            settlement = self.env['settlement.report.ept'].search([('statement_id','=',self.id)])
            settlement.write({'state':'confirm'})
        return super(AccountBankStatement,self).check_confirm_bank()

    def button_reopen(self):
        """
        Added by twinkalc on 12 Oct, 2020,
        Inherited to update the state of settlement report to imported if bank statement
        is reopened.
        """
        if self.settlement_ref:
            settlement = self.env['settlement.report.ept'].search([('statement_id','=',self.id)])
            settlement.write({'state':'processed'})
        return super(AccountBankStatement, self).button_reopen()