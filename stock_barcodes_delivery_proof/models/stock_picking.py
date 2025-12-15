# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # Visibility
    show_delivery_proof = fields.Boolean(
        compute="_compute_show_delivery_proof",
    )

    # Filtered move lines
    move_lines_with_photos = fields.Many2many(
        comodel_name="stock.move.line",
        compute="_compute_move_lines_with_photos",
        string="Move Lines with Delivery Proof",
        help="Move lines that have at least one delivery proof photo",
    )

    @api.depends("picking_type_code", "company_id.delivery_proof_enabled")
    def _compute_show_delivery_proof(self):
        for picking in self:
            picking.show_delivery_proof = (
                picking.picking_type_code == "outgoing"
                and picking.company_id.delivery_proof_enabled
            )

    @api.depends("move_line_ids_without_package.delivery_proof_count")
    def _compute_move_lines_with_photos(self):
        for picking in self:
            picking.move_lines_with_photos = (
                picking.move_line_ids_without_package.filtered(
                    lambda line: line.delivery_proof_count > 0
                )
            )
