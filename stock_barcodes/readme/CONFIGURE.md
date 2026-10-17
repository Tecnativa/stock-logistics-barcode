Before configuring, analyze with the people doing them the flow of each operation: what is read and in which order, what the screen must propose and what it must refuse. Then adjust a capture profile to each flow (*Inventory > Configuration > Capture Profiles*) and set it on the operation types, as explained in `stock_capture`.

Barcodes on master data:

- Products: *Barcode* of the product.
- Locations: *Barcode* of the location (multi-location setting).
- Packagings: barcode of a unit of the product (several units of measure setting), e.g. *Pack of 6*.
- Lots, serial numbers and packages: their name is their barcode.

The tiles of the *Barcodes* menu are barcode actions (*Inventory > Configuration > Barcode Actions*): the window action or method they open, the records they count and the barcode that opens them from the menu. Select them and use *Print barcodes* to get a sheet with their Code128 barcodes.
