odoo.define("stock_barcodes.KanbanRenderer", function(require) {
    "use strict";

    var core = require("web.core");
    var KanbanRenderer = require("web.KanbanRenderer");

    KanbanRenderer.include({
        _barcodeModels: [
            "stock.picking.type",
            "stock.picking",
            "stock.barcodes.action",
            "wiz.stock.barcodes.read",
            "wiz.stock.barcodes.read.picking",
            "wiz.stock.barcodes.read.inventory",
            "wiz.stock.barcodes.read.todo"
        ],
        _is_allowedModel: function(){
            return this._barcodeModels.indexOf(this.state.model) !== -1
        },
        init: function() {
            this._super.apply(this, arguments);
            if (this._is_allowedModel()) {
                this.kanban_action_button_selected = 0;
            }
        },
        on_attach_callback: function() {
            this._super.apply(this, arguments);
            if (this._is_allowedModel()) {
                this.kanban_action_buttons = this.$(".oe_kanban_action_button:visible");
                console.log("Kanban Rendered: " + this.kanban_action_buttons);
                if (this.kanban_action_buttons.length){
                    this.kanban_action_buttons[0].focus();
                }
            }
        },
        _onRecordKeyDown: function(ev) {
            if (this._is_allowedModel()) {
                console.log("PEPE Kanban rendered");
                // F9 key
                if (ev.keyCode === 120) {
                    this.$("button[name='action_clean_values']").click();
                }
                if (ev.keyCode === 123) {
                    this.$("button[name='open_actions']").click();
                }
                // Search kanban buttons to navigate
                if (ev.keyCode === $.ui.keyCode.UP || ev.keyCode === 117|| ev.keyCode === 70) {
                    ev.preventDefault();
                    --this.kanban_action_button_selected;
                    if (this.kanban_action_button_selected < 0) {
                        this.kanban_action_button_selected = this.kanban_action_buttons.length - 1;
                    }
                    this.kanban_action_buttons[this.kanban_action_button_selected].focus();
                    ev.stopPropagation();
                }
                if (ev.keyCode === $.ui.keyCode.DOWN || ev.keyCode === 118|| ev.keyCode === 71) {
                    ev.preventDefault();
                    ++this.kanban_action_button_selected;
                    if (this.kanban_action_button_selected >= this.kanban_action_buttons.length) {
                        this.kanban_action_button_selected = 0;
                    }
                    this.kanban_action_buttons[this.kanban_action_button_selected].focus();
                    ev.stopPropagation();
                }
                if (ev.keyCode === $.ui.keyCode.ENTER || ev.keyCode === 13) {
                    this.kanban_action_buttons[this.kanban_action_button_selected].click();
                };
            } else {
                this._super.apply(this, arguments);
            };
        },
    });
});
