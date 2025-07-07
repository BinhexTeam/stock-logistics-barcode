# Copyright 2025 Binhex <https://www.binhex.cloud>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class WizStockBarcodesReadPicking(models.TransientModel):
    _inherit = "wiz.stock.barcodes.read.picking"

    def action_validate_picking(self):
        res = super().action_validate_picking()
        if self.picking_id._check_expired_lots():
            return self.picking_id.with_context(
                button_validate_picking_ids=self.picking_id.id,
                stock_barcodes_validate_picking=True,
            )._action_generate_expired_wizard()
        return res
