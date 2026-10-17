# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class StockCaptureProfile(models.Model):
    _name = "stock.capture.profile"
    _description = "Behaviour of the capture screens"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    field_ids = fields.One2many(
        comodel_name="stock.capture.profile.field",
        inverse_name="profile_id",
        string="Steps to capture",
        copy=True,
    )
    guided = fields.Boolean(
        string="Guided mode",
        help="The screen proposes one pending operation at a time and rejects "
        "a product, lot or location different from the expected one when its "
        "field is forced. Otherwise barcodes can be read in any order.",
    )
    manual_entry = fields.Boolean(
        help="Open the screen in manual entry mode, with the fields editable "
        "and each reading confirmed from a button.",
    )
    manual_entry_on_edit = fields.Boolean(
        help="Switch to manual entry when a pending operation is edited, so "
        "its values can be changed before confirming.",
    )
    manual_entry_focus_field = fields.Char(
        default="location_id",
        help="Technical name of the field that gets the focus when switching "
        "to manual entry (e.g. location_id or quantity).",
    )
    capture_unreserved = fields.Boolean(
        string="Capture unreserved operations",
        help="Capture on operations without reservation too.",
    )
    card_source = fields.Selection(
        [("move_line", "Detailed operations"), ("move", "Operations")],
        string="Pending cards",
        default="move_line",
        required=True,
        help="Records shown as pending cards and followed in guided mode.",
    )
    card_group = fields.Selection(
        [("location_product", "Location and product"), ("expression", "Expression")],
        string="Group cards by",
        help="Show one pending card per group of detailed operations, e.g. "
        "the lots of a product in a location.",
    )
    card_group_expression = fields.Char(
        help="Python expression giving the key of the group of a detailed "
        "operation, available as object, e.g. "
        "object.location_id, object.product_id, object.package_id",
    )
    card_filter = fields.Selection(
        [
            ("none", "None"),
            ("pending", "Pending"),
            ("done", "Captured"),
            ("all", "All"),
        ],
        string="Cards shown",
        default="pending",
        required=True,
        help="Cards listed when the screen is opened. Inventories show the "
        "counted items or the pending ones.",
    )
    ignore_filled_fields = fields.Boolean(
        help="Skip the required fields that already have a value when reading "
        "a barcode, so it is matched against the next fields of the step (e.g. "
        "a second location barcode sets the destination once the source is "
        "filled).",
    )
    auto_put_in_pack = fields.Boolean(
        help="When a transfer is validated and none of its detailed operations "
        "has a destination package, put them in a new package.",
    )
    manual_quantity = fields.Boolean(
        help="The quantity is always typed by the operator: readings do not set it.",
    )
    manual_confirm = fields.Boolean(
        help="Readings only fill the screen and each one is confirmed with the "
        "Confirm button, instead of being captured as soon as the required "
        "fields are filled.",
    )
    accumulate_read_quantity = fields.Boolean(
        string="Accumulate repeated readings",
        help="With manual confirmation, reading the same product, lot or "
        "packaging again before confirming adds one more unit (or packaging) "
        "to the quantity to confirm.",
    )
    replace_quantity = fields.Boolean(
        string="Replace quantity on each reading",
        help="A confirmed reading replaces the quantity already captured "
        "instead of being added to it: the done quantity of the detailed "
        "operation in transfers and the counted quantity in inventories.",
    )
    allow_negative_quant = fields.Boolean(
        help="Capture quantities that are not available in the location, "
        "leaving negative stock.",
    )
    allow_over_demand = fields.Boolean(
        help="Capture quantities over the demand without asking for confirmation.",
    )
    allow_not_demanded_product = fields.Boolean(
        help="Accept products that are not in the transfer, adding an "
        "operation for them. Otherwise they are rejected as not demanded.",
    )
    fill_from_stock = fields.Boolean(
        string="Fill fields from stock",
        help="When a lot or a product is read, fill the product, lot, package, "
        "owner and location from its stock (only the values common to all its "
        "quants). A lot without stock is rejected unless negative stock is "
        "allowed. Not applied on receipts.",
    )
    quantity_from_stock = fields.Boolean(
        default=True,
        help="Reading a lot or a package proposes its quantity in stock.",
    )
    ignore_quant_location = fields.Boolean(
        help="When the fields are filled from the stock of a lot or package, "
        "keep the location of the screen instead of taking the stock location.",
    )
    auto_lot = fields.Boolean(
        string="Get lots automatically",
        help="When a tracked product is read, set the lot already reserved for "
        "it in the location or, if none, the first available lot by removal "
        "strategy. Not applied on receipts.",
    )
    create_lot = fields.Boolean(
        string="Create lots if not match",
        help="Accept a lot name that does not exist yet.",
    )
    keep_screen_values = fields.Boolean(
        help="Keep the values of the screen until the pending card is completed.",
    )
    propose_location_dest = fields.Boolean(
        string="Propose destination from stock",
        help="Receipts: propose as destination the location where the product "
        "read has most stock, unless the user chose another one or the "
        "destination is forced. A product without stock leaves the "
        "destination empty to be read.",
    )
    use_location_dest_putaway = fields.Boolean(
        string="Use destination putaway",
        help="When the destination location is required and empty, compute it "
        "with the putaway strategy of the transfer destination.",
    )
    show_fixed_location_dest = fields.Boolean(
        string="Show fixed destination",
        help="Read the destination already planned on the detailed operation, "
        "without recomputing the putaway strategy: it is shown on the pending "
        "cards when the putaway is fixed (destination without storage "
        "category), and a read product keeps that destination instead of "
        "getting a new line at the generic destination of the transfer.",
    )
    location_field_to_sort = fields.Selection(
        [
            ("location_id", "Source Location"),
            ("location_dest_id", "Destination Location"),
        ],
        help="Location used to sort the pending cards (by name). If empty, the "
        "destination is used for receipts and internal transfers and the source "
        "for the rest.",
    )
    search_picking_from_product = fields.Selection(
        [("first", "First transfer"), ("last", "Last transfer")],
        help="When the screen is opened from an operation type, without a "
        "transfer, reading a product opens the first or last ready transfer of "
        "that type with an operation for the product.",
    )
    show_detailed_operations = fields.Boolean(
        help="List the captured detailed operations on the screen.",
    )
    show_stock = fields.Boolean(
        help="Show the quantity of the product available in the location.",
    )
    show_owner = fields.Boolean(help="Show the owner field.")
    show_form_scan = fields.Boolean(
        default=True,
        help="Keep the reading fields always visible. Otherwise they are only "
        "shown in manual entry.",
    )
    display_notification = fields.Boolean(
        string="Display notifications",
        help="Show a notification when a reading cannot be captured because a "
        "required field is empty.",
    )

    def _get_field(self, field_name):
        return self.field_ids.filtered(lambda f: f.field_name == field_name)[:1]


