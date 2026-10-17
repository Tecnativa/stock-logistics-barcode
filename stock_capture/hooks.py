# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import logging

_logger = logging.getLogger(__name__)


def pre_init_hook(env):
    """Create the capture state column so it isn't computed for every move"""
    env.cr.execute(
        "ALTER TABLE stock_move ADD COLUMN IF NOT EXISTS capture_state VARCHAR"
    )


def post_init_hook(env):
    """Compute the capture state of the pending moves only"""
    _logger.info("Computing the capture state of pending moves...")
    env["stock.move"].search(
        [("state", "not in", ("draft", "done", "cancel"))]
    )._compute_capture_state()
