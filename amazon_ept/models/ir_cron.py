from odoo import models, fields, _
from odoo.exceptions import Warning

class IrCron(models.Model):
    _inherit = 'ir.cron'

    amazon_seller_cron_id = fields.Many2one('amazon.seller.ept', string="Cron Scheduler")

    def find_running_schedulers(self, cron_xml_id, seller_id):
        """
        use: This function used for when report is processed then it will check
        if any scheduler is running then the function gives warning and terminate process.
        :param cron_xml_id: string[cron xml id]
        :param seller_id: seller id
        :return:
        @author: Keyur Kanani
        """
        cron_id = self.env.ref('amazon_ept.%s%d' % (cron_xml_id, seller_id), raise_if_not_found=False)
        if cron_id and cron_id.sudo().active:
            res = cron_id.sudo().try_cron_lock()
            if self._context.get('raise_warning') and res and res.get('reason'):
                raise Warning(_("You are not allowed to run this Action. \n" 
                                  "The Scheduler is already running the Process."))
