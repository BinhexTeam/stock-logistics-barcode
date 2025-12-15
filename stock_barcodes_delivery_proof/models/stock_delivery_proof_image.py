# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models


class StockDeliveryProofImage(models.Model):
    _name = "stock.delivery.proof.image"
    _description = "Delivery Proof Image"
    _order = "create_date desc"

    name = fields.Char(
        string="Description",
        default=_("Delivery Photo"),
    )

    # Relationship with ir.attachment (hybrid approach)
    attachment_id = fields.Many2one(
        comodel_name="ir.attachment",
        string="Attachment",
        required=True,
        ondelete="restrict",  # Prevent deletion of attachment without deleting this record
        index=True,
    )
    image = fields.Binary(
        related="attachment_id.datas",
        string="Image",
        readonly=False,
    )
    image_filename = fields.Char(
        related="attachment_id.name",
        string="Filename",
    )

    # Direct relationships (advantage of separate model)
    picking_id = fields.Many2one(
        comodel_name="stock.picking",
        string="Picking",
        ondelete="cascade",
        index=True,
    )
    move_line_id = fields.Many2one(
        comodel_name="stock.move.line",
        string="Move Line",
        ondelete="cascade",
        index=True,
    )

    # Metadata
    capture_date = fields.Datetime(
        string="Capture Date",
        default=fields.Datetime.now,
    )
    captured_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Captured By",
        default=lambda self: self.env.user,
    )
    notes = fields.Text(string="Notes")

    # Proof type (picking level or line level)
    proof_type = fields.Selection(
        selection=[
            ("picking", "Picking Level"),
            ("line", "Line Level"),
        ],
        string="Proof Type",
        compute="_compute_proof_type",
        store=True,
    )

    @api.depends("picking_id", "move_line_id")
    def _compute_proof_type(self):
        for record in self:
            if record.move_line_id:
                record.proof_type = "line"
            else:
                record.proof_type = "picking"

    @api.model_create_multi
    def create(self, vals_list):
        """Create attachment automatically if image is passed directly."""
        for vals in vals_list:
            if vals.get("image") and not vals.get("attachment_id"):
                # Determine res_model and res_id for attachment
                res_model = self._name
                res_id = False

                attachment_vals = {
                    "name": vals.get("name", "delivery_proof.jpg"),
                    "datas": vals["image"],
                    "res_model": res_model,
                    "res_id": res_id,
                    "type": "binary",
                }
                attachment = self.env["ir.attachment"].create(attachment_vals)
                vals["attachment_id"] = attachment.id
                # Remove image from vals as it will be handled via related field
                vals.pop("image", None)
        records = super().create(vals_list)
        # Update attachment res_id after creation
        for record in records:
            if record.attachment_id and not record.attachment_id.res_id:
                record.attachment_id.write(
                    {
                        "res_id": record.id,
                        "res_model": self._name,
                    }
                )
        return records

    def unlink(self):
        """Delete associated attachments when record is deleted."""
        # Get attachments before deleting the record, and filter only existing ones
        attachments = self.mapped("attachment_id").exists()
        result = super().unlink()
        # Delete attachments if they still exist (not deleted by cascade)
        if attachments.exists():
            attachments.unlink()
        return result
