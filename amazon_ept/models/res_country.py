from odoo import models, fields


class res_country(models.Model):
    _inherit = "res.country"

    amazon_marketplace_code = fields.Char('Amazon Marketplace Code', size=10, default=False)
    vcs_tax_code = fields.Char('VCS Tax Code')

    def init(self):
        # Here we can set have_marketplace=true for country that have Amazon marketplace
        self._cr.execute("""update res_country set amazon_marketplace_code=code 
                    where code in ('CA','US','DE','ES','FR','IN','IT','JP','MX','BR','AU','TR',
                    'SG','AE','EG','SA','TR','CZ', 'SE')""")
        self._cr.execute("""update res_country set amazon_marketplace_code = 'UK' 
                    where code='GB'""")
        self._cr.execute("""update res_country set vcs_tax_code='GERMANY' where code='DE'""")
        self._cr.execute("""update res_country set vcs_tax_code='SPAIN' where code='ES'""")
        self._cr.execute("""update res_country set vcs_tax_code='FRANCE' where code='FR'""")
        self._cr.execute("""update res_country set vcs_tax_code='UNITED KINGDOM' where code='GB'""")
        self._cr.execute("""update res_country set vcs_tax_code='ITALY' where code='IT'""")
        self._cr.execute("""update res_country set vcs_tax_code='IRELAND' where code='IE'""")
        self._cr.execute("""update res_country set vcs_tax_code='POLAND' where code='PL'""")
        self._cr.execute("""update res_country set vcs_tax_code='BELGIUM' where code='BE'""")
        self._cr.execute("""update res_country set vcs_tax_code='CZECH REPUBLIC' where code='CZ'""")

        # United Kingdom Amazon marketplace code is UK and Country Code for United Kingdom is GB.
