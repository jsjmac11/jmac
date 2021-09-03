odoo.define('odoo_multi_channel_sale.update_mapping', function (require) {
"use strict";
var FormView = require('web.FormView');
var Dialog = require('web.Dialog');
 FormView.include({
        on_button_save: function(e) {
            var self = this;
            return self._super.apply(this, arguments).done(function(id){
                var model = self.model;
                var param = {
                        'model': model, 
                        'id': self.datarecord.id ? self.datarecord.id : id
                        };
                self.rpc('/channel/update/mapping', param)
                .done(function(res) {
               
                });
            })
        },
    });

})