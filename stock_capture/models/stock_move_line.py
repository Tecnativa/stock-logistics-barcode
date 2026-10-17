# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields, models

CAPTURE_PLACE_FIELDS = (
    "location_id",
    "lot_id",
    "package_id",
    "owner_id",
    "location_dest_id",
)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    capture_user_id = fields.Many2one(
        comodel_name="res.users", string="Captured By", copy=False
    )
    capture_date = fields.Datetime(string="Captured On", copy=False)

    def _capture_mark_captured(self):
        """Keep who captured these lines and when"""
        self.write(
            {"capture_user_id": self.env.user.id, "capture_date": fields.Datetime.now()}
        )

    def _capture_matches(self, characteristics):
        """Whether the line has the given characteristics, ``None`` matching any"""
        self.ensure_one()
        return all(
            value is None or self[field] == value
            for field, value in characteristics.items()
        )

    def _capture_same_place(self, other):
        """Whether both lines move the same goods between the same locations"""
        self.ensure_one()
        return all(self[field] == other[field] for field in CAPTURE_PLACE_FIELDS)

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

    def _capture_take(self, quantity, result_package=None, targets=None):
        """Pick a quantity, expressed in the move UoM, of this unpicked line.

        The quantity joins the picked line of the same goods and destination
        package if there is one. Otherwise this line is picked, split first
        when the quantity is lower, so the rest stays reserved on an unpicked
        line.

        :param targets: the picked lines the quantity can join, all the lines
            of the move by default
        :return: the picked line
        """
        self.ensure_one()
        move = self.move_id
        package = self.result_package_id if result_package is None else result_package
        targets = move.move_line_ids if targets is None else targets
        target = targets.filtered(
            lambda ml: (
                ml.picked
                and ml._capture_same_place(self)
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
        self._capture_mark_captured()
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
