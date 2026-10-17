# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models
from odoo.exceptions import UserError

# Values read and not captured yet, kept by the screens between barcodes
SCAN_FIELDS = {
    "product_id": "product.product",
    "uom_id": "uom.uom",
    "lot_id": "stock.lot",
    "location_id": "stock.location",
    "package_id": "stock.package",
    "owner_id": "res.partner",
    "result_package_id": "stock.package",
}
# Values kept after a capture, so the next products go to the same place
SCAN_STICKY_FIELDS = ("location_id", "result_package_id", "owner_id")


class StockPicking(models.Model):
    _inherit = "stock.picking"

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
    ):
        """Capture a quantity of a product on the transfer.

        It is spread over the moves of the product, and a product without moves
        gets a new one, as when a line is added to the transfer.

        :return: the picked move lines holding the captured quantity
        """
        self.ensure_one()
        if self.state in ("draft", "done", "cancel"):
            raise UserError(
                self.env._("Quantities can only be captured on confirmed transfers.")
            )
        uom = uom or product.uom_id
        characteristics = {
            "lot": lot,
            "location": location,
            "package": package,
            "owner": owner,
            "result_package": result_package,
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
        result_package = self.picking_type_id._capture_result_package(
            characteristics["result_package"], self.location_dest_id
        )
        return self.env["stock.move.line"].create(
            {
                "picking_id": self.id,
                "product_id": product.id,
                "uom_id": uom.id,
                "quantity": quantity,
                "location_id": location.id,
                "location_dest_id": self.location_dest_id.id,
                "lot_id": (characteristics["lot"] or self.env["stock.lot"]).id,
                "package_id": (
                    characteristics["package"] or self.env["stock.package"]
                ).id,
                "owner_id": (characteristics["owner"] or self.env["res.partner"]).id,
                "result_package_id": (result_package or self.env["stock.package"]).id,
                "picked": True,
            }
        )

    def capture_scan(self, barcode, scan_values=None):
        """Process a barcode read on the transfer from any capture screen.

        The barcode is interpreted (product, packaging, lot, package, location,
        weight and GS1 barcodes) and joined to the values read before it. Once
        the product is known, with its lot when it needs one, the quantity is
        captured on the transfer.

        :param barcode: the barcode read
        :param scan_values: the values read and not captured yet, as returned
            by the previous call: ids of :data:`SCAN_FIELDS`, ``lot_name`` and
            ``quantity``
        :return: dict with the ``scan_values`` to send with the next barcode,
            their names to show in ``scan_display``, the captured ``line_ids``,
            a ``message`` and its ``message_type``
            (``success``, ``info``, ``warning`` or ``danger``)
        """
        self.ensure_one()
        values = self._capture_scan_browse(scan_values or {})
        read = self._capture_parse_barcode(barcode)
        if not read:
            return self._capture_scan_result(
                values,
                self.env._("Barcode %(barcode)s not found", barcode=barcode),
                "danger",
            )
        package = read.pop("package_content", False)
        if package:
            return self._capture_scan_package(values, package)
        values.update(read)
        return self._capture_scan_apply(values)

    def _capture_scan_browse(self, scan_values):
        values = {
            field: self.env[model].browse(scan_values[field])
            for field, model in SCAN_FIELDS.items()
            if scan_values.get(field)
        }
        for key in ("lot_name", "quantity"):
            if scan_values.get(key):
                values[key] = scan_values[key]
        return values

    def _capture_scan_result(self, values, message, message_type, lines=None):
        scan_values = {
            key: value.id if isinstance(value, models.BaseModel) else value
            for key, value in values.items()
            if value
        }
        scan_display = {
            key: value.display_name if isinstance(value, models.BaseModel) else value
            for key, value in values.items()
            if value
        }
        return {
            "scan_values": scan_values,
            "scan_display": scan_display,
            "line_ids": lines.ids if lines else [],
            "message": message,
            "message_type": message_type,
        }

    def _capture_in_source_location(self, location):
        return any(location._child_of(source) for source in self.location_id)

    def _capture_parse_barcode(self, barcode):
        """Interpret a barcode as the values it reads on these transfers.

        It works on several transfers too, e.g. for a screen showing the
        operations of many of them.

        :return: dict of values with the keys of :data:`SCAN_FIELDS`, plus
            ``lot_name``, ``quantity`` or ``package_content`` (a package read
            in the source location, to capture with all its content). Empty
            when nothing matches.
        """
        nomenclature = self.env.company.nomenclature_id
        parsed = nomenclature.parse_barcode(barcode) if nomenclature else False
        if isinstance(parsed, list):
            values = {}
            for item in parsed:
                values.update(self._capture_gs1_values(item))
            if values.get("product_id") or len(values) > 1:
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
        return {}

    def _capture_search_product(self, code):
        Product = self.env["product.product"]
        codes = [code]
        # GTIN-14 of a product with an EAN-13 barcode
        if len(code) == 14 and code.startswith("0"):
            codes.append(code[1:])
        return Product.search([("barcode", "in", codes)], limit=1)

    def _capture_search_barcode(self, code):
        """Values read by a barcode of a record"""
        product = self._capture_search_product(code)
        if product:
            return {"product_id": product}
        packaging = self.env["product.uom"].search([("barcode", "=", code)], limit=1)
        if packaging:
            return {
                "product_id": packaging.product_id,
                "uom_id": packaging.uom_id,
                "quantity": 1.0,
            }
        lot = self.env["stock.lot"].search(
            [("name", "=", code), ("product_id", "in", self.move_ids.product_id.ids)],
            limit=1,
        )
        if lot:
            return {"lot_id": lot, "product_id": lot.product_id}
        package = self.env["stock.package"].search([("name", "=", code)], limit=1)
        if package:
            if package.quant_ids.filtered(
                lambda quant: self._capture_in_source_location(quant.location_id)
            ):
                return {"package_content": package}
            return {"result_package_id": package}
        location = self.env["stock.location"].search(
            [("barcode", "=", code), ("id", "child_of", self.location_id.ids)],
            limit=1,
        )
        if location:
            return {"location_id": location}
        return {}

    def _capture_scan_apply(self, values):
        """Capture the values read once they are enough"""
        product = values.get("product_id")
        if not product:
            return self._capture_scan_result(
                values, self.env._("Read, scan a product"), "info"
            )
        lot = values.get("lot_id")
        if product.tracking and not lot and values.get("lot_name"):
            lot = values["lot_id"] = self._capture_scan_lot(product, values["lot_name"])
        if product.tracking and not lot:
            return self._capture_scan_result(
                values,
                self.env._("Scan the lot of %(product)s", product=product.display_name),
                "warning",
            )
        uom = values.get("uom_id") or product.uom_id
        quantity = values.get("quantity") or 1.0
        lines = self._capture_product(
            product,
            quantity,
            uom=uom,
            lot=lot or None,
            location=values.get("location_id") or None,
            owner=values.get("owner_id") or None,
            result_package=values.get("result_package_id") or None,
        )
        sticky = {key: values[key] for key in SCAN_STICKY_FIELDS if values.get(key)}
        return self._capture_scan_result(
            sticky,
            self.env._(
                "%(quantity)s %(uom)s of %(product)s",
                quantity=quantity,
                uom=uom.name,
                product=product.display_name,
            ),
            "success",
            lines,
        )

    def _capture_scan_lot(self, product, lot_name):
        lot = self.env["stock.lot"].search(
            [("name", "=", lot_name), ("product_id", "=", product.id)], limit=1
        )
        if not lot and self.picking_type_id.use_create_lots:
            lot = self.env["stock.lot"].create(
                {"name": lot_name, "product_id": product.id}
            )
        return lot

    def _capture_scan_package(self, values, package):
        """Capture a whole package of the source location"""
        lines = self.env["stock.move.line"]
        quants = package.quant_ids.filtered(
            lambda quant: self._capture_in_source_location(quant.location_id)
        )
        for quant in quants:
            lines |= self._capture_product(
                quant.product_id,
                quant.quantity,
                lot=quant.lot_id,
                location=quant.location_id,
                package=package,
                owner=quant.owner_id,
                result_package=values.get("result_package_id") or package,
            )
        sticky = {key: values[key] for key in SCAN_STICKY_FIELDS if values.get(key)}
        return self._capture_scan_result(
            sticky,
            self.env._("Package %(package)s", package=package.name),
            "success",
            lines,
        )
