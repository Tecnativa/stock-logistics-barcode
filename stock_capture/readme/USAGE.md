Screens open a session on a document with `document.action_capture_open(profile=None)` and send it the barcodes read with `stock.capture.session.capture_barcode(barcode)`, which returns the message, its type, the sound to play, the field to focus and an action to execute, if any. Buttons of the screen call the session actions (`action_confirm`, `action_force`, `action_validate`, `action_next_card`...) and the cards call their own (`action_capture_card_select`, `action_capture_remaining`, `action_capture_undo`, `action_capture_close`...) with `capture_session_id` in the context. The session field `feedback_seq` increases on each reading or action, for the screen to play the sound, show the notification and move the focus the session asks for.

A new kind of document inherits `stock.capture.document` and implements its `_capture_*` methods: profile, operations, locations, checks, how a reading is applied and how it is validated.

Other modules capture quantities through the engine:

- `stock.picking._capture_product(product, quantity, uom=None, lot=None, location=None, package=None, owner=None, result_package=None, merge=True, location_dest=None)`
- `stock.move._capture_quantity(quantity, uom=None, lot=None, location=None, package=None, owner=None, result_package=None, merge=True, location_dest=None)`
- `stock.move._capture_spread(quantity, uom=None, **characteristics)`, on several moves of a product, filling the pending quantity of each in order
- `stock.move.line._capture_set_quantity(quantity)`, to set the quantity captured on a given line, e.g. a weight recorded on it
- `stock.move.line._capture_undo(quantity=None, merge=True)`

A characteristic left as `None` matches any reserved line, while an empty recordset matches the lines without it. Captures add to the picked line of the same goods unless `merge=False` is given, which gives each capture lines of its own, e.g. one per weighing to label it.

The destination package of a capture can be decided by other modules extending `stock.picking.type._capture_result_package(result_package, location_dest)`, e.g. `stock_capture_package` creates a new package for each capture.

Installed on a database migrated from 18.0, the quantities read on pending detailed operations (`qty_picked` of `stock_move_line_qty_picked`) and the backorder decisions of `stock_barcodes` are captured.
