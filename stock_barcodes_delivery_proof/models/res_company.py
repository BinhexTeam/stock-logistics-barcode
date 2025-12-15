# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    delivery_proof_enabled = fields.Boolean(
        string="Enable Delivery Proof Capture",
        default=False,
        help="Allow capturing photos as delivery proof from the barcode "
        "scanner interface. Only applies to outgoing pickings (deliveries).",
    )
    delivery_proof_level = fields.Selection(
        selection=[
            ("picking", "Per Picking"),
            ("line", "Per Line"),
        ],
        string="Delivery Proof Capture Level",
        default="picking",
        help="Per Picking: Capture photos for the entire delivery.\n"
        "Per Line: Capture photos for each product line individually.",
    )
