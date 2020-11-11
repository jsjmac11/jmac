odoo.define('sale.distributor', function (require) {
"use strict";

    var core = require('web.core');
    var FormDialog = require('web.view_dialogs');

    var QWeb = core.qweb;
    var _t = core._t;

    var Dialog = require('web.Dialog');
    var ListRenderer = require('web.ListRenderer');

    // Confirm Dialog on Delete Record
    ListRenderer.include({
        _onRemoveIconClick: function (event) {
            var self = this;
            var _super = this._super.bind(this, event);
            event.stopPropagation();
            if (this.state && this.state.model == 'sale.order.line'){
                Dialog.confirm(self, _t("Are you sure you want to delete this record ?"), {
                    confirm_callback: _super,
                });
            } else {
                _super();
            }
        },
    });

    var FormViewDialog = FormDialog.FormViewDialog.include({
        init: function (parent, options) {
            var res = this._super(parent, options);
            if ((this.res_model == 'sale.order.line') && this.context.is_next_prev){
                var options = this.options;
                var parent = this.getParent();
                var local_array = parent.model.localData[this.parentID]._cache;
                var array_child_ids = Object.keys(local_array)
                if (this.res_id){
                    var index = array_child_ids.indexOf(this.res_id.toString())
                }
                var total_length = array_child_ids.length - 1
                if ('buttons' in this) {
                    if(total_length != index){
                        this.buttons.splice(this.buttons.length, 0, {
                            classes: "fa fa-chevron-right btn-primary button-next-form-dialog",
                            click: function () {
                                this.on_click_form_dialog_next();
                            },
                        });
                    }
                    if(index != 0){
                        this.buttons.splice(this.buttons.length, 1, {
                            classes: "fa fa-chevron-left btn-primary button-previous-form-dialog",
                            click: function () {
                                this.on_click_form_dialog_previous();
                            },
                        });
                    }
                    if(this.res_id){
                        this.buttons.splice(this.buttons.length, 3, {
                            text: array_child_ids.length,
                            classes: "form_pager",
                        });
                        this.buttons.splice(this.buttons.length, 4, {
                            text: _t("/"),
                            classes: "form_pager",
                        });
                        this.buttons.splice(this.buttons.length, 5, {
                            text: index + 1,
                            classes: "form_pager",
                        });
                    }
                }
            }
            return res
        },
        on_click_form_dialog_next: function(){
            var options = this.options;
            var parent = this.getParent();
            var local_array = parent.model.localData[this.parentID];
            var array_child_ids = Object.keys(local_array._cache)
            if (this.res_id){
                var index = array_child_ids.indexOf(this.res_id.toString())
            }
            else{
                var index = array_child_ids.length
            }
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
            var array_child_ids = Object.keys(local_array._cache)
            if (this.res_id){
                var index = array_child_ids.indexOf(this.res_id.toString())
            }
            else{
                var index = array_child_ids.length -1
            }
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
