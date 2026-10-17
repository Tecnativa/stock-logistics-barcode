# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""The barcode option groups of 18.0 become capture profiles of stock_capture.

Their steps are kept for the fields the screens read in 20.0; fields added by
other modules (e.g. a secondary unit) are migrated by those modules.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

# 18.0 option group column: (profile field, conversion)
GROUP_FIELDS = {
    "barcode_guided_mode": ("guided", lambda value: value == "guided"),
    "manual_entry": ("manual_entry", bool),
    "manual_entry_on_edit": ("manual_entry_on_edit", bool),
    "manual_entry_field_focus": (
        "manual_entry_focus_field",
        lambda value: {"product_qty": "quantity"}.get(value, value),
    ),
    "confirmed_moves": ("capture_unreserved", bool),
    "source_pending_moves": (
        "card_source",
        lambda value: "move" if value == "move_ids" else "move_line",
    ),
    "ignore_filled_fields": ("ignore_filled_fields", bool),
    "auto_put_in_pack": ("auto_put_in_pack", bool),
    "is_manual_qty": ("manual_quantity", bool),
    "is_manual_confirm": ("manual_confirm", bool),
    "allow_negative_quant": ("allow_negative_quant", bool),
    "fill_fields_from_lot": ("fill_from_stock", bool),
    "ignore_quant_location": ("ignore_quant_location", bool),
    "auto_lot": ("auto_lot", bool),
    "create_lot": ("create_lot", bool),
    "show_detailed_operations": ("show_detailed_operations", bool),
    "keep_screen_values": ("keep_screen_values", bool),
    "accumulate_read_quantity": ("accumulate_read_quantity", bool),
    "display_notification": ("display_notification", bool),
    "use_location_dest_putaway": ("use_location_dest_putaway", bool),
    "show_fixed_location_dest": ("show_fixed_location_dest", bool),
    "location_field_to_sort": ("location_field_to_sort", lambda value: value),
    "show_stock": ("show_stock", bool),
    "show_owner": ("show_owner", bool),
    "no_increase_qty_done": ("replace_quantity", bool),
    "show_form_scan": ("show_form_scan", bool),
    "search_picking_from_product": (
        "search_picking_from_product",
        lambda value: value,
    ),
    "allow_not_demanded_product": ("allow_not_demanded_product", bool),
}
OPTION_FIELD_NAMES = {"product_qty": "quantity"}
# Font Awesome icons of the 18.0 tiles: Material Symbols bundled with Odoo
ICONS = {
    "fa-truck": "local_shipping",
    "fa-sign-in": "login",
    "fa-sign-out": "logout",
    "fa-exchange": "sync_alt",
    "fa-random": "swap_horiz",
    "fa-cubes": "inventory_2",
    "fa-cube": "inventory_2",
    "fa-archive": "archive",
    "fa-list": "checklist",
    "fa-check-square-o": "checklist",
    "fa-tags": "label",
    "fa-tag": "label",
    "fa-barcode": "barcode",
    "fa-map-marker": "location_on",
    "fa-print": "print",
    "fa-search": "search",
}


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,)
    )
    return bool(cr.fetchone())


def _column_exists(cr, table, column):
    cr.execute(
        """SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s""",
        (table, column),
    )
    return bool(cr.fetchone())


def _columns(cr, table):
    cr.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
        (table,),
    )
    return {row[0] for row in cr.fetchall()}


def _profile_values(row):
    values = {"name": row["name"] or "Profile"}
    for column, (field, convert) in GROUP_FIELDS.items():
        if column in row and row[column] is not None:
            values[field] = convert(row[column])
    cards = row.get("show_pending_moves")
    values["card_filter"] = cards if cards in ("pending", "all") else "none"
    if row.get("display_read_quant"):
        values["card_filter"] = "done"
    key = (row.get("group_key_for_todo_records") or "").strip()
    if key.replace(" ", "") == "object.location_id,object.product_id":
        values["card_group"] = "location_product"
    elif key:
        values["card_group"] = "expression"
        values["card_group_expression"] = key
    if row.get("code") == "OUT":
        values["quantity_from_stock"] = False
    elif row.get("code") == "REL":
        values["allow_over_demand"] = True
    return values


