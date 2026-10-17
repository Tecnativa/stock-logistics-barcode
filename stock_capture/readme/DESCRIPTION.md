This module is the engine of the screens that read barcodes or weigh quantities on stock documents. It has no screen of its own: `stock_barcodes`, `stock_weighing` and other interfaces only add views on it, so every feature works the same way on all of them.

**Documents.** A screen works on a document: a transfer, an operation type (the transfer to work on is found from the product read), a batch transfer, a location being counted (inventory) or, with `mrp_capture`, a manufacturing order. The cards of the screens are the real operations, detailed operations or quants of the document.

**Profiles.** A capture profile, set on each operation type, decides how the screens behave: the fields read in each step (required, forced in guided mode, filled by default, cleaned after each reading), guided or free mode, manual quantities and confirmation, cards, stock and demand checks, lots, packages and putaway.

**Readings.** The screen sessions interpret barcodes the same way for every screen: products, packagings, lots, packages (their content or the destination package), locations, weight barcodes and GS1-128 barcodes.

**Captured quantities.** A captured quantity is taken from the reservation of the move, the way Odoo's own barcode application does it, so reading less than reserved does not release the rest:

- The captured part of a reserved line becomes a picked line and the rest stays reserved on an unpicked one. Capturing the same goods again adds to that picked line.
- Capturing a lot, location, package or owner other than the reserved one moves the reservation of the move to it, and a destination read by the user is set on the captured line.
- Only the quantity captured over the reservation is reserved anew.
- Undoing a captured quantity gives it back to the reservation of the move up to its demand.
- Operations closed from a screen keep what to do with the rest of their demand (backorder or not), so Odoo does not ask again when the transfer is validated.

When the transfer is validated, Odoo drops the unpicked lines, as it does with any transfer.
