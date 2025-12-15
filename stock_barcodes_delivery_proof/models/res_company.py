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
