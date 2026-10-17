# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class StockPickingType(models.Model):
    _name = "stock.picking.type"
    _inherit = ("stock.picking.type", "stock.capture.document")

    capture_profile_id = fields.Many2one(
        comodel_name="stock.capture.profile",
        help="Behaviour of the capture screens (barcodes...) on this operation "
        "type and its transfers.",
    )
    capture_new_picking_profile_id = fields.Many2one(
        comodel_name="stock.capture.profile",
        string="Capture Profile for New Transfers",
        help="Profile of the capture screen opened on a new unplanned transfer "
        "of this operation type.",
    )

    def _capture_result_package(self, result_package, location_dest):
        """Destination package of a capture going to the given location.

        :param result_package: the package given by the user, ``None`` when
            none was given and an empty recordset to capture without package
        :return: the package to capture into, with the same meaning
        """
        return result_package

    # Capture document: the transfers of the operation type, the one to work
    # on is found from the product read

    def _capture_profile(self):
        """The profile of the operation type or the default one of its kind"""
        if self.capture_profile_id:
            return self.capture_profile_id
        xmlid = {
            "incoming": "stock_capture.stock_capture_profile_receipt",
            "outgoing": "stock_capture.stock_capture_profile_delivery",
            "internal": "stock_capture.stock_capture_profile_internal",
        }.get(self.code)
        profile = self.env.ref(xmlid, raise_if_not_found=False) if xmlid else None
        return profile or super()._capture_profile()

    def _capture_kind(self):
        return self.code or "internal"

    def _capture_source_locations(self):
        return self.default_location_src_id

    def _capture_dest_locations(self):
        return self.default_location_dest_id

    def _capture_defaults(self):
        values = super()._capture_defaults()
        if self.code == "outgoing" and not values["location_dest_id"]:
            values["location_dest_id"] = self.env.ref(
                "stock.stock_location_customers", raise_if_not_found=False
            )
        elif self.code == "incoming" and not values["location_id"]:
            values["location_id"] = self.env.ref(
                "stock.stock_location_suppliers", raise_if_not_found=False
            )
        return values

    def _capture_info(self):
        info = super()._capture_info()
        info["company_id"] = self.company_id
        return info

    def _capture_ready_pickings(self, product):
        """Ready transfers of the operation type with an operation of the
        product, in the order their operations were created"""
        moves = self.env["stock.move"].search(
            [
                ("picking_type_id", "=", self.id),
                ("state", "in", ["assigned", "partially_available"]),
                ("product_id", "=", product.id),
            ],
            order="id",
        )
        return moves.picking_id

    def _capture_document_for(self, session):
        search = session.profile_id.search_picking_from_product
        if not search or not session.product_id:
            return self.browse()
        pickings = self._capture_ready_pickings(session.product_id)
        return pickings[:1] if search == "first" else pickings[-1:]

    def _capture_check(self, session):
        return session._capture_fail(self.env._("No picking selected"), "info")

    def action_capture_new_picking(self):
        """Open the capture screen on a new unplanned transfer"""
        self.ensure_one()
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.id,
                "location_id": self.default_location_src_id.id,
                "location_dest_id": self.default_location_dest_id.id,
            }
        )
        return picking.action_capture_open(
            profile=self.capture_new_picking_profile_id or None
        )
