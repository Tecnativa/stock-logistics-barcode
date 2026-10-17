# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models
from odoo.exceptions import UserError
from odoo.tools import is_html_empty


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ("stock.picking", "stock.capture.document")

    def _capture_product(
        self,
        product,
        quantity,
        uom=None,
        lot=None,
        location=None,
        package=None,
        owner=None,
        result_package=None,
        merge=True,
        location_dest=None,
    ):
        """Capture a quantity of a product on the transfer.

        It is spread over the moves of the product, and a product without moves
        gets a new one, as when a line is added to the transfer.

        :return: the picked move lines holding the captured quantity
        """
        self.ensure_one()
        if self.state in ("done", "cancel"):
            raise UserError(
                self.env._("Quantities can only be captured on transfers to do.")
            )
        uom = uom or product.uom_id
        characteristics = {
            "lot": lot,
            "location": location,
            "package": package,
            "owner": owner,
            "result_package": result_package,
            "location_dest": location_dest,
        }
        moves = self.move_ids.filtered(
            lambda move: (
                move.product_id == product
                and move.state not in ("draft", "done", "cancel")
            )
        )
        if not moves:
            return self._capture_new_product(product, quantity, uom, characteristics)
        return moves._capture_spread(quantity, uom=uom, merge=merge, **characteristics)

    def _capture_new_product(self, product, quantity, uom, characteristics):
        """Capture a product without moves in the transfer.

        Odoo links the new line to a move of the transfer or creates one.
        """
        self.ensure_one()
        location = characteristics["location"] or self.location_id
        location_dest = characteristics.get("location_dest") or self.location_dest_id
        result_package = self.picking_type_id._capture_result_package(
            characteristics["result_package"], location_dest
        )
        return self.env["stock.move.line"].create(
            {
                "picking_id": self.id,
                "product_id": product.id,
                "uom_id": uom.id,
                "quantity": quantity,
                "location_id": location.id,
                "location_dest_id": location_dest.id,
                "lot_id": (characteristics["lot"] or self.env["stock.lot"]).id,
                "package_id": (
                    characteristics["package"] or self.env["stock.package"]
                ).id,
                "owner_id": (characteristics["owner"] or self.env["res.partner"]).id,
                "result_package_id": (result_package or self.env["stock.package"]).id,
                "picked": True,
            }
        )

    # Capture document

    def _capture_profile(self):
        return self.picking_type_id._capture_profile()

    def _capture_kind(self):
        return self.picking_type_code or "internal"

    def _capture_moves(self):
        return self.move_ids

    def _capture_source_locations(self):
        return self.location_id

    def _capture_dest_locations(self):
        return self.location_dest_id

    def _capture_info(self):
        return {
            "partner_id": self.partner_id,
            "note": False if is_html_empty(self.note) else self.note,
            "company_id": self.company_id,
        }

    def _capture_apply_new_product(self, session):
        if not session.profile_id.allow_not_demanded_product:
            return False
        values = session._capture_characteristics()
        return self._capture_product(
            session.product_id,
            values["quantity"],
            uom=values["uom"],
            lot=values["lot"],
            location=values["location"],
            package=values["package"],
            owner=values["owner"],
            result_package=values["result_package"],
            location_dest=values["location_dest"],
        )

    def _capture_can_create_lot(self, product):
        return (
            self.picking_type_code == "incoming"
            and self.picking_type_id.use_create_lots
        )

    def _capture_can_validate(self):
        return self.state not in ("draft", "done", "cancel") or (
            self.state == "draft" and bool(self.move_ids)
        )

    def _capture_validate_context(self, session):
        """Context to validate these transfers from a capture screen. When the
        user decided on the screen what to do with every operation not fully
        captured, Odoo doesn't ask again"""
        context = {"capture_session_id": session.id}
        short_moves = self.move_ids.filtered(
            lambda move: (
                move.state not in ("done", "cancel")
                and move.uom_id.compare(move.captured_quantity, move.product_uom_qty)
                < 0
            )
        )
        if (
            self.move_line_ids.filtered("picked")
            and short_moves
            and all(m.capture_backorder_action != "pending" for m in short_moves)
        ):
            context["skip_backorder"] = True
            context["picking_ids_not_to_backorder"] = self.filtered(
                lambda picking: all(
                    m.capture_backorder_action == "skip_backorder"
                    for m in short_moves.filtered(lambda m: m.picking_id == picking)
                )
            ).ids
        return context

    def _capture_put_in_pack(self):
        """Put in pack the transfers whose profile asks for it, when nothing
        is packed"""
        to_pack = self.filtered(
            lambda picking: (
                picking.picking_type_id._capture_profile().auto_put_in_pack
                and picking.move_line_ids
                and not picking.move_line_ids.result_package_id
            )
        )
        if to_pack:
            to_pack.action_put_in_pack()

    def _capture_validate(self, session):
        self._capture_put_in_pack()
        return self.with_context(
            **self._capture_validate_context(session)
        ).button_validate()

    def button_validate(self):
        """Back from a capture screen once validated, also when Odoo asked
        first what to do with the backorders"""
        result = super().button_validate()
        session = self.env["stock.capture.session"]._capture_from_context()
        if session and result is True and all(p.state == "done" for p in self):
            return session._capture_after_validate()
        return result
