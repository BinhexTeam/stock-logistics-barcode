# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    delivery_proof_ids = fields.One2many(
        comodel_name="stock.delivery.proof.image",
        inverse_name="picking_id",
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
        for picking in self:
            picking.delivery_proof_count = len(picking.delivery_proof_ids)

    @api.depends("picking_type_code", "company_id.delivery_proof_enabled")
    def _compute_show_delivery_proof(self):
        for picking in self:
            picking.show_delivery_proof = (
                picking.picking_type_code == "outgoing"
                and picking.company_id.delivery_proof_enabled
            )

    def action_view_delivery_proof(self):
        """Open delivery proof images in a kanban/list view."""
        self.ensure_one()
        action = {
            "name": "Delivery Proof Photos",
            "type": "ir.actions.act_window",
            "res_model": "stock.delivery.proof.image",
            "view_mode": "kanban,tree,form",
            "domain": [("picking_id", "=", self.id)],
            "context": {
                "default_picking_id": self.id,
            },
        }
        return action

    def action_add_delivery_proof(self):
        """Action to add a delivery proof image from the picking form."""
        self.ensure_one()
        return {
            "name": "Add Delivery Proof",
            "type": "ir.actions.act_window",
            "res_model": "stock.delivery.proof.image",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_picking_id": self.id,
            },
        }
