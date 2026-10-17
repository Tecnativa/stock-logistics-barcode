# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import logging

_logger = logging.getLogger(__name__)


def pre_init_hook(env):
    """Create the capture state column so it isn't computed for every move"""
    env.cr.execute(
        "ALTER TABLE stock_move ADD COLUMN IF NOT EXISTS capture_state VARCHAR"
    )
    # Instant default for the existing moves instead of writing it on each one
    env.cr.execute(
        """ALTER TABLE stock_move ADD COLUMN IF NOT EXISTS capture_backorder_action
        VARCHAR DEFAULT 'pending'"""
    )


def _column_exists(cr, table, column):
    cr.execute(
        """SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s""",
        (table, column),
    )
    return bool(cr.fetchone())


def _capture_read_quantities(env):
    """Up to 18.0 the quantities read or weighed on pending detailed operations
    were their qty_picked (stock_move_line_qty_picked), and stock_barcodes kept
    what to do with the rest of each operation. Capture them now."""
    cr = env.cr
    if _column_exists(cr, "stock_move", "barcode_backorder_action"):
        cr.execute(
            """UPDATE stock_move SET capture_backorder_action = barcode_backorder_action
            WHERE barcode_backorder_action IS NOT NULL
            AND state NOT IN ('done', 'cancel')"""
        )
    if not _column_exists(cr, "stock_move_line", "qty_picked"):
        return
    cr.execute(
        """SELECT sml.id, sml.qty_picked
        FROM stock_move_line sml
        JOIN stock_move sm ON sm.id = sml.move_id
        WHERE sm.state NOT IN ('draft', 'done', 'cancel') AND sml.qty_picked > 0"""
    )
    rows = cr.fetchall()
    _logger.info("Capturing the quantities read of %s detailed operations", len(rows))
    lines = env["stock.move.line"].browse([row[0] for row in rows])
    for line, (_line_id, qty_picked) in zip(lines, rows, strict=True):
        line._capture_set_quantity(qty_picked)
    env.flush_all()


def post_init_hook(env):
    """Compute the capture state of the pending moves only"""
    _capture_read_quantities(env)
    _logger.info("Computing the capture state of pending moves...")
    env["stock.move"].search(
        [("state", "not in", ("draft", "done", "cancel"))]
    )._compute_capture_state()
