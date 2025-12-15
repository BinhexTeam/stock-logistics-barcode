# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models


class WizStockBarcodesReadPicking(models.TransientModel):
    _inherit = "wiz.stock.barcodes.read.picking"

    # Fields for UI
    show_delivery_proof = fields.Boolean(
        compute="_compute_show_delivery_proof",
    )
    delivery_proof_level = fields.Selection(
        related="picking_id.company_id.delivery_proof_level",
    )
    delivery_proof_ids = fields.One2many(
        related="picking_id.delivery_proof_ids",
        readonly=False,
    )
    delivery_proof_count = fields.Integer(
        related="picking_id.delivery_proof_count",
    )

    @api.depends("picking_type_code", "picking_id.company_id.delivery_proof_enabled")
    def _compute_show_delivery_proof(self):
        for wiz in self:
            wiz.show_delivery_proof = (
                wiz.picking_type_code == "outgoing"
                and wiz.picking_id.company_id.delivery_proof_enabled
            )

    def action_save_delivery_proof(self, image_data, move_line_id=False):
        """Save the captured image as delivery proof.

        Args:
            image_data: Base64 encoded image data
            move_line_id: Optional move line ID for line-level proof

        Returns:
            The created stock.delivery.proof.image record
        """
        self.ensure_one()

        vals = {
            "image": image_data,
            "name": _("Delivery Photo %s") % fields.Datetime.now(),
            "picking_id": self.picking_id.id,
        }

        if move_line_id:
            move_line = self.env["stock.move.line"].browse(move_line_id)
            if move_line.exists() and move_line.picking_id == self.picking_id:
                vals["move_line_id"] = move_line_id

        return self.env["stock.delivery.proof.image"].create(vals)

    def action_delete_delivery_proof(self, proof_id):
        """Delete a delivery proof image.

        Args:
            proof_id: ID of the stock.delivery.proof.image to delete

        Returns:
            True if successful
        """
        import logging

        _logger = logging.getLogger(__name__)

        _logger.info("=" * 80)
        _logger.info("action_delete_delivery_proof called")
        _logger.info("self: %s", self)
        _logger.info("proof_id: %s (type: %s)", proof_id, type(proof_id))
        _logger.info("self.picking_id: %s", self.picking_id)
        _logger.info("=" * 80)

        self.ensure_one()
        proof = self.env["stock.delivery.proof.image"].browse(proof_id)

        _logger.info("Proof record: %s", proof)
        _logger.info("Proof exists: %s", proof.exists())
        if proof.exists():
            _logger.info("Proof.picking_id: %s", proof.picking_id)
            _logger.info("Matches: %s", proof.picking_id == self.picking_id)

        if proof.exists() and proof.picking_id == self.picking_id:
            proof.unlink()
            _logger.info("Photo deleted successfully")
            return True

        _logger.warning(
            "Photo NOT deleted - proof doesn't exist or doesn't match picking"
        )
        return False

    def get_delivery_proof_data(self):
        """Get delivery proof images data for the JS widget.

        Returns:
            List of dictionaries with proof image data
        """
        self.ensure_one()
        proofs = self.picking_id.delivery_proof_ids
        return [
            {
                "id": proof.id,
                "name": proof.name,
                "capture_date": proof.capture_date.isoformat()
                if proof.capture_date
                else None,
                "captured_by": proof.captured_by_id.name
                if proof.captured_by_id
                else None,
                "move_line_id": proof.move_line_id.id if proof.move_line_id else None,
                "product_name": proof.move_line_id.product_id.display_name
                if proof.move_line_id
                else None,
            }
            for proof in proofs
        ]

    def get_move_lines_for_proof(self):
        """Get move lines available for line-level proof capture.

        Returns:
            List of dictionaries with move line data
        """
        self.ensure_one()
        if self.delivery_proof_level != "line":
            return []

        return [
            {
                "id": line.id,
                "product_name": line.product_id.display_name,
                "qty_done": line.qty_done,
                "proof_count": line.delivery_proof_count,
            }
            for line in self.picking_id.move_line_ids.filtered(
                lambda line: line.qty_done > 0
            )
        ]
