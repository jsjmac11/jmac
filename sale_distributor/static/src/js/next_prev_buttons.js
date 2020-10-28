odoo.define('sale.distributor', function (require) {
"use strict";

    var core = require('web.core');
    var FormDialog = require('web.view_dialogs');

    var QWeb = core.qweb;
    var _t = core._t;

    var FormViewDialog = FormDialog.FormViewDialog.include({

        init: function (parent, options) {
            var res = this._super(parent, options);
            if ((this.res_model == 'sale.order.line') && this.context.is_next_prev){ 
                if ('buttons' in this) {
                    this.buttons.splice(this.buttons.length, 0, {
                        text: _t("Next"),
                        classes: "btn-primary button-next-form-dialog",
                        click: function () {
                            this.on_click_form_dialog_next();
                        },
                    }, {
                        text: _t("Previous"),
                        classes: "btn-primary button-previous-form-dialog",
                        click: function () {
                            this.on_click_form_dialog_previous();
                        },
                    });
                }
            }
            return res
        },
        on_click_form_dialog_next: function(){
            var options = this.options;
            var parent = this.getParent();
            var local_array = parent.model.localData[this.parentID];
            var array_child_ids = local_array.res_ids;
            var index = array_child_ids.indexOf(this.res_id)

            if (index === (array_child_ids.length - 1)){
                this.close();
            }else{
                options.res_id = array_child_ids[index +1];
                options.recordID = local_array._cache[options.res_id];
                this.close();
                new FormDialog.FormViewDialog(parent, options).open();
            }

        },

        on_click_form_dialog_previous: function(){
            var options = this.options;
            var parent = this.getParent();
            var local_array = parent.model.localData[this.parentID];
            var array_child_ids = local_array.res_ids;
            var index = array_child_ids.indexOf(this.res_id)

            if (index === 0){
                this.close();
            }else{
                options.res_id = array_child_ids[index - 1];
                options.recordID = local_array._cache[options.res_id];
                this.close();
                new FormDialog.FormViewDialog(parent, options).open();
            }
        },
    })
})
