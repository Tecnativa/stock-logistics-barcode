This module is the engine the reading and weighing screens use to record the quantities captured by the user on transfers. It has no screen of its own.

A captured quantity is taken from the reservation of the move, the way Odoo's own barcode application does it, so reading less than reserved does not release the rest:

- The captured part of a reserved line becomes a picked line and the rest stays reserved on an unpicked one. Capturing the same goods again adds to that picked line.
- Capturing a lot, location, package or owner other than the reserved one moves the reservation of the move to it.
- Only the quantity captured over the reservation is reserved anew.
- A quantity can be captured into a destination package, which keeps a picked line per package.
- Undoing a captured quantity gives it back to the reservation of the move up to its demand.
- A product captured on a transfer fills its moves in order, and a product without moves gets a new one.

Barcodes read by a screen are interpreted here too, so every screen reads products, packagings, lots, packages, locations, weights and GS1 barcodes the same way.

When the transfer is validated, Odoo drops the unpicked lines, as it does with any transfer.
