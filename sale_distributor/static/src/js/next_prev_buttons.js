 odoo.define('sale.distributor', function (require) {
"use strict";

    var core = require('web.core');
    var FormDialog = require('web.view_dialogs');

    var QWeb = core.qweb;
    var _t = core._t;

    var Dialog = require('web.Dialog');
    var ListRenderer = require('web.ListRenderer');
    var FormRenderer = require('web.FormRenderer');

    // Copy Address
    FormRenderer.include({
        events:  {
            'click .invoice_button': '_onClickInvoiceAdd',
            'click .delivery_button': '_onClickDeliveryAdd',
        },

        _onClickInvoiceAdd: function () {
            var mv = this.state.data.partner_invoice_id.data.display_name
            var $ClipboardButton = this.$('.invoice_button');
            var $temp = $("<input>");
            $("body").append($temp);
            $temp.val(mv).select();
            document.execCommand("copy");
            this.do_notify(_t("Copied Invoice Address"));
            $temp.remove();
        },
        _onClickDeliveryAdd: function () {
            var mv = this.state.data.partner_shipping_id.data.display_name
            var $temp = $("<input>");
            $("body").append($temp);
            $temp.val(mv).select();
            document.execCommand("copy");
            this.do_notify(_t("Copied Delivery Address"));
            $temp.remove();
        },

    });
    // Confirm Dialog on Delete Record
    ListRenderer.include({
        _onRemoveIconClick: function (event) {
            var self = this;
            var _super = this._super.bind(this, event);
            event.stopPropagation();
            if ((this.state && this.state.model == 'sale.order.line') && this.state.data[0].context.confirm_delete){
                Dialog.confirm(self, _t("Are you sure you want to delete this record ?"), {
                    confirm_callback: _super,
                });
            } else {
                _super();
            }
        },
    });
    // Next & Previous Functionality
    var FormViewDialog = FormDialog.FormViewDialog.include({
        init: function (parent, options) {
            var res = this._super(parent, options);
            var multi_select = !_.isNumber(options.res_id) && !options.disable_multiple_selection;
            if ((this.res_model == 'sale.order.line') && this.context.is_next_prev){
                var options = this.options;
                var parent = this.getParent();
                var local_array = parent.model.localData[this.parentID]._cache;
                // var array_child_ids = Object.keys(local_array)
                var array_child_ids = _.pluck(parent.renderer.state.data.order_line.data, 'res_id')
                if (this.res_id){
                    // var index = array_child_ids.indexOf(this.res_id.toString())
                    var index = array_child_ids.indexOf(this.res_id)
                }
                var total_length = array_child_ids.length - 1
                var readonly = _.isNumber(options.res_id) && options.readonly;
                if ('buttons' in this) {
                    // Pager
                    if(this.res_id){
                        this.buttons.splice(this.buttons.length, 0, {
                            text: array_child_ids.length,
                            classes: "form_pager",
                        });
                        this.buttons.splice(this.buttons.length, 1, {
                            text: _t("/"),
                            classes: "form_pager",
                        });
                        this.buttons.splice(this.buttons.length, 2, {
                            text: index + 1,
                            classes: "form_pager",
                        });
                    }
                    // Next & Previous Button
                    if(total_length != index && readonly){
                        this.buttons.splice(this.buttons.length, 3, {
                            classes: "fa fa-chevron-right btn-primary button-next-form-dialog",
                            click: function () {
                                this.on_click_form_dialog_next_read();
                            },
                        });
                    }
                    if(index != 0 && readonly){
                        this.buttons.splice(this.buttons.length, 4, {
                            classes: "fa fa-chevron-left btn-primary button-previous-form-dialog",
                            click: function () {
                                this.on_click_form_dialog_previous_read();
                            },
                        });
                    }

                    if(total_length != index && !readonly && this.res_id){
                        this.buttons.splice(this.buttons.length, 5, {
                            text: _t("SAVE & NEXT"),
                            classes: "btn-position btn-primary button-next-form-dialog",
                            click: function () {
                                this.on_click_form_dialog_next_edit();
                            },
                        });
                    }
                    if(index != 0 && !readonly && this.res_id){
                        this.buttons.splice(this.buttons.length, 6, {
                            text: _t("SAVE & PREVIOUS"),
                            classes: "btn-position btn-primary button-previous-form-dialog",
                            click: function () {
                                this.on_click_form_dialog_previous_edit();
                            },
                        });
                    }
                    // Save & Close Button
                    if(!readonly){
                        this.buttons[0].text = (multi_select ? _t("Save & Close") : _t("Save & Close"));
                        this.buttons[0].click = function () {this._save().then(this.close.bind(this));}
                    }
                }
            }
            // return res
        },
        // Next Button Editable Mode
        on_click_form_dialog_next_edit: function(){
            var options = this.options;
            var parent = this.getParent();
            var local_array = parent.model.localData[this.parentID];
            // var array_child_ids = Object.keys(local_array._cache)
            var array_child_ids = _.pluck(parent.renderer.state.data.order_line.data, 'res_id')
            if (this.res_id){
                // var index = array_child_ids.indexOf(this.res_id.toString())
                var index = array_child_ids.indexOf(this.res_id)
            }
            else{
                var index = array_child_ids.length
            }
            if (index === (array_child_ids.length - 1)){
                this.close();
            }else{
                options.res_id = array_child_ids[index +1];
                options.recordID = local_array._cache[options.res_id];
                var old_dialog = _.extend({}, this);
                var new_dialog = new FormDialog.FormViewDialog(parent, options);
                new_dialog.open();
                new_dialog.opened().then(function(){
                    old_dialog._save().then(old_dialog.close());

                })
            }
        },
        // Previous Button Editable Mode
        on_click_form_dialog_previous_edit: function(){
            var options = this.options;
            var parent = this.getParent();
            var local_array = parent.model.localData[this.parentID];
            // var array_child_ids = Object.keys(local_array._cache)
            var array_child_ids = _.pluck(parent.renderer.state.data.order_line.data, 'res_id')
            if (this.res_id){
                // var index = array_child_ids.indexOf(this.res_id.toString())
                var index = array_child_ids.indexOf(this.res_id)
            }
            else{
                var index = array_child_ids.length -1
            }
            if (index === 0){
                this.close();
            }else{
                options.res_id = array_child_ids[index - 1];
                options.recordID = local_array._cache[options.res_id];
                var old_dialog = _.extend({}, this);
                var new_dialog = new FormDialog.FormViewDialog(parent, options);
                new_dialog.open();
                new_dialog.opened().then(function(){
                    old_dialog._save().then(old_dialog.close());
                })
            }
        },
        // Next Button Readonly Mode
        on_click_form_dialog_next_read: function(){
            var options = this.options;
            var parent = this.getParent();
            var local_array = parent.model.localData[this.parentID];
            // var array_child_ids = Object.keys(local_array._cache)
            var array_child_ids = _.pluck(parent.renderer.state.data.order_line.data, 'res_id')
            if (this.res_id){
                // var index = array_child_ids.indexOf(this.res_id.toString())
                var index = array_child_ids.indexOf(this.res_id)
            }
            else{
                var index = array_child_ids.length
            }
            if (index === (array_child_ids.length - 1)){
                this.close();
            }else{
                options.res_id = array_child_ids[index +1];
                options.recordID = local_array._cache[options.res_id];
                var old_dialog = _.extend({}, this);
                var new_dialog = new FormDialog.FormViewDialog(parent, options);
                new_dialog.open();
                new_dialog.opened().then(function(){
                    old_dialog.close();
                })
            }
        },
        // Previous Button Readonly Mode
        on_click_form_dialog_previous_read: function(){
            var options = this.options;
            var parent = this.getParent();
            var local_array = parent.model.localData[this.parentID];
            // var array_child_ids = Object.keys(local_array._cache)
            var array_child_ids = _.pluck(parent.renderer.state.data.order_line.data, 'res_id')
            if (this.res_id){
                // var index = array_child_ids.indexOf(this.res_id.toString())
                var index = array_child_ids.indexOf(this.res_id)
            }
            else{
                var index = array_child_ids.length -1
            }
            if (index === 0){
                this.close();
            }else{
                options.res_id = array_child_ids[index - 1];
                options.recordID = local_array._cache[options.res_id];
                var old_dialog = _.extend({}, this);
                var new_dialog = new FormDialog.FormViewDialog(parent, options);
                new_dialog.open();
                new_dialog.opened().then(function(){
                    old_dialog.close();
                })
            }
        },
    })
})
