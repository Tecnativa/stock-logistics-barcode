# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class StockLocation(models.Model):
    """A location is the document of an inventory count: the quantities read
    are counted on its stock"""

    _name = "stock.location"
    _inherit = ("stock.location", "stock.capture.document")

    def _capture_profile(self):
        return self.env.ref("stock_capture.stock_capture_profile_inventory")

    def _capture_kind(self):
        return "inventory"

    def _capture_source_locations(self):
        return self

    def _capture_dest_locations(self):
        return self

    def _capture_info(self):
        info = super()._capture_info()
        info["company_id"] = self.company_id or self.env.company
        return info

    def _capture_search_barcode(self, code):
        values = super()._capture_search_barcode(code)
        if not values.get("lot_id") and not values.get("product_id"):
            lot = self.env["stock.lot"].search([("name", "=", code)], limit=2)
            if len(lot) == 1:
                values = {"lot_id": lot, "product_id": lot.product_id}
        return values

    def _capture_counted_quants_domain(self, counted=True):
        """Quants of the user to count in the location, the counted ones or
        the pending ones"""
        return [
            ("location_id", "child_of", self.ids),
            ("user_id", "=", self.env.user.id),
            ("inventory_date", "<=", fields.Date.context_today(self)),
            ("inventory_quantity_set", "=", counted),
        ]

    def _capture_check(self, session):
        product = session.product_id
        if not product.is_storable:
            return session._capture_fail(
                self.env._(
                    "The product %(product)s is not tracked in stock",
                    product=product.display_name,
                )
            )
        if product.tracking == "serial" and product.uom_id.compare(
            session._capture_quantity_in_product_uom(), 1
        ):
            return session._capture_fail(
                self.env._(
                    "Inventory line with more than one unit in serial tracked product"
                )
            )
        return True

    def _capture_apply(self, session):
        """Count the quantity read on the stock of the location"""
        product = session.product_id
        lot = session.lot_id
        if product.tracking and not lot and session.lot_name:
            lot = session.lot_id = session._capture_lot(create=True)
        location = session.location_id or self
        quant_domain = [
            ("product_id", "=", product.id),
            ("location_id", "=", location.id),
            ("lot_id", "=", lot.id),
            ("package_id", "=", session.package_id.id),
            ("owner_id", "=", session.owner_id.id),
        ]
        Quant = self.env["stock.quant"].with_context(inventory_mode=True)
        quant = session.edit_quant_id or Quant.search(quant_domain, limit=1)
        quantity = session._capture_quantity_in_product_uom()
        if quant:
            quant = quant.with_context(inventory_mode=True)
            if (
                product.tracking == "serial"
                and quant.inventory_quantity_set
                and quant.inventory_quantity > 0
            ):
                return session._capture_fail(
                    self.env._(
                        "Inventory line with more than one unit in serial tracked "
                        "product"
                    )
                )
            if (
                quant == session.edit_quant_id
                or session.profile_id.replace_quantity
                or not quant.inventory_quantity_set
            ):
                new_quantity = quantity
            else:
                new_quantity = quant.inventory_quantity + quantity
            quant.write(
                {
                    "inventory_quantity": new_quantity,
                    "user_id": self.env.user.id,
                    "inventory_date": fields.Date.context_today(self),
                }
            )
        else:
            quant = Quant.create(
                {
                    "product_id": product.id,
                    "location_id": location.id,
                    "lot_id": lot.id,
                    "package_id": session.package_id.id,
                    "owner_id": session.owner_id.id,
                    "inventory_quantity": quantity,
                }
            )
        session.edit_quant_id = False
        return quant

    def _capture_can_validate(self):
        return True

    def _capture_validate(self, session):
        """Apply the counted quantities, with the reason asked by Odoo"""
        quants = self.env["stock.quant"].search(self._capture_counted_quants_domain())
        if not quants:
            return session._capture_fail(self.env._("Nothing counted to apply"))
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock.action_stock_inventory_adjustement_name"
        )
        action["context"] = {
            "default_quant_ids": quants.ids,
            "capture_session_id": session.id,
        }
        return action
