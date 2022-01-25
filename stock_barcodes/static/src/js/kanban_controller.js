/* Copyright 2018-2019 Sergio Teruel <sergio.teruel@tecnativa.com>.
 * License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl). */

odoo.define("stock_barcodes.KanbanController", function(require) {
    "use strict";

    var core = require("web.core");
    var KanbanController = require("web.KanbanController");

    KanbanController.include({
        _barcodeModels: [
            "wiz.stock.barcodes.read",
            "wiz.stock.barcodes.read.picking",
            "wiz.stock.barcodes.read.inventory",
            "stock.picking.type",
            "stock.picking",
        ],
        _is_allowedModel: function(){
            console.log(this._barcodeModels.indexOf(this.modelName));
            console.log(this.modelName);
            return this._barcodeModels.indexOf(this.modelName) !== -1
        },
        init: function() {
            this._super.apply(this, arguments);
            if (this._is_allowedModel()) {
                console.log("INIT");
                this.kanban_action_button_selected = 0;
            }
        },
        on_detach_callback: function() {
            this._super.apply(this, arguments);
            if (this._is_allowedModel()) {
                console.log("on_detach_callback");
                core.bus.off("keydown", this, this._onCoreKeyDown);
                core.bus.off("keyup", this, this._onCoreKeyUp);
            }
        },
        on_attach_callback: function() {
            this._super.apply(this, arguments);
            if (this._is_allowedModel()) {
                console.log("on_attach_callback");
                core.bus.on("keydown", this, this._onCoreKeyDown);
                core.bus.on("keyup", this, this._onCoreKeyUp);
                console.log(this.$(".oe_kanban_action_button"));
                this.kanban_action_buttons = this.$(".oe_kanban_action_button");
                this.kanban_action_buttons[0].focus();
//                _.defer(() => this.kanban_action_buttons[0].focus());
                console.log($(":focus"));
            }
        },

        _onCoreKeyDown: function(ev) {
            if (this._is_allowedModel()) {
                // TODO: Remove
                //                alert(ev.keyCode);
                console.log("KeyDown: " + ev.keyCode);
                // F9 key
                if (ev.keyCode === 120) {
                    this.$("button[name='action_clean_values']").click();
                }
                if (ev.keyCode === 123) {
                    this.$("button[name='open_actions']").click();
                }
                console.log($(":focus"));
                // Search kanban buttons to navigate
                if (ev.keyCode === $.ui.keyCode.UP || ev.keyCode === 84) {
                    console.log("UP");
                    --this.kanban_action_button_selected;
                    if (this.kanban_action_button_selected < 0) {
                        this.kanban_action_button_selected = this.kanban_action_buttons.length - 1;
                    }
                    this.kanban_action_buttons[this.kanban_action_button_selected].focus();
                }
                if (ev.keyCode === $.ui.keyCode.DOWN || ev.keyCode === 71) {
                    console.log("DOWN");
                    ++this.kanban_action_button_selected;
                    if (this.kanban_action_button_selected >= this.kanban_action_buttons.length) {
                        this.kanban_action_button_selected = 0;
                    }
//                    debugger;
                    this.kanban_action_buttons[this.kanban_action_button_selected].focus();
                }
            }
        },
        _onCoreKeyUp: function(ev) {
            if (this._is_allowedModel()) {
                // TODO: Remove
                //                console.log('KeyUp: ' + ev.keyCode);
                //                alert(ev.keyCode);
                // Intro key
                if (ev.keyCode === $.ui.keyCode.ENTER) {
                    this.$(":focus").click();
                    this.$("button[name='action_confirm']:visible").click();
                }
            }
        },
    });
});
