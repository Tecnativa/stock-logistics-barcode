/* Copyright 2018-2019 Sergio Teruel <sergio.teruel@tecnativa.com>.
 * Copyright 2022 Tecnativa - Alexandre D. Díaz
 * License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl). */

odoo.define("stock_barcodes.BasicController", function(require) {
    "use strict";

    const BasicController = require("web.BasicController");
    const WebClientObj = require("web.web_client");
    const BarcodesModelsMixin = require("stock_barcodes.BarcodesModelsMixin");


    BasicController.include(BarcodesModelsMixin);
    BasicController.include({
        /**
         * @override
         */
        init: function() {
            this._super.apply(this, arguments);
            this._is_valid_barcode_model = this._isAllowedBarcodeModel(this.initialState.model);
            if (this._is_valid_barcode_model) {
                this._keybind_selectable_index = 0;
                this._keybind_selectable_items = [];
                this._is_browser_chrome = WebClientObj.BrowserDetection.isBrowserChrome();
                const state_id = this.initialState.data.id;
                if (state_id) {
                    this._channel_barcode_read = `stock_barcodes_read-${this.initialState.data.id}`;
                    this._channel_barcode_sound = `stock_barcodes_sound-${this.initialState.data.id}`;

                    if (this.call("bus_service", "isMasterTab")) {
                        this.call("bus_service", "addChannel", this._channel_barcode_read);
                        this.call("bus_service", "addChannel", this._channel_barcode_sound);
                    }
                }
            }
        },

        /**
         * @override
         */
        destroy: function() {
            this._super.apply(this, arguments);
            if (this._is_valid_barcode_model) {
                this.$sound_ok.remove();
                this.$sound_ko.remove();
            }
        },

        /**
         * @override
         */
        on_detach_callback: function() {
            this._super.apply(this, arguments);
            if (this._is_valid_barcode_model) {
                $(document).off("keydown", this._onDocumentKeyDown);
                $(document).off("keyup", this._onDocumentKeyUp);
                this.call(
                    "bus_service",
                    "off",
                    "notification",
                    this,
                    this.bus_notification
                );
            }
        },

        /**
         * @override
         */
        on_attach_callback: function() {
            this._super.apply(this, arguments);
            if (this._is_valid_barcode_model) {
                this._appendBarcodesSounds();
                $(document).on("keydown", {controller: this}, this._onDocumentKeyDown);
                $(document).on("keyup", {controller: this}, this._onDocumentKeyUp);
                this.call(
                    "bus_service",
                    "on",
                    "notification",
                    this,
                    this.onBusNotificationBarcode
                );
                this._keybind_selectable_items = this.$(".oe_kanban_action_button:visible");
                if (this._keybind_selectable_items.length){
                    this._keybind_selectable_items[0].focus();
                }
            }
        },

        /**
         * Longpolling messages
         *
         * @param {Array} notifications
         */
        onBusNotificationBarcode: function(notifications) {
            for (const notif in notifications) {
                const [channel, message] = notification;
                if (channel === "stock_barcodes_read-" + self.initialState.data.id) {
                    if (message.action === "focus") {
                        setTimeout(() => {
                            self.$(`[name=${message.field_name}] input`).select();
                        }, 300);
                        //                        Self.$(`[name=${message.field_name}] input`).select();
                    }
                } else if (
                    channel ===
                    "stock_barcodes_sound-" + self.initialState.data.id
                ) {
                    if (message.sound === "ok") {
                        self.$sound_ok[0].play();
                    } else if (message.sound === "ko") {
                        self.$sound_ko[0].play();
                    }
                }
            }
        },

        /**
         * Helper to toggle access keys panel visibility
         *
         * @param {Boolean} status
         */
        _toggleAccessKeys: function (status) {
            if (status) {
                WebClientObj._addAccessKeyOverlays();
            } else {
                WebClientObj._hideAccessKeyOverlay();
            };
            WebClientObj._areAccessKeyVisible = status;
        },

        /**
         * Append the audio elements to play the sounds.
         * This is here because only must exists one controller at time
         *
         * @private
         */
        _appendBarcodesSounds: function () {
            this.$sound_ok = $('<audio>',{
                src: '/stock_barcodes/static/src/sounds/bell.wav',
                preload: 'auto'
            });
            this.$sound_ok.appendTo("body");
            this.$sound_ko = $('<audio>',{
                src: '/stock_barcodes/static/src/sounds/error.wav',
                preload: 'auto'
            });
            this.$sound_ko.appendTo("body");
        },

        /**
         * Dedicated keyboard handle for chrome browser
         * @param {KeyboardEvent} ev
         */
        _onPushKeyForChrome: function(ev) {
            let prefixkey = "";
            if (ev.shift) {
                prefixkey += "shift+";
            }
            const elementWithAccessKey = document.querySelector(`[accesskey="${prefixkey}${ev.key.toLowerCase()}"], [accesskey="${prefixkey}${ev.key.toUpperCase()}"]`);
            if (elementWithAccessKey) {
                ev.preventDefault();
                elementWithAccessKey.focus();
                elementWithAccessKey.click();
            };
        },

        /**
         * @private
         * @param {KeyboardEvent} ev
         */
        _onDocumentKeyDown: function(ev) {
            var self = (ev.data && ev.data.controller) || this;
            if (self._is_valid_barcode_model) {
                // ACCESS KEY PANEL MANAGEMENT
                const alt = ev.altKey || ev.key === "Alt",
                    newEvent = _.extend({}, ev),
                    shift = ev.shiftKey || ev.key === "Shift";
                if (ev.keyCode === 113) { // F2
                    self._toggleAccessKeys(!WebClientObj._areAccessKeyVisible)
                } else if (WebClientObj._areAccessKeyVisible && !shift && !alt) {
                    if (self._is_browser_chrome) {
                        self._onPushKeyForChrome(ev);
                    } else {
                        newEvent.altKey = true;
                        newEvent.shiftKey = true;
                        WebClientObj._onKeyDown(newEvent);
                    };
                };

                // VIEW ACTIONS MANAGEMENT
                if (ev.keyCode === 120) { // F9
                    self.$("button[name='action_clean_values']").click();
                } else if (ev.keyCode === 123) {
                    self.$("button[name='open_actions']").click();
                } else if (ev.keyCode === $.ui.keyCode.UP || ev.keyCode === 78) {
                    // Search kanban buttons to navigate
                    console.log("UP: "+ev.keyCode);
                    ev.preventDefault();
                    --self._keybind_selectable_index;
                    if (self._keybind_selectable_index < 0) {
                        self._keybind_selectable_index = self._keybind_selectable_items.length - 1;
                    }
                    self._keybind_selectable_items[self._keybind_selectable_index].focus();
//                    ev.stopPropagation();
                } else if (ev.keyCode === $.ui.keyCode.DOWN || ev.keyCode === 77) {
                    console.log("DOWN: "+ev.keyCode);
                    ev.preventDefault();
                    ++self._keybind_selectable_index;
                    if (self._keybind_selectable_index >= self._keybind_selectable_items.length) {
                        self._keybind_selectable_index = 0;
                    }
                    self._keybind_selectable_items[self._keybind_selectable_index].focus();
//                    ev.stopPropagation();
                } else if (ev.keyCode === $.ui.keyCode.ENTER || ev.keyCode === 13) {
                    console.log(ev.keyCode);
                    self._keybind_selectable_items[self._keybind_selectable_index].click();
                };

            }
        },

        /**
         * @private
         * @param {KeyboardEvent} ev
         */
        _onDocumentKeyUp: function(ev) {
            if (this._is_valid_barcode_model) {
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