def _migrate_option_groups(env):
    cr = env.cr
    if not _table_exists(cr, "stock_barcodes_option_group"):
        return {}
    Profile = env["stock.capture.profile"]
    known_fields = dict(
        Profile.env["stock.capture.profile.field"]._fields["field_name"].selection
    )
    cr.execute("SELECT * FROM stock_barcodes_option_group ORDER BY id")
    columns = [desc[0] for desc in cr.description]
    groups = [dict(zip(columns, row, strict=True)) for row in cr.fetchall()]
    profiles = {}
    for group in groups:
        cr.execute(
            """SELECT * FROM stock_barcodes_option
            WHERE option_group_id = %s ORDER BY step, sequence, id""",
            (group["id"],),
        )
        option_columns = [desc[0] for desc in cr.description]
        steps = []
        for option in (
            dict(zip(option_columns, row, strict=True)) for row in cr.fetchall()
        ):
            field_name = OPTION_FIELD_NAMES.get(
                option["field_name"], option["field_name"]
            )
            if field_name not in known_fields:
                _logger.warning(
                    "Option %s of %s reads %s, unknown by the capture profiles",
                    option["name"],
                    group["name"],
                    option["field_name"],
                )
                continue
            steps.append(
                (
                    0,
                    0,
                    {
                        "name": option["name"] or known_fields[field_name],
                        "field_name": field_name,
                        "step": option["step"] or 0,
                        "sequence": option["sequence"] or 100,
                        "to_scan": bool(option["to_scan"]),
                        "required": bool(option["required"]),
                        "filled_default": bool(option["filled_default"]),
                        "forced": bool(option["forced"]),
                        "clean_after_done": bool(option["clean_after_done"]),
                    },
                )
            )
        values = _profile_values(group)
        values["field_ids"] = steps
        profiles[group["id"]] = Profile.create(values)
    _logger.info("%s barcode option groups migrated to capture profiles", len(groups))
    return profiles


def _migrate_picking_types(env, profiles):
    cr = env.cr
    columns = _columns(cr, "stock_picking_type")
    for old, new in (
        ("barcode_option_group_id", "capture_profile_id"),
        ("new_picking_barcode_option_group_id", "capture_new_picking_profile_id"),
    ):
        if old not in columns:
            continue
        cr.execute(
            SQL(
                "SELECT id, %s FROM stock_picking_type WHERE %s IS NOT NULL",
                SQL.identifier(old),
                SQL.identifier(old),
            )
        )
        for type_id, group_id in cr.fetchall():
            if group_id in profiles:
                env["stock.picking.type"].browse(type_id)[new] = profiles[group_id]


def _migrate_actions(env):
    cr = env.cr
    if not _column_exists(cr, "stock_barcodes_action", "icon_class"):
        return
    cr.execute("SELECT id, icon_class FROM stock_barcodes_action")
    for action_id, icon_class in cr.fetchall():
        icon = "barcode"
        for token in (icon_class or "").split():
            icon = ICONS.get(token, icon)
        cr.execute(
            "UPDATE stock_barcodes_action SET icon = %s WHERE id = %s",
            (icon, action_id),
        )
    # The tiles shipped by 18.0 opened lists filtered by a context the counter
    # parsed: they are replaced by the new tiles of 20.0
    for xmlid in (
        "stock_barcodes_action_picking_in",
        "stock_barcodes_action_picking_int",
        "stock_barcodes_action_picking_out",
        "stock_barcodes_action_barcode_operations",
    ):
        record = env.ref(f"stock_barcodes.{xmlid}", raise_if_not_found=False)
        if record and record._name == "stock.barcodes.action":
            record.active = False
    # The inventory tile keeps its identifier and opens the new inventory
    inventory = env.ref(
        "stock_barcodes.stock_barcodes_action_inventory", raise_if_not_found=False
    )
    if inventory and inventory._name == "stock.barcodes.action":
        inventory.write(
            {
                "method": "action_open_inventory",
                "action_window_id": False,
                "context": False,
                "icon": "checklist",
            }
        )


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    profiles = _migrate_option_groups(env)
    _migrate_picking_types(env, profiles)
    _migrate_actions(env)
