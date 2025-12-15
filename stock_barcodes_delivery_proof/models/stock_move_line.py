# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    delivery_proof_ids = fields.One2many(
        comodel_name="stock.delivery.proof.image",
        inverse_name="move_line_id",
        string="Delivery Proof Images",
    )
    delivery_proof_count = fields.Integer(
        compute="_compute_delivery_proof_count",
        string="Proof Count",
    )
    show_delivery_proof = fields.Boolean(
        compute="_compute_show_delivery_proof",
        string="Show Delivery Proof",
    )

    @api.depends("delivery_proof_ids")
    def _compute_delivery_proof_count(self):
        for line in self:
            line.delivery_proof_count = len(line.delivery_proof_ids)

    @api.depends(
        "picking_code",
        "company_id.delivery_proof_enabled",
        "company_id.delivery_proof_level",
    )
    def _compute_show_delivery_proof(self):
        for line in self:
            line.show_delivery_proof = (
                line.picking_code == "outgoing"
                and line.company_id.delivery_proof_enabled
                and line.company_id.delivery_proof_level == "line"
            )
