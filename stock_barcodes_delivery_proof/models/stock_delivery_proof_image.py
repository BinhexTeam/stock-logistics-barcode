# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, fields, models


class StockDeliveryProofImage(models.Model):
    _name = "stock.delivery.proof.image"
    _description = "Delivery Proof Image"
    _order = "create_date desc"

    move_line_id = fields.Many2one(
        comodel_name="stock.move.line",
        required=True,
        ondelete="cascade",
        index=True,
    )
    image = fields.Binary(
        string="Photo",
        required=True,
        attachment=False,  # Store directly in DB, not as ir.attachment
    )
    capture_date = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
    )
    captured_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Captured By",
        default=lambda self: self.env.user,
        required=True,
    )
    notes = fields.Text()

    def name_get(self):
        """Custom name display for photos."""
        result = []
        for record in self:
            name = _("Photo - %s") % record.capture_date.strftime("%Y-%m-%d %H:%M:%S")
            result.append((record.id, name))
        return result
