# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = "stock.move"

    captured_quantity = fields.Float(
        compute="_compute_captured_quantity",
        digits="Product Unit",
        help="Quantity picked, captured or otherwise, in the unit of the move",
    )
    capture_state = fields.Selection(
        selection=[
            ("to_capture", "To capture"),
            ("capturing", "Capturing"),
            ("captured", "Captured"),
        ],
        compute="_compute_capture_state",
        store=True,
        help="Progress of the capture of the operation, shared by the screens "
        "that read or weigh quantities",
    )
    capture_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Captured By",
        copy=False,
        help="User capturing the operation, who locks it for the others",
    )
    is_capture_locked = fields.Boolean(compute="_compute_is_capture_locked")
    capture_state_color = fields.Integer(compute="_compute_capture_state_color")
    capture_lot_names = fields.Char(compute="_compute_capture_names")
    capture_location_names = fields.Char(compute="_compute_capture_names")

    @api.depends("move_line_ids.quantity", "move_line_ids.picked")
    def _compute_captured_quantity(self):
        for move in self:
            move.captured_quantity = sum(
                line.uom_id._compute_quantity(line.quantity, move.uom_id, round=False)
                for line in move.move_line_ids.filtered("picked")
            )

    @api.depends(
        "move_line_ids.quantity", "move_line_ids.picked", "state", "product_uom_qty"
    )
    def _compute_capture_state(self):
        for move in self:
            if move.state in ("draft", "done", "cancel"):
                move.capture_state = False
            elif move.uom_id.compare(move.captured_quantity, move.product_uom_qty) >= 0:
                move.capture_state = "captured"
            elif move.uom_id.compare(move.captured_quantity, 0) > 0:
                move.capture_state = "capturing"
            else:
                move.capture_state = "to_capture"

    def _compute_capture_state_color(self):
        colors = {"to_capture": 1, "capturing": 3, "captured": 10}
        for move in self:
            move.capture_state_color = colors.get(move.capture_state, 0)

    @api.depends("move_line_ids.lot_id", "move_line_ids.location_id")
    def _compute_capture_names(self):
        """Lots and source locations of the operations, to show on cards"""
        for move in self:
            move.capture_lot_names = ", ".join(move.move_line_ids.lot_id.mapped("name"))
            move.capture_location_names = ", ".join(
                move.move_line_ids.location_id.mapped("name")
            )

    @api.depends("capture_user_id", "state")
    @api.depends_context("uid")
    def _compute_is_capture_locked(self):
        """The operations captured by another user are locked"""
        for move in self:
            move.is_capture_locked = (
                move.state not in ("draft", "done", "cancel")
                and move.capture_user_id
                and move.capture_user_id != self.env.user
            )

    def _capture_lock(self):
        """Lock the operations for the current user, so others don't capture
        them at the same time"""
        locked = self.filtered("is_capture_locked")
        if locked:
            raise UserError(
                self.env._(
                    "The user %(user)s is already capturing this operation",
                    user=locked[:1].capture_user_id.name,
                )
            )
        self.capture_user_id = self.env.user

    def _capture_unlock(self):
        self.capture_user_id = False

    def action_capture_remaining(self):
        """Capture what is left of the demand of the operations, e.g. from a
        card, for products that are not read or weighed one by one"""
        for move in self.filtered(lambda m: m.state not in ("draft", "done", "cancel")):
            remaining = move.product_uom_qty - move.captured_quantity
            if move.uom_id.compare(remaining, 0) > 0:
                move._capture_quantity(remaining)
        return True

    def action_capture_undo(self):
        """Undo everything captured on the operations"""
        for line in self.move_line_ids.filtered("picked"):
            if line.exists() and line.state not in ("done", "cancel"):
                line._capture_undo()
        return True

    def _capture_quantity(self, quantity, uom=None, **characteristics):
        """Record a quantity captured by the user (read or weighed) on the move.

        See :meth:`_capture_lines` for the arguments. The captured lines keep
        who captured them and when.

        :return: the picked move lines holding the captured quantity
        """
        lines = self._capture_lines(quantity, uom=uom, **characteristics)
        lines._capture_mark_captured()
        return lines

    def _capture_lines(
        self,
        quantity,
        uom=None,
        lot=None,
        location=None,
        package=None,
        owner=None,
        result_package=None,
        merge=True,
    ):
        """Take a captured quantity from the reservation of the move.

        The captured quantity is taken from the reservation of the move, so
        capturing what is reserved keeps the reserved quantity:

        - first from its unpicked lines with the captured characteristics;
        - then from the rest of its unpicked lines, when the captured lot,
          location, package or owner is not the reserved one;
        - only the quantity captured over the reservation is reserved anew.

        A characteristic left as ``None`` matches any line, while an empty
        recordset matches the lines without it.

        :param merge: add the quantity to the picked line of the same goods if
            there is one. Without it, the quantity gets lines of its own, e.g.
            one per weighing to label it.
        :return: the picked move lines holding the captured quantity
        """
        self.ensure_one()
        if self.state in ("draft", "done", "cancel"):
            raise UserError(
                self.env._("Quantities can only be captured on confirmed moves.")
            )
        result_package = self.picking_type_id._capture_result_package(
            result_package, self.location_dest_id
        )
        remaining = (uom or self.uom_id)._compute_quantity(
            quantity, self.uom_id, round=False
        )
        characteristics = {
            "lot_id": lot,
            "location_id": location,
            "package_id": package,
            "owner_id": owner,
        }
        unpicked_lines = self.move_line_ids.filtered(lambda ml: not ml.picked)
        matching_lines = unpicked_lines.filtered(
            lambda ml: ml._capture_matches(characteristics)
        )
        captured_lines = self.env["stock.move.line"]
        for line in matching_lines:
            if self.uom_id.compare(remaining, 0) <= 0:
                return captured_lines
            take = min(remaining, line._capture_move_uom_quantity())
            captured_lines |= line._capture_take(
                take, result_package, targets=None if merge else captured_lines
            )
            remaining -= take
        if self.uom_id.compare(remaining, 0) <= 0:
            return captured_lines
        # The rest of the reservation of the move moves to the captured
        # characteristics, so the move keeps its reserved quantity
        to_add = remaining
        for line in unpicked_lines - matching_lines:
            if self.uom_id.compare(remaining, 0) <= 0:
                break
            take = min(remaining, line._capture_move_uom_quantity())
            line._capture_release(take)
            remaining -= take
        return captured_lines | self._capture_add(
            to_add,
            characteristics,
            result_package,
            targets=None if merge else captured_lines,
        )

    def _capture_spread(self, quantity, uom=None, **characteristics):
        """Capture a quantity of a product over these moves of it.

        It fills the pending quantity of the moves in order and captures the
        rest on the last one.

        :return: the picked move lines holding the captured quantity
        """
        uom = uom or self.product_id.uom_id
        # A single destination package for the whole captured quantity
        first_move = self[:1]
        characteristics["result_package"] = (
            first_move.picking_type_id._capture_result_package(
                characteristics.get("result_package"), first_move.location_dest_id
            )
        )
        captured_lines = self.env["stock.move.line"]
        remaining = quantity
        for move in self:
            if uom.compare(remaining, 0) <= 0:
                break
            take = remaining
            if move != self[-1]:
                picked_quantity = sum(
                    line.uom_id._compute_quantity(line.quantity, uom, round=False)
                    for line in move.move_line_ids.filtered("picked")
                )
                pending = (
                    move.uom_id._compute_quantity(
                        move.product_uom_qty, uom, round=False
                    )
                    - picked_quantity
                )
                take = min(remaining, pending)
                if uom.compare(take, 0) <= 0:
                    continue
            captured_lines |= move._capture_quantity(take, uom=uom, **characteristics)
            remaining -= take
        return captured_lines

    def _capture_add(
        self, quantity, characteristics, result_package=None, targets=None
    ):
        """Add a quantity, expressed in the move UoM, to the picked line with the
        given characteristics, creating it if there is none.

        :param targets: the picked lines the quantity can be added to, all the
            lines of the move by default
        """
        self.ensure_one()
        values = {
            "lot_id": characteristics.get("lot_id") or self.env["stock.lot"],
            "location_id": characteristics.get("location_id") or self.location_id,
            "package_id": characteristics.get("package_id")
            or self.env["stock.package"],
            "owner_id": characteristics.get("owner_id") or self.env["res.partner"],
            "location_dest_id": self.location_dest_id,
            "result_package_id": result_package or self.env["stock.package"],
        }
        targets = self.move_line_ids if targets is None else targets
        target = targets.filtered(lambda ml: ml.picked and ml._capture_matches(values))[
            :1
        ]
        if target:
            target.quantity += self.uom_id._compute_quantity(
                quantity, target.uom_id, round=False
            )
            return target
        line_values = self._prepare_move_line_vals()
        line_values.update(
            {field: record.id for field, record in values.items()},
            quantity=quantity,
            picked=True,
        )
        return self.env["stock.move.line"].create(line_values)