class StockCaptureProfileField(models.Model):
    _name = "stock.capture.profile.field"
    _description = "Field of a capture profile: when and how it is read"
    _order = "step, sequence, id"

    sequence = fields.Integer(default=100)
    name = fields.Char(required=True, translate=True)
    profile_id = fields.Many2one(
        comodel_name="stock.capture.profile", required=True, ondelete="cascade"
    )
    field_name = fields.Selection(
        [
            ("location_id", "Source Location"),
            ("location_dest_id", "Destination Location"),
            ("product_id", "Product"),
            ("packaging_id", "Packaging"),
            ("lot_id", "Lot/Serial Number"),
            ("lot_name", "Lot/Serial Number Name"),
            ("package_id", "Package"),
            ("result_package_id", "Destination Package"),
            ("owner_id", "Owner"),
            ("quantity", "Quantity"),
        ],
        required=True,
    )
    step = fields.Integer(
        help="Order in which the fields are asked. Only the fields to scan of "
        "the current step are matched against a barcode."
    )
    to_scan = fields.Boolean(
        help="The field can be filled by reading a barcode in its step."
    )
    required = fields.Boolean(
        help="A reading is not captured while the field is empty. The step of "
        "the first empty required field is the current step of the screen."
    )
    filled_default = fields.Boolean(
        help="Fill the field with the value of the pending card (guided mode) "
        "or of the document when the screen is opened."
    )
    forced = fields.Boolean(
        help="Guided mode: reject a value different from the one of the pending card."
    )
    clean_after_done = fields.Boolean(
        help="Empty the field after each captured reading."
    )
