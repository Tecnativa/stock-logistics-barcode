Other modules capture quantities through:

- `stock.picking._capture_product(product, quantity, uom=None, lot=None, location=None, package=None, owner=None, result_package=None, merge=True)`
- `stock.move._capture_quantity(quantity, uom=None, lot=None, location=None, package=None, owner=None, result_package=None, merge=True)`
- `stock.move._capture_spread(quantity, uom=None, **characteristics)`, on several moves of a product, filling the pending quantity of each in order
- `stock.move.line._capture_set_quantity(quantity)`, to set the quantity captured on a given line, e.g. a weight recorded on it
- `stock.move.line._capture_undo(quantity=None, merge=True)`

A characteristic left as `None` matches any reserved line, while an empty recordset matches the lines without it. Captures add to the picked line of the same goods unless `merge=False` is given, which gives each capture lines of its own, e.g. one per weighing to label it.

The destination package of a capture can be decided by other modules extending `stock.picking.type._capture_result_package(result_package, location_dest)`, e.g. `stock_capture_package` creates a new package for each capture.

The screens that read barcodes send each barcode to `stock.picking.capture_scan(barcode, scan_values)`, which interprets it (product, packaging, lot, package, location, weight and GS1 barcodes), joins it to the values read before and captures the product once it is known, with its lot when it needs one. It returns the values to send with the next barcode, their names to show, the captured lines and a message.

The operations show their progress with `captured_quantity` and `capture_state`, can be locked by the user capturing them (`_capture_lock`, `is_capture_locked`) and offer `action_capture_remaining` and `action_capture_undo` to the cards of the screens. The captured lines keep who captured them and when.

