This module adds to `stock_capture` an option per operation type to put each read or weighed quantity in a new package, e.g. one package per weighing of a variable weight product. It works on transfers and, with `mrp_capture`, on manufacturing orders for the product to manufacture and its byproducts.

The packages get the package type set on the operation type, and their labels are printed as Odoo prints them on "Put in Pack", with the operation type options to print the package label.

A quantity captured with a destination package given by the user goes to that package, and components consumed or goods written off never get one.
