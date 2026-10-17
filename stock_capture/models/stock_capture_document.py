# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models


class StockCaptureDocument(models.AbstractModel):
    """Document whose quantities are captured: a transfer, an operation type, a
    location being counted, a batch, a manufacturing order...

    The capture screens work on a document through these methods, so a new
    kind of document only implements them.
    """

    _name = "stock.capture.document"
    _description = "Document of a capture screen"

    # Document API

    def _capture_profile(self):
        """Profile of the screens working on the document"""
        return self.env.ref("stock_capture.stock_capture_profile_operation")

    def _capture_kind(self):
        """``incoming``, ``outgoing``, ``internal`` or ``inventory``: what the
        screen does with the stock"""
        return "internal"

    def _capture_moves(self):
        """Operations of the document whose quantities are captured"""
        return self.env["stock.move"]

    def _capture_source_locations(self):
        """Locations the stock is taken from"""
        return self.env["stock.location"]

    def _capture_dest_locations(self):
        """Locations the stock goes to"""
        return self.env["stock.location"]

    def _capture_defaults(self):
        """Values of the screen when opened on the document"""
        return {
            "location_id": self._capture_source_locations()[:1],
            "location_dest_id": self._capture_dest_locations()[:1],
        }

    def _capture_info(self):
        """Information of the document shown on the screen"""
        return {
            "partner_id": self.env["res.partner"],
            "note": False,
            "company_id": self.env.company,
        }

    def _capture_can_validate(self):
        return False

    def _capture_can_create_lot(self, product):
        """Whether a lot name read for the product creates the lot"""
        return False

    def _capture_done_action(self, session):
        """Action once the document is validated from a screen, ``False`` for
        the default one of the screen"""
        return False

    def _capture_validate(self, session):
        """Validate the document from a screen.

        :return: the action to execute
        """
        return False

    def _capture_document_for(self, session):
        """Document the reading of the session applies to, e.g. the transfer
        found from the product read on an operation type. Empty when there is
        none."""
        return self

    def _capture_apply(self, session):
        """Apply the reading of the session to the document.

        The session messages explain why a reading is not applied.

        :return: the captured records (move lines, quants...), or ``False``
        """
        return self._capture_apply_moves(session)

    def _capture_check(self, session):
        """Whether the reading can be applied, setting the session message
        when not"""
        return self._capture_check_moves(session)

    def action_capture_open(self, profile=None):
        """Open the capture screen of the document"""
        self.ensure_one()
        session = self.env["stock.capture.session"]._capture_open(self, profile)
        return session._capture_action()

    # Barcodes

    def _capture_parse_barcode(self, barcode):
        """Interpret a barcode as the values it reads on these documents.

        :return: dict of values with the keys of the session fields
            (``product_id``, ``uom_id``, ``lot_id``, ``location_id``,
            ``result_package_id``...), plus ``lot_name``, ``quantity`` or
            ``package_content`` (a package read in the source location, to
            capture with all its content). Empty when nothing matches.
        """
        nomenclature = self.env.company.nomenclature_id
        parsed = nomenclature.parse_barcode(barcode) if nomenclature else False
        if isinstance(parsed, list):
            values = {}
            # The batch or lot number (AI 10) wins over the serial number (21)
            for item in sorted(parsed, key=lambda item: item.get("ai") == "10"):
                values.update(self._capture_gs1_values(item))
            if values:
                return values
        elif parsed and parsed.get("type") == "weight":
            product = self._capture_search_product(parsed["base_code"])
            if product:
                return {
                    "product_id": product,
                    "quantity": parsed["value"],
                    "uom_id": self.env.ref("uom.product_uom_kgm"),
                }
        code = parsed.get("code", barcode) if isinstance(parsed, dict) else barcode
        return self._capture_search_barcode(code)

    def _capture_is_gs1(self, barcode):
        nomenclature = self.env.company.nomenclature_id
        if not nomenclature or not nomenclature.is_gs1_nomenclature:
            return False
        return isinstance(nomenclature.parse_barcode(barcode), list)

    def _capture_gs1_values(self, item):
        """Values read by a GS1 element"""
        value = item.get("value")
        if item["type"] == "product":
            product = self._capture_search_product(value)
            return {"product_id": product} if product else {}
        if item["type"] == "lot":
            return {"lot_name": value}
        if item["type"] == "quantity":
            values = {"quantity": value}
            if item["rule"].associated_uom_id:
                values["uom_id"] = item["rule"].associated_uom_id
            return values
        if item["type"] in ("package", "location"):
            return self._capture_search_barcode(item["string_value"])
        if item["type"] == "location_dest":
            location = self._capture_search_location(item["string_value"])
            return {"location_dest_id": location} if location else {}
        if item["type"] in ("expiration_date", "use_date"):
            return {item["type"]: value}
        return {}

    def _capture_search_product(self, code):
        codes = [code]
        # GTIN-14 of a product with an EAN-13 barcode
        if len(code) == 14 and code.startswith("0"):
            codes.append(code[1:])
        return self.env["product.product"].search([("barcode", "in", codes)], limit=1)

    def _capture_search_packaging(self, code):
        return self.env["product.uom"].search([("barcode", "=", code)], limit=1)

    def _capture_search_location(self, code):
        return self.env["stock.location"].search(
            [
                ("barcode", "=", code),
                ("company_id", "in", [False, *self.env.companies.ids]),
            ],
            limit=1,
        )

    def _capture_search_package(self, code):
        return self.env["stock.package"].search([("name", "=", code)], limit=1)

    def _capture_in_source_location(self, location):
        return any(
            location._child_of(source) for source in self._capture_source_locations()
        )

    def _capture_search_barcode(self, code):
        """Values read by a barcode of a record"""
        product = self._capture_search_product(code)
        if product:
            return {"product_id": product}
        packaging = self._capture_search_packaging(code)
        if packaging:
            return {
                "product_id": packaging.product_id,
                "packaging_id": packaging,
                "uom_id": packaging.uom_id,
                "quantity": 1.0,
            }
        lot = self.env["stock.lot"].search(
            [
                ("name", "=", code),
                ("product_id", "in", self._capture_moves().product_id.ids),
            ],
            limit=1,
        )
        if lot:
            return {"lot_id": lot, "product_id": lot.product_id}
        package = self._capture_search_package(code)
        if package:
            if package.quant_ids.filtered(
                lambda quant: self._capture_in_source_location(quant.location_id)
            ):
                return {"package_content": package}
            return {"result_package_id": package}
        location = self.env["stock.location"].search(
            [
                ("barcode", "=", code),
                ("id", "child_of", self._capture_source_locations().ids),
            ],
            limit=1,
        )
        if location:
            return {"location_id": location}
        return {}

    # Documents with operations

    def _capture_candidate_moves(self, session):
        """Operations of the document the product read can be captured on"""
        states = ["assigned", "partially_available"]
        if session.profile_id.capture_unreserved or session.capture_kind == "incoming":
            states += ["confirmed", "waiting"]
        if session.profile_id.guided and session.card_move_ids:
            moves = session.card_move_ids
        else:
            moves = self._capture_moves()
        return moves.filtered(
            lambda move: move.product_id == session.product_id and move.state in states
        )

    def _capture_check_moves(self, session):
        product = session.product_id
        moves = self._capture_candidate_moves(session)
        if not moves and not session.profile_id.allow_not_demanded_product:
            return session._capture_fail(self.env._("Product not demanded"))
        if product.tracking == "serial" and (session.lot_id or session.lot_name):
            serial_lines = self._capture_moves().move_line_ids.filtered(
                lambda ml: (
                    ml.picked
                    and (
                        (session.lot_id and ml.lot_id == session.lot_id)
                        or (session.lot_name and ml.lot_name == session.lot_name)
                    )
                )
            )
            if serial_lines:
                session.lot_id = session.lot_name = False
                return session._capture_fail(self.env._("S/N Already in picking"))
        if session.env.context.get("capture_force"):
            return True
        uom = session.uom_id or product.uom_id
        quantity = uom._compute_quantity(session.quantity, product.uom_id)
        if (
            session.capture_kind != "incoming"
            and not session.profile_id.allow_negative_quant
            and session.location_id.usage == "internal"
            and product.uom_id.compare(quantity, session._capture_available()) > 0
        ):
            return session._capture_fail(
                self.env._("Quantities not available in location")
            )
        if moves and not session.profile_id.allow_over_demand:
            pending = sum(
                move.uom_id._compute_quantity(
                    move.product_uom_qty - move.captured_quantity, product.uom_id
                )
                for move in moves
            )
            if product.uom_id.compare(quantity, pending) > 0:
                session.force_visible = True
                session._capture_focus("quantity")
                return session._capture_fail(
                    self.env._("Quantities scanned are higher than necessary.")
                )
        return True

    def _capture_apply_new_product(self, session):
        """Capture a product without operations in the document"""
        return False

    def _capture_apply_moves(self, session):
        moves = self._capture_candidate_moves(session)
        if not moves:
            return self._capture_apply_new_product(session)
        values = session._capture_characteristics()
        uom = values.pop("uom")
        quantity = values.pop("quantity")
        if session.profile_id.replace_quantity:
            lines = moves.move_line_ids.filtered(
                lambda ml: (
                    ml.picked
                    and ml._capture_matches(
                        {
                            "lot_id": values["lot"],
                            "location_id": values["location"],
                            "package_id": values["package"],
                            "owner_id": values["owner"],
                        }
                    )
                )
            )[:1]
            if lines:
                return lines._capture_set_quantity(
                    uom._compute_quantity(quantity, lines.uom_id, round=False)
                )
        return moves._capture_spread(quantity, uom=uom, **values)
