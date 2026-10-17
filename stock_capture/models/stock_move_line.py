# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models

CAPTURE_PLACE_FIELDS = (
    "location_id",
    "lot_id",
    "package_id",
    "owner_id",
    "location_dest_id",
)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    capture_card_quantity = fields.Float(
        compute="_compute_capture_card_quantities",
        digits="Product Unit",
        help="Quantity of the card in the unit of the product: the lines of "
        "its group when the screen groups them",
    )
    capture_card_captured = fields.Float(
        compute="_compute_capture_card_quantities", digits="Product Unit"
    )
    capture_card_pending = fields.Float(
        compute="_compute_capture_card_quantities",
        digits="Product Unit",
        help="Quantity of the card left to capture, in the unit of the product",
    )

    @api.depends("quantity", "picked")
    @api.depends_context("capture_session_id")
    def _compute_capture_card_quantities(self):
        for line in self:
            lines = line._capture_card_lines()
            line.capture_card_quantity = sum(lines.mapped("quantity_product_uom"))
            line.capture_card_captured = sum(
                lines.filtered("picked").mapped("quantity_product_uom")
            )
            line.capture_card_pending = (
                line.capture_card_quantity - line.capture_card_captured
            )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if self.env.context.get("capture_pick_with_lot"):
            lines._capture_pick_with_lot()
        return lines

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get("capture_pick_with_lot") and (
            "lot_id" in vals or "lot_name" in vals
        ):
            self._capture_pick_with_lot()
        return result

    def _capture_pick_with_lot(self):
        """Lines getting a serial number in the detailed operations opened
        from a capture screen are captured"""
        for line in self.filtered(lambda ml: ml.lot_id or ml.lot_name):
            values = {"picked": True}
            if line.move_id and not line.picking_id:
                # The generate serials tool creates the lines without transfer
                values["picking_id"] = line.move_id.picking_id.id
            line.with_context(capture_pick_with_lot=False).write(values)

    def _capture_matches(self, characteristics):
        """Whether the line has the given characteristics, ``None`` matching any"""
        self.ensure_one()
        return all(
            value is None or self[field] == value
            for field, value in characteristics.items()
        )

    def _capture_same_place(self, other, location_dest=None):
        """Whether both lines move the same goods between the same locations.

        :param location_dest: compare the destination of this line with it
            instead of with the destination of the other line
        """
        self.ensure_one()
        if location_dest is None:
            location_dest = other.location_dest_id
        return self.location_dest_id == location_dest and all(
            self[field] == other[field]
            for field in CAPTURE_PLACE_FIELDS
            if field != "location_dest_id"
        )

    def _capture_move_uom_quantity(self):
        self.ensure_one()
        return self.uom_id._compute_quantity(
            self.quantity, self.move_id.uom_id, round=False
        )

    def _capture_release(self, quantity):
        """Give back a quantity, expressed in the move UoM, of the line"""
        self.ensure_one()
        quantity = self.move_id.uom_id._compute_quantity(
            quantity, self.uom_id, round=False
        )
        if self.uom_id.compare(quantity, self.quantity) >= 0:
            self.unlink()
        else:
            self.quantity -= quantity

    def _capture_take(
        self, quantity, result_package=None, targets=None, location_dest=None
    ):
        """Pick a quantity, expressed in the move UoM, of this unpicked line.

        The quantity joins the picked line of the same goods, destination and
        destination package if there is one. Otherwise this line is picked,
        split first when the quantity is lower, so the rest stays reserved on
        an unpicked line.

        :param targets: the picked lines the quantity can join, all the lines
            of the move by default
        :param location_dest: destination of the picked quantity, the one of
            the line by default
        :return: the picked line
        """
        self.ensure_one()
        move = self.move_id
        package = self.result_package_id if result_package is None else result_package
        dest = self.location_dest_id if location_dest is None else location_dest
        targets = move.move_line_ids if targets is None else targets
        target = targets.filtered(
            lambda ml: (
                ml.picked
                and ml._capture_same_place(self, location_dest=dest)
                and ml.result_package_id == package
            )
        )[:1]
        if target:
            self._capture_release(quantity)
            target.quantity += move.uom_id._compute_quantity(
                quantity, target.uom_id, round=False
            )
            return target
        quantity = move.uom_id._compute_quantity(quantity, self.uom_id, round=False)
        if self.uom_id.compare(quantity, self.quantity) < 0:
            rest = self._split(quantity, package.id)
            # Odoo creates the line picked when the move already is
            if rest.picked:
                rest.picked = False
        elif self.result_package_id != package:
            self.result_package_id = package
        if self.location_dest_id != dest:
            self.location_dest_id = dest
        self.picked = True
        return self

    def _capture_undo(self, quantity=None, merge=True):
        """Undo a quantity, expressed in the line UoM, captured on this line.

        The quantity goes back to the reservation of the move up to its demand,
        joining the unpicked line of the same goods if there is one.

        :param merge: without it, the line is kept, unpicked when the whole
            quantity is undone, instead of joining another line
        """
        self.ensure_one()
        move = self.move_id
        if quantity is None or self.uom_id.compare(quantity, self.quantity) > 0:
            quantity = self.quantity
        whole_line = self.uom_id.compare(quantity, self.quantity) == 0
        # The quantity captured over the demand is not kept reserved
        excess = move.uom_id._compute_quantity(
            move.quantity - move.product_uom_qty, self.uom_id, round=False
        )
        release = min(quantity, max(excess, 0.0))
        keep = quantity - release
        sibling = self.browse()
        if merge:
            sibling = move.move_line_ids.filtered(
                lambda ml: not ml.picked and ml._capture_same_place(self)
            )[:1]
        if not sibling and whole_line:
            if not self.uom_id.is_zero(release):
                self.quantity -= release
            self.picked = False
            return
        if not sibling and self.uom_id.is_zero(release):
            rest = self._split(self.quantity - quantity, self.result_package_id.id)
            rest.picked = False
            return
        if not self.uom_id.is_zero(keep):
            if sibling:
                sibling.quantity += self.uom_id._compute_quantity(
                    keep, sibling.uom_id, round=False
                )
            else:
                self.copy(
                    {"quantity": keep, "picked": False, "result_package_id": False}
                )
        if whole_line:
            self.unlink()
        else:
            self.quantity -= quantity

    def _capture_set_quantity(self, quantity):
        """Set the quantity, expressed in the line UoM, captured on this line,
        e.g. a weight recorded on it.

        The difference with its current quantity is given back to or taken from
        the reservation of the move, as captures do: an unpicked line captured
        for less keeps the rest reserved on an unpicked line, and the quantity
        captured over the line is taken from the other unpicked lines of the
        move before reserving anew. Setting zero undoes the capture and keeps
        the line, unpicked.
        """
        self.ensure_one()
        move = self.move_id
        if self.uom_id.is_zero(quantity):
            if self.picked:
                self._capture_undo(merge=False)
            return self
        if not self.picked:
            if self.uom_id.compare(quantity, self.quantity) < 0:
                rest = self._split(quantity, self.result_package_id.id)
                # Odoo creates the line picked when the move already is
                if rest.picked:
                    rest.picked = False
            self.picked = True
        elif self.uom_id.compare(quantity, self.quantity) < 0:
            self._capture_undo(self.quantity - quantity, merge=False)
            return self
        extra = self.uom_id._compute_quantity(
            quantity - self.quantity, move.uom_id, round=False
        )
        if move.uom_id.compare(extra, 0) <= 0:
            return self
        # Take the extra quantity from the reservation of the same goods first
        others = (move.move_line_ids - self).filtered(lambda ml: not ml.picked)
        others = others.sorted(lambda ml: not ml._capture_same_place(self))
        remaining = extra
        for line in others:
            if move.uom_id.compare(remaining, 0) <= 0:
                break
            take = min(remaining, line._capture_move_uom_quantity())
            line._capture_release(take)
            remaining -= take
        self.quantity = quantity
        return self

    # Cards of the capture screens

    def _capture_card_lines(self):
        """Lines of the card, all the lines of its group when the screen groups
        them"""
        session = self.env["stock.capture.session"]._capture_from_context()
        if not session or not session.profile_id.card_group:
            return self
        moves = session._capture_document()._capture_moves()
        key = session._capture_card_group_key(self)
        return moves.move_line_ids.filtered(
            lambda ml: (
                ml.state not in ("done", "cancel")
                and session._capture_card_group_key(ml) == key
            )
        )

    def action_capture_card_remaining(self):
        """Capture what is reserved on the card"""
        for line in self._capture_card_lines().filtered(lambda ml: not ml.picked):
            line._capture_take(line._capture_move_uom_quantity())
        self.env["stock.capture.session"]._capture_refresh_from_context()
        return True

    def action_capture_card_undo(self):
        """Undo what is captured on the card"""
        for line in self._capture_card_lines().filtered("picked"):
            if line.exists():
                line._capture_undo()
        self.env["stock.capture.session"]._capture_refresh_from_context()
        return True

    def action_capture_card_skip(self):
        """Leave the reservation of the card without capturing it"""
        lines = self._capture_card_lines().filtered(lambda ml: not ml.picked)
        lines.unlink()
        self.env["stock.capture.session"]._capture_refresh_from_context()
        return True

    def action_capture_line_delete(self):
        """Remove a captured detailed operation: its quantity is reserved again
        for its operation"""
        moves = self.move_id
        for line in self.filtered("picked"):
            line._capture_undo()
        moves.capture_backorder_action = "pending"
        moves.capture_forced = False
        moves._action_assign()
        self.env["stock.capture.session"]._capture_refresh_from_context()
        return True

    def action_capture_card_select(self):
        """Fill the capture screen from the card"""
        self.ensure_one()
        session = self.env["stock.capture.session"]._capture_from_context()
        if session:
            session.action_select_card(self._name, self.id)
        return True
