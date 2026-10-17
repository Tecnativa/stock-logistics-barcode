# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import base64
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval


class StockBarcodesAction(models.Model):
    """Tiles of the barcode main menu"""

    _name = "stock.barcodes.action"
    _description = "Action of the barcode main menu"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=100)
    action_window_id = fields.Many2one(
        comodel_name="ir.actions.act_window", string="Window Action"
    )
    method = fields.Char(
        help="Method of stock.barcodes.action returning the action to open, "
        "instead of a window action, e.g. action_open_inventory",
    )
    context = fields.Char(help="Context added to the window action")
    count_model = fields.Char(
        help="Model of the records counted on the tile, the one of the window "
        "action by default"
    )
    domain = fields.Char(default="[]", help="Records counted on the tile")
    icon = fields.Char(
        default="barcode",
        help="Name of a Material Symbols icon bundled with Odoo, e.g. local_shipping",
    )
    barcode = fields.Char(help="Reading it from the main menu opens the action")
    barcode_image = fields.Image(compute="_compute_barcode_image")
    count_elements = fields.Integer(compute="_compute_count_elements")

    @api.constrains("barcode")
    def _check_barcode(self):
        for action in self.filtered("barcode"):
            if not re.match(r"^[a-zA-Z0-9-]+$", action.barcode):
                raise ValidationError(
                    self.env._(
                        "The barcode %(barcode)s is not correct. Use numbers, "
                        "letters and dashes, without spaces. E.g. 15753, BC-5789",
                        barcode=action.barcode,
                    )
                )
            duplicated = self.search(
                [("barcode", "=", action.barcode), ("id", "!=", action.id)]
            )
            if duplicated:
                raise ValidationError(
                    self.env._(
                        "The barcode is already used by %(actions)s",
                        actions=", ".join(duplicated.mapped("name")),
                    )
                )

    @api.depends("barcode")
    def _compute_barcode_image(self):
        report = self.env["ir.actions.report"]
        for action in self:
            action.barcode_image = (
                base64.b64encode(report.barcode("Code128", action.barcode))
                if action.barcode
                else False
            )

    @api.depends("domain", "count_model", "action_window_id")
    def _compute_count_elements(self):
        for action in self:
            model = action.count_model or action.action_window_id.res_model
            if not model or not action.domain or action.domain == "[]":
                action.count_elements = 0
                continue
            domain = Domain(safe_eval(action.domain, {"uid": self.env.uid}))
            action.count_elements = self.env[model].search_count(list(domain))

    def open_action(self):
        self.ensure_one()
        if self.method:
            return getattr(self, self.method)()
        action = self.action_window_id._get_action_dict()
        context = dict(safe_eval(action.get("context") or "{}", {"uid": self.env.uid}))
        if self.context:
            context.update(safe_eval(self.context, {"uid": self.env.uid}))
        action["context"] = context
        return action

    def action_open_inventory(self):
        """Count the stock of the main warehouse"""
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        return warehouse.lot_stock_id.action_capture_open()

    @api.model
    def get_main_menu(self):
        """Tiles of the main menu"""
        return [
            {
                "id": action.id,
                "name": action.name,
                "icon": action.icon,
                "count": action.count_elements,
                "barcode": action.barcode,
            }
            for action in self.search([])
        ]

    @api.model
    def open_by_barcode(self, barcode):
        """Action of the tile with the barcode read on the main menu"""
        action = self.search([("barcode", "=", barcode)], limit=1)
        return action.open_action() if action else False

    def print_barcodes(self):
        return self.env.ref(
            "stock_barcodes.action_report_barcode_actions"
        ).report_action(self, config=False)
