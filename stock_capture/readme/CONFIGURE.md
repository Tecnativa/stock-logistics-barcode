The first task of an implementation is to analyze, with the people doing them, the flow of each operation: what is read and in which order, what the screen must propose and what it must refuse. Then adjust a profile to each flow in *Inventory > Configuration > Capture Profiles* and set it on its operation types (*Capture Profile*, and *Capture Profile for New Transfers* for the unplanned transfers created from the screens).

The shipped profiles (Delivery, Receipt, Internal Transfer, Relocation, Inventory and Operation) are the ones agreed by the profiles used in production by several companies. An operation type without profile uses the one of its kind: Receipt, Delivery or Internal Transfer.

Each field of a profile has:

- *Step*: order in which the fields are asked. Only the fields to scan of the current step are matched against a barcode, and the current step is the one of the first required field still empty.
- *To scan*, *Required*, *Filled by default* (from the pending card in guided mode or from the document), *Forced* (guided mode rejects another value) and *Clean after done*.

Barcodes are read on products, product packagings (product units with a barcode), locations, lots and packages (their name). The GS1 nomenclature of the company reads GS1-128 barcodes with several values.

The system parameter `stock_capture.limit_product_qty` (999999 by default) rejects absurd quantities, e.g. a barcode read into the quantity field.
