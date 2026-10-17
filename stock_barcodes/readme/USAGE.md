Open the barcode screen from:

1. The *Barcodes* menu: choose a tile (Receipts, Deliveries, Internal Transfers, Inventory, Operations) or read the barcode of a tile.
2. The cards of *Inventory > Overview*: read on any ready transfer of the operation type, list its transfers ready to read or start a new unplanned transfer.
3. The *Scan* button of a transfer, a batch transfer or, with `stock_barcodes_mrp`, a manufacturing order.

The screen keeps what you read until it is captured, and the session survives the navigation for two days.

**Reading.** Read in any order (free mode) or follow the pending card proposed (guided mode). A product adds one unit (a packaging, its quantity; a weight or GS1 barcode, its quantity); a tracked product waits for its lot unless the profile takes it from the stock; a location sets the source (or the destination, depending on the step); a package with stock moves with all its content, another package becomes the destination package. The message tells what was read and the line below what the screen waits for. Readings that cannot be captured play an error sound and say why: wrong product, lot or location for the card, product not demanded, quantity not available in the location, or over the demand (*Capture anyway* captures it).

**Manual entry.** The keyboard button makes the fields editable; *Confirm* captures them. With manual confirmation in the profile every reading waits for *Confirm*, and repeated readings can add up.

**Cards.** The pending operations or detailed operations of the document, sorted by location. Tap a card to fill the screen from it. Its buttons capture what is left, undo what was captured, leave a detailed operation without capturing it or close an operation with or without backorder. The eye button switches between pending and captured cards and the list button shows the captured detailed operations, which can be removed.

**Other tools.** Product information (stock by location, on hand, incoming, outgoing, forecasted) and selection of a source or destination location with stock; new destination package and keeping it for the next readings; serial numbers entered in the detailed operations of the product; registering the barcode of a new packaging.

**Validate** validates the document with the captured quantities, putting it in a package first when the profile asks for it, and goes back to the transfers ready to read.

**Inventory.** The *Inventory* tile counts the stock of the main warehouse. Each reading adds to the counted quantity of the location read (or replaces it, depending on the profile); serial numbers count one unit each. Cards show what you counted or what is pending, with buttons to add, remove or clear. *Apply* applies your counts with the reason Odoo asks for.
