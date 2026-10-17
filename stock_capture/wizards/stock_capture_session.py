# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang
from odoo.tools.safe_eval import safe_eval

KINDS = [
    ("incoming", "Receipt"),
    ("outgoing", "Delivery"),
    ("internal", "Internal Transfer"),
    ("inventory", "Inventory"),
]
# Fields filled from a pending card
CARD_FIELDS = (
    "location_id",
    "location_dest_id",
    "product_id",
    "lot_id",
    "package_id",
    "result_package_id",
)


class StockCaptureSession(models.TransientModel):
    """What a user is reading on a capture screen working on a document.

    The screen sends the barcodes read to :meth:`capture_barcode` and shows the
    fields of the session: the values read, the message of the last reading
    and the cards of the document (operations, detailed operations or quants)
    to capture.
    """

    _name = "stock.capture.session"
    _description = "Capture screen session"
    _rec_name = "document_name"
    # The session survives the navigation of the user for two days
    _transient_max_hours = 48

    res_model = fields.Char(string="Document Model", required=True, index=True)
    res_id = fields.Many2oneReference(
        string="Document", model_field="res_model", required=True, index=True
    )
    document_name = fields.Char(compute="_compute_document")
    capture_kind = fields.Selection(KINDS, compute="_compute_document")
    company_id = fields.Many2one("res.company", compute="_compute_document")
    partner_id = fields.Many2one("res.partner", compute="_compute_document")
    note = fields.Html(compute="_compute_document")
    can_validate = fields.Boolean(compute="_compute_document")
    profile_id = fields.Many2one(
        comodel_name="stock.capture.profile", required=True, ondelete="cascade"
    )
    user_id = fields.Many2one(
        comodel_name="res.users", default=lambda self: self.env.user, required=True
    )
    # Values read
    barcode = fields.Char(readonly=True)
    product_id = fields.Many2one(comodel_name="product.product")
    product_tracking = fields.Selection(related="product_id.tracking")
    uom_id = fields.Many2one(comodel_name="uom.uom", string="Unit")
    packaging_id = fields.Many2one(comodel_name="product.uom")
    quantity = fields.Float(digits="Product Unit")
    lot_id = fields.Many2one(comodel_name="stock.lot", string="Lot/Serial Number")
    lot_name = fields.Char(string="Lot/Serial Number Name")
    location_id = fields.Many2one(comodel_name="stock.location", string="Source")
    location_from_user = fields.Boolean(
        help="The source was read or chosen by the user, not proposed by the screen"
    )
    location_dest_id = fields.Many2one(
        comodel_name="stock.location", string="Destination"
    )
    location_dest_proposed = fields.Boolean(
        help="The destination was proposed by the screen from the stock of the product"
    )
    package_id = fields.Many2one(comodel_name="stock.package")
    result_package_id = fields.Many2one(
        comodel_name="stock.package", string="Destination Package"
    )
    keep_result_package = fields.Boolean(
        help="Keep the destination package for the next readings"
    )
    owner_id = fields.Many2one(comodel_name="res.partner")
    edit_quant_id = fields.Many2one(
        comodel_name="stock.quant",
        help="Counted quant edited from its card: its quantity is replaced",
    )
    # Screen
    step = fields.Integer(readonly=True)
    step_message = fields.Char(readonly=True, help="What the screen waits for")
    message = fields.Char(readonly=True)
    message_type = fields.Selection(
        [
            ("info", "Info"),
            ("success", "Success"),
            ("warning", "Warning"),
            ("danger", "Error"),
        ],
        readonly=True,
    )
    manual_entry = fields.Boolean(help="Enter the values by hand")
    force_visible = fields.Boolean(
        readonly=True,
        help="The last reading needs a confirmation to be captured anyway",
    )
    feedback_seq = fields.Integer(
        readonly=True,
        help="Increased on each reading or action, for the screen to play its "
        "sound, show its notification and move the focus",
    )
    feedback_sound = fields.Selection([("ok", "OK"), ("ko", "KO")], readonly=True)
    feedback_focus = fields.Char(readonly=True)
    feedback_notification = fields.Char(readonly=True)
    show_detailed_operations = fields.Boolean()
    card_filter = fields.Selection(
        selection=lambda self: (
            self.env["stock.capture.profile"]._fields["card_filter"].selection
        ),
    )
    card_move_id = fields.Many2one(comodel_name="stock.move", string="Current Card")
    card_line_id = fields.Many2one(
        comodel_name="stock.move.line", string="Current Detailed Card"
    )
    card_move_ids = fields.Many2many(
        comodel_name="stock.move", compute="_compute_cards", string="Operations"
    )
    card_line_ids = fields.Many2many(
        comodel_name="stock.move.line",
        compute="_compute_cards",
        string="Detailed Operations",
    )
    card_quant_ids = fields.Many2many(
        comodel_name="stock.quant", compute="_compute_cards", string="Stock"
    )
    card_count = fields.Integer(compute="_compute_cards")
    captured_line_ids = fields.Many2many(
        comodel_name="stock.move.line",
        compute="_compute_captured_line_ids",
        string="Captured",
    )
    product_demand = fields.Float(compute="_compute_product_totals")
    product_captured = fields.Float(compute="_compute_product_totals")
    product_available = fields.Float(compute="_compute_product_available")
    product_outgoing_qty = fields.Float(
        compute="_compute_product_outgoing_qty",
        digits="Product Unit",
        help="Quantity of the product to deliver from the warehouse of the "
        "document, e.g. to store first what has to leave",
    )
    location_stock_count = fields.Integer(
        compute="_compute_location_stock_count",
        help="Locations with stock of the product",
    )
    # Profile options shown on the screen
    guided = fields.Boolean(related="profile_id.guided")
    manual_quantity = fields.Boolean(related="profile_id.manual_quantity")
    manual_confirm = fields.Boolean(related="profile_id.manual_confirm")
    show_stock = fields.Boolean(related="profile_id.show_stock")
    show_owner = fields.Boolean(related="profile_id.show_owner")
    show_form_scan = fields.Boolean(related="profile_id.show_form_scan")
    card_source = fields.Selection(related="profile_id.card_source")

    # Document

    def _capture_document(self):
        self.ensure_one()
        return self.env[self.res_model].browse(self.res_id).exists()

    def write(self, vals):
        if "location_id" in vals and "location_from_user" not in vals:
            # A source set by the user, e.g. typed in manual entry
            vals = dict(vals, location_from_user=bool(vals["location_id"]))
        if "location_dest_id" in vals and "location_dest_proposed" not in vals:
            # A destination set by the user
            vals = dict(vals, location_dest_proposed=False)
        return super().write(vals)

    @api.depends("res_model", "res_id")
    def _compute_document(self):
        for session in self:
            document = session._capture_document()
            info = document._capture_info() if document else {}
            session.document_name = document.display_name
            session.capture_kind = document._capture_kind() if document else False
            session.company_id = info.get("company_id")
            session.partner_id = info.get("partner_id")
            session.note = info.get("note")
            session.can_validate = bool(document) and document._capture_can_validate()

    @api.model
    def _capture_open(self, document, profile=None):
        """Session of the current user on the document, created when there is
        none"""
        profile = profile or document._capture_profile()
        session = self.search(
            [
                ("res_model", "=", document._name),
                ("res_id", "=", document.id),
                ("user_id", "=", self.env.user.id),
                ("profile_id", "=", profile.id),
            ],
            limit=1,
            order="id desc",
        )
        if not session:
            session = self.create(
                {
                    "res_model": document._name,
                    "res_id": document.id,
                    "profile_id": profile.id,
                    "manual_entry": profile.manual_entry,
                    "card_filter": profile.card_filter,
                    "show_detailed_operations": profile.show_detailed_operations,
                }
            )
            session._capture_fill_defaults()
        session._capture_refresh()
        return session

    def _capture_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.document_name,
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
            "context": {"form_view_initial_mode": "edit"},
        }

    def _capture_fill_defaults(self):
        """Values of the document for the fields filled by default"""
        values = self._capture_document()._capture_defaults()
        kind = self.capture_kind
        for field_name, value in values.items():
            field = self.profile_id._get_field(field_name)
            # The fixed side of receipts and deliveries is always known
            fixed = (field_name == "location_id" and kind == "incoming") or (
                field_name == "location_dest_id" and kind == "outgoing"
            )
            if field.filled_default or fixed or kind == "inventory":
                self[field_name] = value
        self.location_from_user = False

    def _capture_switch_document(self, document):
        """Work on another document, e.g. the transfer found from a product
        read on an operation type"""
        self.write({"res_model": document._name, "res_id": document.id})
        self._capture_fill_defaults()

    # Feedback

    def _capture_message(self, message, message_type="info"):
        self.message = message
        self.message_type = message_type

    def _capture_feedback(self, sound=None, focus=None, notification=None):
        self.write(
            {
                "feedback_seq": self.feedback_seq + 1,
                "feedback_sound": sound,
                "feedback_focus": focus,
                "feedback_notification": notification,
            }
        )

    def _capture_focus(self, field_name):
        self.feedback_focus = field_name

    def _capture_fail(self, message, message_type="danger"):
        """Reject the reading with the message. Return ``False`` to be returned
        by the checks"""
        self._capture_message(
            f"{self.barcode} ({message})" if self.barcode else message, message_type
        )
        if message_type == "danger":
            self.feedback_sound = "ko"
        return False

    def _capture_result(self):
        """Feedback of the last reading for the screen"""
        self.ensure_one()
        return {
            "message": self.message,
            "message_type": self.message_type,
            "sound": self.feedback_sound,
            "focus": self.feedback_focus,
            "notification": self.feedback_notification,
        }

    # Steps

    def _capture_lot_required(self):
        return self.product_id.tracking and not (
            self.lot_id or (self.lot_name and self._capture_can_create_lot())
        )

    def _capture_field_empty(self, field):
        if field.field_name in ("lot_id", "lot_name"):
            if not self.product_id.tracking or self.profile_id.auto_lot:
                return False
            return not (self.lot_id or self.lot_name)
        return not self[field.field_name]

    def _capture_update_step(self):
        """The step is the one of the first required field to fill"""
        required = self.profile_id.field_ids.filtered("required")
        step = 0
        for field in required:
            if self._capture_field_empty(field):
                step = field.step
                break
        if not step:
            step = required[:1].step
        self.step = step
        names = self.profile_id.field_ids.filtered(
            lambda f: f.step == step and f.to_scan
        ).mapped("name")
        self.step_message = (
            self.env._("Scan %(fields)s", fields=", ".join(names)) if names else False
        )

    def _capture_option_required(self, field):
        """Whether an empty required field can be left empty. Hook for modules
        filling it in another way"""
        if field.field_name == "location_dest_id" and (
            self.profile_id.use_location_dest_putaway
        ):
            document = self._capture_document()
            destination = document._capture_dest_locations()[:1]
            self.location_dest_id = destination.with_context(
                avoid_location_with_reserve=True
            )._get_putaway_strategy(
                self.product_id,
                quantity=self._capture_quantity_in_product_uom(),
                package=self.result_package_id,
            )
            return bool(self.location_dest_id)
        return False

    def _capture_check_required(self):
        for field in self.profile_id.field_ids.filtered("required"):
            if not self._capture_field_empty(field):
                continue
            if field.field_name == "quantity" and self.manual_quantity:
                self._capture_focus("quantity")
            if self._capture_option_required(field):
                continue
            if self.profile_id.display_notification:
                self.feedback_notification = self.env._(
                    "%(name)s is required", name=field.name
                )
            self._capture_update_step()
            return False
        return True

    # Reading

    def capture_barcode(self, barcode):
        """Process a barcode read on the screen.

        :return: feedback for the screen: ``message``, ``message_type``,
            ``sound`` (``ok`` or ``ko``), ``focus`` (field to focus),
            ``notification`` and ``action`` (to execute, e.g. to open the
            transfer found from the product read)
        """
        self.ensure_one()
        self.barcode = barcode.rstrip()
        self.feedback_notification = self.feedback_focus = False
        self.feedback_sound = "ok"
        action = self._capture_process_barcode()
        self._capture_feedback(
            sound=self.feedback_sound,
            focus=self.feedback_focus,
            notification=self.feedback_notification,
        )
        result = self._capture_result()
        if isinstance(action, dict):
            result["action"] = action
        return result

    def _capture_process_barcode(self):
        self._capture_message(self.env._("OK"), "success")
        if self._capture_read_parsed():
            return self._capture_after_read()
        options = self.profile_id.field_ids.filtered(
            lambda f: f.to_scan and f.step == self.step
        )
        read_item, read_quantity = self._capture_read_item(), self.quantity
        found = False
        for option in options:
            if (
                self.profile_id.ignore_filled_fields
                and option.required
                and not self._capture_field_empty(option)
            ):
                continue
            reader = getattr(self, f"_capture_read_{option.field_name}", None)
            if not reader:
                continue
            if reader():
                found = True
                self._capture_accumulate(option, read_item, read_quantity)
                break
            if self.message_type != "success":
                self.feedback_sound = "ko"
                return False
        if not found:
            if self.profile_id.ignore_filled_fields:
                message = self.env._("Barcode not found or field already filled")
            else:
                message = self.env._("Barcode not found with this screen values")
            return self._capture_fail(message)
        return self._capture_after_read()

    def _capture_after_read(self):
        if not self._capture_check_required():
            return False
        if self.manual_confirm or self.manual_entry:
            self._capture_message(self.env._("Review and confirm"), "info")
            return False
        return self._capture_confirm()

    def _capture_read_parsed(self):
        """Values read by GS1 and weight barcodes, whatever the step"""
        document = self._capture_document()
        nomenclature = self.env.company.nomenclature_id
        parsed = nomenclature.parse_barcode(self.barcode) if nomenclature else False
        is_weight = isinstance(parsed, dict) and parsed.get("type") == "weight"
        if not isinstance(parsed, list) and not is_weight:
            return False
        values = document._capture_parse_barcode(self.barcode)
        if not values.get("product_id") and not is_weight:
            # GS1 barcodes of a location or package follow the steps
            if values.get("location_id") and not self._capture_read_values(values):
                return False
            return bool(values) and self._capture_read_values(values)
        return self._capture_read_values(values)

    def _capture_read_values(self, values):
        """Fill the session with the values read by a barcode"""
        package = values.get("package_content")
        if package:
            return self._capture_read_package(package)
        self._capture_read_extra_values(values)
        product = values.get("product_id")
        if product:
            self._capture_set_product(product)
        if values.get("packaging_id"):
            self.packaging_id = values["packaging_id"]
        if values.get("lot_id"):
            self.lot_id = values["lot_id"]
        elif values.get("lot_name"):
            lot = self._capture_lot()
            if lot:
                self.lot_id = lot
            else:
                self.lot_name = values["lot_name"]
        if values.get("uom_id"):
            self.uom_id = values["uom_id"]
        if values.get("quantity"):
            self.quantity = values["quantity"]
        for field_name in ("location_id", "location_dest_id", "result_package_id"):
            if values.get(field_name):
                self[field_name] = values[field_name]
        return True

    def _capture_read_extra_values(self, values):
        """Hook for the values read by other modules, e.g. the expiration date
        of a GS1 barcode"""

    def _capture_read_item(self):
        return (self.product_id, self.packaging_id, self.lot_id, self.lot_name)

    def _capture_quantity_set_by_user(self):
        return (
            self.manual_entry
            or self.manual_quantity
            or self.profile_id._get_field("quantity").filled_default
        )

    def _capture_accumulate(self, option, read_item, read_quantity):
        """Add one more unit (or packaging) to the quantity read when the same
        item is read again before confirming the reading"""
        if (
            not self.profile_id.accumulate_read_quantity
            or not self.manual_confirm
            or option.field_name not in ("product_id", "packaging_id", "lot_id")
            or self._capture_quantity_set_by_user()
            or not read_quantity
            or self._capture_read_item() != read_item
        ):
            return
        if self.quantity == 1.0:
            self.quantity = read_quantity + 1.0

    def _capture_set_default_quantity(self):
        if not self._capture_quantity_set_by_user():
            self.quantity = 1.0

    def _capture_search(self, model):
        return self.env[model].search([("barcode", "=", self.barcode)])

    def _capture_read_location_id(self):
        location = self._capture_document()._capture_search_location(self.barcode)
        if location:
            self.location_id = location
            return True
        return False

    def _capture_read_location_dest_id(self):
        location = self._capture_document()._capture_search_location(self.barcode)
        if location:
            self.location_dest_id = location
            return True
        return False

    def _capture_allowed_product(self, product):
        return product.type == "consu" and (
            self.capture_kind != "inventory" or product.is_storable
        )

    def _capture_read_product_id(self):
        document = self._capture_document()
        product = document._capture_search_product(self.barcode)
        if not product:
            return False
        if not self._capture_allowed_product(product):
            self._capture_message(
                self.env._("The product type is not allowed"), "danger"
            )
            return False
        self._capture_set_product(product)
        if self._capture_fill_from_stock_active():
            quants = self.env["stock.quant"].search(
                self._capture_quant_domain(product=product)
            )
            if quants:
                # A product read is one more unit, not the quantity in stock
                self.with_context(
                    capture_skip_stock_quantity=True
                )._capture_fill_from_quants(quants)
        return True

    def _capture_read_packaging_id(self):
        packaging = self._capture_document()._capture_search_packaging(self.barcode)
        if not packaging:
            return False
        if self.product_id != packaging.product_id:
            self.lot_id = False
        self.product_id = packaging.product_id
        self.packaging_id = packaging
        self.uom_id = packaging.uom_id
        self._capture_set_default_quantity()
        return True

    def _capture_read_lot_name(self):
        if self.product_id.tracking:
            self.lot_name = self.barcode
            lot = self._capture_lot()
            if lot:
                self.lot_id = lot
            self._capture_set_default_quantity()
            return True
        return False

    def _capture_read_lot_id(self):
        if not self.env.user.has_group("stock.group_production_lot"):
            return False
        domain = [("name", "=", self.barcode)]
        if self.product_id:
            domain.append(("product_id", "=", self.product_id.id))
        lots = self.env["stock.lot"].search(domain)
        if len(lots) > 1:
            self._capture_message(
                self.env._("More than one lot found\nScan product before"), "danger"
            )
            return False
        if not lots:
            if self.product_id.tracking and self._capture_can_create_lot():
                self.lot_name = self.barcode
                self._capture_set_default_quantity()
                return True
            return False
        if self.profile_id.fill_from_stock:
            quants = self.env["stock.quant"].search(
                self._capture_quant_domain(product=lots.product_id, lot=lots)
                + [("quantity", ">", 0)]
            )
            if (
                not quants
                and self.capture_kind != "inventory"
                and not self.profile_id.allow_negative_quant
            ):
                self.lot_id = self.lot_name = False
                self._capture_message(
                    self.env._("No stock available for this lot with screen values"),
                    "danger",
                )
                return False
            if quants:
                self._capture_fill_from_quants(quants)
                return True
        if self.product_id != lots.product_id:
            self._capture_set_product(lots.product_id)
        self.lot_id = lots
        self._capture_set_default_quantity()
        return True

    def _capture_read_package_id(self):
        if not self.env.user.has_group("stock.group_tracking_lot"):
            return False
        package = self._capture_document()._capture_search_package(self.barcode)
        if not package:
            return False
        return self._capture_read_package(package)

    def _capture_read_package(self, package):
        domain = [("package_id", "=", package.id), ("quantity", ">", 0)]
        if self.profile_id._get_field("location_id").forced and self.location_id:
            domain.append(("location_id", "=", self.location_id.id))
        if self.owner_id:
            domain.append(("owner_id", "=", self.owner_id.id))
        quants = self.env["stock.quant"].search(domain)
        internal = quants.filtered(lambda q: q.location_id.usage == "internal")
        if not quants:
            return False
        if internal:
            self._capture_fill_from_quants(internal)
        else:
            self.with_context(
                capture_ignore_quant_location=True
            )._capture_fill_from_quants(quants)
        return True

    def _capture_read_result_package_id(self):
        if not self.env.user.has_group("stock.group_tracking_lot"):
            return False
        package = self._capture_document()._capture_search_package(self.barcode)
        if package:
            self.result_package_id = package
            return True
        return False

    def _capture_set_product(self, product):
        """A product is read: its unit and quantity are proposed"""
        self.package_id = False
        if self.product_id != product and self.lot_id.product_id != product:
            self.lot_id = False
            self.lot_name = False
        if self.product_id != product:
            self.packaging_id = False
        self.product_id = product
        self.uom_id = product.uom_id
        self._capture_set_default_quantity()
        self._capture_on_product()

    def _capture_on_product(self):
        """Hook run when the product changes: source of free mode readings,
        lot proposed by removal strategy and destination proposed from the
        stock on receipts"""
        if self.capture_kind == "incoming":
            self._capture_propose_location_dest()
            return
        if self.capture_kind == "inventory":
            return
        if not self.guided:
            self._capture_set_free_source()
        if self.profile_id.auto_lot and self.product_id.tracking:
            self._capture_set_lot_by_removal()

    def _capture_propose_location_dest(self, defaults=None):
        """Receipts store the product where it already has most stock"""
        profile = self.profile_id
        if not profile.propose_location_dest or not self.product_id:
            return
        if profile._get_field("location_dest_id").forced:
            return
        document = self._capture_document()
        proposals = document._capture_dest_locations() | (
            defaults or self.env["stock.location"]
        )
        if (
            self.location_dest_id
            and not self.location_dest_proposed
            and self.location_dest_id not in proposals
        ):
            # A destination chosen by the user is respected
            return
        stock = self.with_context(
            capture_location_field="location_dest_id"
        )._capture_location_stock()
        if stock:
            location = max(stock, key=lambda item: item[1])[0]
        elif self.location_dest_proposed:
            # The destination proposed for the previous product is not valid
            # for this one: the user has to read it
            location = self.env["stock.location"]
        else:
            return
        self.write({"location_dest_id": location.id, "location_dest_proposed": True})

    def _capture_set_free_source(self):
        """In free mode a product read is taken from where it is reserved,
        unless the source already has a pending reservation of it"""
        if self.location_from_user:
            return
        document = self._capture_document()
        pending = document._capture_moves().move_line_ids.filtered(
            lambda ml: (
                ml.product_id == self.product_id
                and not ml.picked
                and ml.location_id.usage == "internal"
            )
        )
        if not pending or pending.filtered(
            lambda ml: ml.location_id == self.location_id
        ):
            return
        self.write(
            {
                "location_id": pending.sorted(lambda ml: ml.location_id.complete_name)[
                    0
                ].location_id.id,
                "location_from_user": False,
            }
        )

    def _capture_set_lot_by_removal(self):
        moves = self._capture_document()._capture_moves()
        pending = moves.move_line_ids.filtered(
            lambda ml: (
                ml.product_id == self.product_id
                and ml.location_id == self.location_id
                and ml.lot_id
                and not ml.picked
                and (not self.package_id or ml.package_id == self.package_id)
                and ml.owner_id == self.owner_id
            )
        )
        if pending:
            self.lot_id = pending[:1].lot_id
            return
        quants = self.env["stock.quant"]._gather(self.product_id, self.location_id)
        quant = quants.filtered(
            lambda q: (
                q.lot_id
                and q.available_quantity > 0
                and (not self.package_id or q.package_id == self.package_id)
                and q.owner_id == self.owner_id
            )
        )[:1]
        self.lot_id = quant.lot_id

    def _capture_fill_from_stock_active(self):
        return self.profile_id.fill_from_stock and self.capture_kind != "incoming"

    def _capture_quant_domain(self, product=None, lot=None):
        domain = [("location_id.usage", "=", "internal")]
        if product:
            domain.append(("product_id", "in", product.ids))
        if lot:
            domain.append(("lot_id", "in", lot.ids))
        if self.location_id and self.location_id.usage == "internal":
            domain.append(("location_id", "=", self.location_id.id))
        else:
            sources = self._capture_document()._capture_source_locations()
            if sources:
                domain.append(("location_id", "child_of", sources.ids))
            else:
                domain.append(("company_id", "=", self.env.company.id))
        if self.package_id:
            domain.append(("package_id", "=", self.package_id.id))
        if self.owner_id:
            domain.append(("owner_id", "=", self.owner_id.id))
        return domain

    def _capture_fill_from_quants(self, quants):
        """Fill the values common to the quants of the stock read"""
        ignore_location = self.env.context.get(
            "capture_ignore_quant_location", self.profile_id.ignore_quant_location
        )
        location_field = self.profile_id._get_field("location_id")
        if len(quants.product_id) == 1 and self.product_id != quants.product_id:
            self._capture_set_product(quants.product_id)
        if len(quants.package_id) == 1 and all(q.package_id for q in quants):
            self.package_id = quants.package_id
            if len(quants) == 1:
                self.result_package_id = quants.package_id
        if len(quants.lot_id) == 1 and all(q.lot_id for q in quants):
            self.lot_id = quants.lot_id
        if len(quants.owner_id) == 1:
            self.owner_id = quants.owner_id
        if (
            not ignore_location
            and len(quants.location_id) == 1
            and self.capture_kind != "incoming"
            and not (location_field.forced and len(quants) == 1)
            and (len(quants) == 1 or not self.location_id)
        ):
            self.write(
                {"location_id": quants.location_id.id, "location_from_user": False}
            )
        if (
            len(quants) == 1
            and self.profile_id.quantity_from_stock
            and not self.env.context.get("capture_skip_stock_quantity")
            and not self._capture_quantity_set_by_user()
        ):
            self.uom_id = quants.product_id.uom_id
            self.quantity = quants.quantity

    # Lots

    def _capture_can_create_lot(self):
        return (
            self.profile_id.create_lot
            or self._capture_document()._capture_can_create_lot(self.product_id)
        )

    def _capture_lot(self, create=False):
        """Lot of the lot name read, created when allowed"""
        if not self.lot_name or not self.product_id:
            return self.env["stock.lot"]
        lot = self.env["stock.lot"].search(
            [("name", "=", self.lot_name), ("product_id", "=", self.product_id.id)],
            limit=1,
        )
        if not lot and (create or self._capture_can_create_lot()):
            lot = self.env["stock.lot"].create(self._capture_lot_values())
        return lot

    def _capture_lot_values(self):
        """Values of a lot created from the lot name read"""
        return {
            "name": self.lot_name,
            "product_id": self.product_id.id,
            "company_id": (self.company_id or self.env.company).id,
        }

    # Capture

    def _capture_quantity_in_product_uom(self):
        uom = self.uom_id or self.product_id.uom_id
        return uom._compute_quantity(self.quantity, self.product_id.uom_id, round=False)

    def _capture_characteristics(self):
        """Arguments of the engine for the reading"""
        document = self._capture_document()
        location_dest = self.location_dest_id
        if location_dest and location_dest in document._capture_dest_locations():
            # The generic destination keeps the putaway planned on the lines
            location_dest = None
        result_package = self.result_package_id or None
        if (
            self.package_id
            and not result_package
            and self.product_id.uom_id.compare(
                sum(
                    self.package_id.quant_ids.filtered(
                        lambda q: (
                            q.product_id == self.product_id
                            and (not self.lot_id or q.lot_id == self.lot_id)
                        )
                    ).mapped("quantity")
                ),
                self._capture_quantity_in_product_uom(),
            )
            <= 0
        ):
            # The whole package is read: it moves as it is
            result_package = self.package_id
        lot = None
        if self.product_id.tracking:
            lot = self.lot_id or self._capture_lot()
        return {
            "quantity": self.quantity,
            "uom": self.uom_id or self.product_id.uom_id,
            "lot": lot,
            "location": self.location_id or None,
            "package": self.package_id or None,
            "owner": self.owner_id or None,
            "result_package": result_package,
            "location_dest": location_dest or None,
        }

    def _capture_available(self):
        """Stock of the product read in the source location, less what the
        document already captured from it"""
        if not self.product_id or self.location_id.usage != "internal":
            return 0.0
        domain = [
            ("product_id", "=", self.product_id.id),
            ("location_id", "child_of", self.location_id.id),
        ]
        if self.lot_id:
            domain.append(("lot_id", "=", self.lot_id.id))
        if self.owner_id:
            domain.append(("owner_id", "=", self.owner_id.id))
        [[quantity]] = self.env["stock.quant"]._read_group(
            domain, aggregates=["quantity:sum"]
        )
        moves = self._capture_document()._capture_moves()
        captured = moves.move_line_ids.filtered(
            lambda ml: (
                ml.picked
                and ml.product_id == self.product_id
                and ml.location_id._child_of(self.location_id)
                and (not self.lot_id or ml.lot_id == self.lot_id)
            )
        )
        return (quantity or 0.0) - sum(captured.mapped("quantity_product_uom"))

    def _capture_check_conditions(self):
        if not self.location_id and self.capture_kind != "incoming":
            self.product_id = False
            return self._capture_fail(self.env._("Waiting location"), "info")
        if not self.product_id:
            return self._capture_fail(self.env._("Waiting product"), "info")
        if self.product_id.tracking and not self.lot_id and not self.lot_name:
            return self._capture_fail(self.env._("Waiting lot"), "info")
        if not self.quantity and self.capture_kind != "inventory":
            return self._capture_fail(self.env._("Waiting quantities"), "info")
        if self.guided and not self._capture_check_guided():
            return False
        limit = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_float("stock_capture.limit_product_qty", 999999.0)
        )
        if self.quantity > limit:
            # A barcode read into the quantity field
            return self._capture_fail(self.env._("The quantity is huge"))
        return True

    def _capture_check_guided(self):
        card = self.card_line_id or self.card_move_id
        if not card:
            return True
        card_line = self.card_line_id
        checks = [
            (
                "product_id",
                card.product_id,
                self.product_id,
                self.env._("Wrong product"),
            ),
            (
                "location_id",
                card_line.location_id if card_line else self.location_id,
                self.location_id,
                self.env._("Wrong location"),
            ),
            (
                "location_dest_id",
                card.location_dest_id,
                self.location_dest_id,
                self.env._("Wrong location dest"),
            ),
        ]
        if card.product_id.tracking and card_line:
            checks.append(
                ("lot_id", card_line.lot_id, self.lot_id, self.env._("Wrong lot"))
            )
        for field_name, expected, value, message in checks:
            if value != expected and self.profile_id._get_field(field_name).forced:
                if field_name == "product_id":
                    self.quantity = 0.0
                return self._capture_fail(message)
        return True

    def action_confirm(self):
        """Capture the values read, e.g. when confirmed by hand"""
        self.ensure_one()
        self.feedback_notification = self.feedback_focus = False
        self.feedback_sound = "ok"
        self.barcode = False
        result = self._capture_confirm()
        self._capture_feedback(
            sound=self.feedback_sound,
            focus=self.feedback_focus,
            notification=self.feedback_notification,
        )
        return result if isinstance(result, dict) else True

    def action_force(self):
        """Capture the last reading although it is over the demand"""
        self.force_visible = False
        return self.with_context(capture_force=True).action_confirm()

    def _capture_confirm(self):
        if not self._capture_check_required():
            self.feedback_sound = "ko"
            return False
        manual = self.manual_entry
        if not self.quantity and not self.manual_quantity and not manual:
            self.quantity = 1.0
        if not self._capture_check_conditions():
            return False
        document = self._capture_document()
        target = document._capture_document_for(self)
        if not target:
            return document._capture_check(self)
        switched = target != document
        if switched:
            self._capture_switch_document(target)
            document = target
        if not document._capture_check(self):
            return False
        records = document._capture_apply(self)
        if not records:
            if self.message_type == "success":
                self._capture_fail(self.env._("Product not demanded"))
            self.feedback_sound = "ko"
            return False
        self.force_visible = False
        self._capture_after_capture(records)
        if manual:
            self._capture_message(self.env._("Manual entry OK"), "success")
        if switched:
            # The screen shows the transfer found from the product
            return self._capture_action()
        return records

    def _capture_after_capture(self, records):
        """Hook after a reading is captured (labels, sounds...)"""
        self._capture_message(
            self.env._(
                "%(quantity)s %(uom)s of %(product)s",
                quantity=formatLang(self.env, self.quantity, dp="Product Unit"),
                uom=(self.uom_id or self.product_id.uom_id).name,
                product=self.product_id.display_name,
            ),
            "success",
        )
        keep = (
            self.profile_id.keep_screen_values
            and (self.card_line_id or self.card_move_id)
            and not self._capture_card_done(self.card_line_id or self.card_move_id)
        )
        if not keep:
            self._capture_clean_values()
        self._capture_refresh()

    def _capture_clean_values(self):
        for field in self.profile_id.field_ids.filtered("clean_after_done"):
            if field.field_name == "result_package_id" and self.keep_result_package:
                continue
            if field.field_name in self._fields:
                self[field.field_name] = False
        self.quantity = 0.0
        self.lot_name = False
        self.packaging_id = False
        self.edit_quant_id = False
        self.manual_entry = self.profile_id.manual_entry
        self.force_visible = False

    # Cards

    def _capture_card_location_field(self):
        field = self.profile_id.location_field_to_sort
        if not field:
            field = (
                "location_dest_id"
                if self.capture_kind in ("incoming", "internal")
                else "location_id"
            )
        return field

    def _capture_sort_cards(self, records):
        field = self._capture_card_location_field()

        def key(record):
            location = (
                record.move_line_ids[:1] or record
                if record._name == "stock.move"
                else record
            )[field]
            return location.complete_name or ""

        return records.sorted(key)

    def _capture_card_done(self, card):
        if card._name == "stock.move":
            return card.capture_state == "captured" or card.state in ("done", "cancel")
        if card._name == "stock.move.line":
            return card.picked or card.state in ("done", "cancel")
        return False

    def _capture_card_group_key(self, line):
        profile = self.profile_id
        if profile.card_group == "location_product":
            return (line.location_id, line.product_id)
        if profile.card_group == "expression" and profile.card_group_expression:
            key = safe_eval(profile.card_group_expression, {"object": line})
            return tuple(key) if isinstance(key, (list, tuple)) else (key,)
        return line

    def _capture_cards_of_document(self):
        """Pending and captured cards of the document"""
        document = self._capture_document()
        Move, Line = self.env["stock.move"], self.env["stock.move.line"]
        if not document:
            return Move, Line
        moves = document._capture_moves().filtered(
            lambda move: (
                move.state not in ("draft", "cancel")
                or (move.state == "draft" and self.capture_kind == "incoming")
            )
        )
        if self.card_source == "move":
            return self._capture_sort_cards(moves), Line
        lines = self._capture_sort_cards(moves.move_line_ids)
        # Demand not reserved is a card of its operation
        unreserved = moves.filtered(
            lambda move: (
                self.capture_kind != "incoming"
                and move.state not in ("done", "cancel")
                and move.capture_backorder_action == "pending"
                and move.uom_id.compare(
                    move.product_uom_qty,
                    sum(
                        ml.uom_id._compute_quantity(ml.quantity, move.uom_id)
                        for ml in move.move_line_ids
                    ),
                )
                > 0
            )
        )
        return unreserved, lines

    @api.depends("card_filter", "res_model", "res_id", "card_move_id", "card_line_id")
    def _compute_cards(self):
        for session in self:
            if session.capture_kind == "inventory":
                session.card_move_ids = session.card_line_ids = False
                session.card_quant_ids = session._capture_quant_cards()
                session.card_count = len(
                    session.env["stock.quant"].search(
                        session._capture_document()._capture_counted_quants_domain()
                    )
                )
                continue
            session.card_quant_ids = False
            moves, lines = session._capture_cards_of_document()
            card_filter = session.card_filter
            if card_filter == "none":
                moves, lines = moves.browse(), lines.browse()
            elif card_filter in ("pending", "done"):
                done = card_filter == "done"
                moves = moves.filtered(
                    lambda m, s=session, d=done: s._capture_card_done(m) == d
                )
                lines = lines.filtered(
                    lambda ml, s=session, d=done: s._capture_card_done(ml) == d
                )
            if session.profile_id.card_group:
                grouped = {}
                for line in lines:
                    grouped.setdefault(session._capture_card_group_key(line), line)
                lines = lines.browse([line.id for line in grouped.values()])
            session.card_move_ids = moves
            session.card_line_ids = lines
            session.card_count = len(moves) + len(lines)

    def _capture_quant_cards(self):
        location = self._capture_document()
        counted = self.card_filter != "pending"
        quants = self.env["stock.quant"].search(
            location._capture_counted_quants_domain(counted=counted),
            order="write_date desc" if counted else None,
        )
        if not counted:
            quants = quants.sorted(lambda q: q.location_id.complete_name or "")
        return quants

    @api.depends("res_model", "res_id", "show_detailed_operations")
    def _compute_captured_line_ids(self):
        for session in self:
            if not session.show_detailed_operations or session.capture_kind == (
                "inventory"
            ):
                session.captured_line_ids = False
                continue
            moves = session._capture_document()._capture_moves()
            session.captured_line_ids = moves.move_line_ids.filtered("picked").sorted(
                lambda ml: ml.write_date, reverse=True
            )

    @api.depends("product_id", "uom_id", "res_model", "res_id")
    def _compute_product_totals(self):
        for session in self:
            demand = captured = 0.0
            if session.product_id and session.capture_kind != "inventory":
                uom = session.uom_id or session.product_id.uom_id
                moves = (
                    session._capture_document()
                    ._capture_moves()
                    .filtered(
                        lambda m, s=session: (
                            m.product_id == s.product_id and m.state != "cancel"
                        )
                    )
                )
                demand = sum(
                    m.uom_id._compute_quantity(m.product_uom_qty, uom, round=False)
                    for m in moves
                )
                captured = sum(
                    m.uom_id._compute_quantity(m.captured_quantity, uom, round=False)
                    for m in moves
                )
            session.product_demand = demand
            session.product_captured = captured

    @api.depends("product_id", "location_id", "lot_id", "owner_id", "package_id")
    def _compute_product_available(self):
        Quant = self.env["stock.quant"]
        for session in self:
            if not session.product_id or not session.location_id:
                session.product_available = 0.0
                continue
            session.product_available = Quant._get_available_quantity(
                session.product_id,
                session.location_id,
                lot_id=session.lot_id or None,
                package_id=session.package_id or None,
                owner_id=session.owner_id or None,
                allow_negative=True,
            )

    @api.model
    def _capture_from_context(self):
        """Session of the screen a card action comes from"""
        session_id = self.env.context.get("capture_session_id")
        return self.browse(session_id).exists() if session_id else self.browse()

    @api.model
    def _capture_refresh_from_context(self):
        session = self._capture_from_context()
        if session:
            session._capture_refresh()
            session._capture_feedback()

    @api.depends("product_id", "res_model", "res_id")
    def _compute_product_outgoing_qty(self):
        for session in self:
            warehouses = session._capture_warehouses()
            session.product_outgoing_qty = (
                session.product_id.with_context(
                    warehouse_id=warehouses.ids
                ).outgoing_qty
                if session.product_id
                else 0.0
            )

    @api.depends("product_id", "res_model", "res_id")
    def _compute_location_stock_count(self):
        Quant = self.env["stock.quant"]
        for session in self:
            if not session.product_id:
                session.location_stock_count = 0
                continue
            groups = Quant._read_group(
                [
                    ("product_id", "=", session.product_id.id),
                    (
                        "location_id",
                        "child_of",
                        session._capture_warehouses().view_location_id.ids,
                    ),
                    ("location_id.usage", "=", "internal"),
                ],
                ["location_id"],
                ["quantity:sum"],
            )
            uom = session.product_id.uom_id
            session.location_stock_count = sum(
                1 for _location, quantity in groups if uom.compare(quantity, 0) > 0
            )

    def _capture_warehouses(self):
        """Warehouses of the document, all of the company if it has none"""
        locations = (
            self._capture_document()._capture_source_locations()
            | self._capture_document()._capture_dest_locations()
        )
        warehouses = locations.warehouse_id
        return warehouses or self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)]
        )

    def _capture_refresh(self):
        """Recompute the step and, in guided mode, the current card"""
        self.invalidate_recordset(["card_move_ids", "card_line_ids", "card_count"])
        if self.guided and self.capture_kind != "inventory":
            current = self.card_line_id or self.card_move_id
            if not current or self._capture_card_done(current):
                self._capture_set_card(self._capture_next_pending_card())
        self._capture_update_step()

    def _capture_pending_cards(self):
        moves, lines = self._capture_cards_of_document()
        cards = [line for line in lines if not self._capture_card_done(line)]
        cards += [move for move in moves if not self._capture_card_done(move)]
        return cards

    def _capture_next_pending_card(self):
        cards = self._capture_pending_cards()
        return cards[0] if cards else None

    def _capture_set_card(self, card):
        """Make the card the current one, filling the fields by default from
        it"""
        self.card_line_id = card if card and card._name == "stock.move.line" else False
        self.card_move_id = card if card and card._name == "stock.move" else False
        if card:
            self._capture_fill_from_card(card)

    def _capture_fill_from_card(self, card, all_fields=False):
        self._capture_fill_values_from_card(card, all_fields=all_fields)
        if self.capture_kind == "incoming":
            self._capture_propose_location_dest(defaults=card.location_dest_id)

    def _capture_fill_values_from_card(self, card, all_fields=False):
        for field_name in CARD_FIELDS:
            if field_name == "result_package_id" and self.keep_result_package:
                continue
            option = self.profile_id._get_field(field_name)
            if not (all_fields or option.filled_default):
                if option.clean_after_done and not self.env.context.get(
                    "capture_keep_values"
                ):
                    self[field_name] = False
                continue
            if field_name in card._fields:
                self[field_name] = card[field_name]
            elif field_name in ("location_id", "location_dest_id"):
                self[field_name] = (card.move_line_ids[:1] or card)[field_name]
        self.location_from_user = False
        if card.product_id:
            self.uom_id = card.product_id.uom_id
        quantity_option = self.profile_id._get_field("quantity")
        if all_fields or quantity_option.filled_default:
            self.quantity = self._capture_card_pending_quantity(card)
        elif not self.force_visible:
            self.quantity = 0.0

    def _capture_card_pending_quantity(self, card):
        if card._name == "stock.move.line":
            if card.picked:
                return 0.0
            return card.uom_id._compute_quantity(
                card.quantity, card.product_id.uom_id, round=False
            )
        return card.uom_id._compute_quantity(
            max(card.product_uom_qty - card.captured_quantity, 0.0),
            card.product_id.uom_id,
            round=False,
        )

    def _capture_move_card(self, offset):
        cards = self._capture_pending_cards()
        if not cards:
            return
        current = self.card_line_id or self.card_move_id
        index = cards.index(current) if current in cards else -offset
        self._capture_set_card(cards[(index + offset) % len(cards)])
        self._capture_update_step()

    def action_next_card(self):
        self._capture_move_card(1)
        return True

    def action_previous_card(self):
        self._capture_move_card(-1)
        return True

    def action_select_card(self, model, record_id):
        """Fill the screen from a card, e.g. to edit or confirm it"""
        card = self.env[model].browse(record_id).exists()
        if not card:
            return True
        if self.profile_id.manual_entry_on_edit:
            self.manual_entry = True
            if self.profile_id.manual_entry_focus_field:
                self._capture_focus(self.profile_id.manual_entry_focus_field)
        if card._name == "stock.quant":
            self.write(
                {
                    "location_id": card.location_id.id,
                    "product_id": card.product_id.id,
                    "uom_id": card.product_id.uom_id.id,
                    "lot_id": card.lot_id.id,
                    "package_id": card.package_id.id,
                    "owner_id": card.owner_id.id,
                    "quantity": card.inventory_quantity,
                    "edit_quant_id": card.id,
                    "manual_entry": True,
                }
            )
        else:
            if self.guided:
                self.card_line_id = card if card._name == "stock.move.line" else False
                self.card_move_id = card if card._name == "stock.move" else False
            self._capture_fill_from_card(card, all_fields=True)
            if not self.profile_id._get_field("quantity").filled_default:
                self.quantity = 0.0
        self._capture_update_step()
        self._capture_feedback(focus=self.feedback_focus or "quantity")
        return True

    # Buttons

    def action_clean(self):
        self._capture_clean_values()
        self.write(
            {
                "product_id": False,
                "lot_id": False,
                "package_id": False,
                "quantity": 0.0,
                "manual_entry": self.profile_id.manual_entry,
            }
        )
        self._capture_update_step()
        return True

    def action_clean_product(self):
        self.write({"product_id": False, "packaging_id": False, "quantity": 0.0})
        self._capture_update_step()
        return True

    def action_clean_lot(self):
        self.write({"lot_id": False, "lot_name": False})
        self._capture_update_step()
        return True

    def action_clean_package(self):
        self.write({"package_id": False, "result_package_id": False})
        self._capture_update_step()
        return True

    def action_create_package(self):
        self.result_package_id = self.env["stock.package"].create({})
        return True

    def action_toggle_keep_result_package(self):
        self.keep_result_package = not self.keep_result_package
        return True

    def action_manual_entry(self):
        self.manual_entry = not self.manual_entry
        if self.manual_entry and self.profile_id.manual_entry_focus_field:
            self._capture_feedback(focus=self.profile_id.manual_entry_focus_field)
        return True

    def action_toggle_detailed_operations(self):
        self.show_detailed_operations = not self.show_detailed_operations
        return True

    def action_toggle_card_filter(self):
        """Switch between the pending and the captured cards"""
        self.card_filter = "done" if self.card_filter == "pending" else "pending"
        return True

    def action_open_document(self):
        return self._capture_document().get_record_default_action()

    def action_put_in_pack(self):
        document = self._capture_document()
        if document._name == "stock.picking":
            return document.action_put_in_pack()
        return True

    def action_validate(self):
        self.ensure_one()
        result = self._capture_document()._capture_validate(self)
        if result is False:
            self._capture_feedback(sound="ko")
            return True
        return result

    def _capture_after_validate(self):
        """Action once the document is validated: the ready transfers of its
        operation type"""
        document = self._capture_document()
        action = document._capture_done_action(self)
        if action:
            return action
        picking_type = (
            document.picking_type_id
            if "picking_type_id" in document._fields
            else self.env["stock.picking.type"]
        )
        if picking_type:
            return picking_type.get_action_picking_tree_ready()
        return {"type": "ir.actions.act_window_close"}

    def action_assign_serials(self):
        """Enter the serial numbers of the product read in the detailed
        operations of its operation (e.g. with the generate serials tool).
        The lines getting a serial number are captured."""
        self.ensure_one()
        moves = (
            self._capture_document()
            ._capture_moves()
            .filtered(
                lambda m: (
                    m.product_id == self.product_id
                    and m.state not in ("draft", "done", "cancel")
                )
            )
        )
        if not moves:
            raise UserError(self.env._("No pending operations for this product"))
        move = (
            moves.filtered(lambda m: m.move_line_ids.filtered(lambda ml: not ml.picked))
            or moves
        )[:1]
        action = move.action_show_details()
        action["context"] = dict(
            action.get("context") or {},
            capture_session_id=self.id,
            capture_pick_with_lot=True,
        )
        return action

    def action_new_packaging(self):
        """Register the barcode of a packaging of the product read"""
        self.ensure_one()
        wizard = self.env["stock.capture.new.packaging"].create(
            {"session_id": self.id, "product_id": self.product_id.id}
        )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("New packaging"),
            "res_model": wizard._name,
            "res_id": wizard.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
        }

    # Stock by location

    def _capture_location_stock_field(self):
        """Field filled by a location chosen from the stock of the product"""
        return self.env.context.get(
            "capture_location_field",
            "location_dest_id" if self.capture_kind == "incoming" else "location_id",
        )

    def _capture_location_stock_reversed(self):
        """Receipts list first the locations emptied last"""
        return self.env.context.get(
            "capture_location_reverse", self.capture_kind == "incoming"
        )

    def _capture_location_stock_parents(self):
        document = self._capture_document()
        if self._capture_location_stock_field() == "location_dest_id":
            locations = document._capture_dest_locations()
        else:
            locations = document._capture_source_locations()
        return (
            locations
            or self.env["stock.warehouse"]
            .search([("company_id", "=", self.env.company.id)])
            .view_location_id
        )

    def _capture_location_stock(self):
        """(location, quantity) of the locations with stock of the product, in
        removal strategy order (reversed for receipts)"""
        Quant = self.env["stock.quant"]
        quants = Quant.browse()
        for location in self._capture_location_stock_parents():
            quants |= Quant._gather(self.product_id, location)
        quants = quants.filtered(lambda q: q.location_id.usage == "internal")
        quantities = defaultdict(float)
        for quant in quants:
            quantities[quant.location_id] += quant.quantity
        locations = quants.location_id
        if self._capture_location_stock_reversed():
            locations = locations[::-1]
        return [
            (location, quantities[location])
            for location in locations
            if self.product_id.uom_id.compare(quantities[location], 0) > 0
        ]

    def action_product_info(self):
        return self._capture_product_info_action(self.env._("Product information"))

    def action_select_location(self):
        return self._capture_product_info_action(
            self.env._("Select location"), show_product_info=False
        )

    def _capture_product_info_action(self, name, show_product_info=True):
        self.ensure_one()
        info = self.env["stock.capture.product.info"].create(
            self._capture_product_info_values(show_product_info)
        )
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": info._name,
            "res_id": info.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
        }

    def _capture_product_info_values(self, show_product_info=True):
        product = self.product_id.with_context(
            location=self._capture_location_stock_parents().ids
        )
        return {
            "session_id": self.id,
            "location_field": self._capture_location_stock_field(),
            "product_id": self.product_id.id,
            "show_product_info": show_product_info,
            "qty_available": product.qty_available,
            "incoming_qty": product.incoming_qty,
            "outgoing_qty": product.outgoing_qty,
            "virtual_available": product.virtual_available,
            "line_ids": [
                fields.Command.create(
                    {"sequence": sequence, "location_id": location.id, "quantity": qty}
                )
                for sequence, (location, qty) in enumerate(
                    self._capture_location_stock()
                )
            ],
        }

    def _capture_set_location(self, field_name, location):
        self[field_name] = location
        if (
            field_name == "location_id"
            and self.profile_id.auto_lot
            and self.product_id.tracking
        ):
            self._capture_set_lot_by_removal()
        self._capture_update_step()
