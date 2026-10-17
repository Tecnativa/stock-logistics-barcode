# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import datetime

from odoo import fields, models


class StockCaptureSession(models.TransientModel):
    _inherit = "stock.capture.session"

    lot_expiration_date = fields.Datetime(
        string="Expiration Date",
        help="Expiration date read (GS1 AI 17) for a new lot",
    )
    lot_use_date = fields.Datetime(
        string="Best before Date",
        help="Best before date read (GS1 AI 15) for a new lot",
    )

    def _capture_read_extra_values(self, values):
        result = super()._capture_read_extra_values(values)
        for key, field_name in (
            ("expiration_date", "lot_expiration_date"),
            ("use_date", "lot_use_date"),
        ):
            if values.get(key):
                self[field_name] = fields.Datetime.to_datetime(values[key])
        return result

    def _capture_lot_values(self):
        values = super()._capture_lot_values()
        product = self.product_id
        expiration_date = self.lot_expiration_date
        if not expiration_date and self.lot_use_date:
            # Only the best before date is read: the expiration date follows
            # from the times of the product
            expiration_date = self.lot_use_date + datetime.timedelta(
                days=product.use_time
            )
        if expiration_date:
            values["expiration_date"] = expiration_date
        if self.lot_use_date:
            values["use_date"] = self.lot_use_date
        return values

    def _capture_clean_values(self):
        result = super()._capture_clean_values()
        self.lot_expiration_date = self.lot_use_date = False
        return result

    def action_clean_lot(self):
        self.lot_expiration_date = self.lot_use_date = False
        return super().action_clean_lot()
