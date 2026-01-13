# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models


class WizStockBarcodeSession(models.TransientModel):
    _inherit = "wiz.stock.barcode.session"

    def adjust_move_done_qty(self, move_id, delta):
        move = self.env["stock.move"].browse(move_id)
        if move._fields.get("quantity_done"):
            move.quantity_done = (move.quantity_done or 0.0) + delta
        elif move._fields.get("quantity"):
            move.quantity = (move.quantity or 0.0) + delta
        else:
            for line in move.move_line_ids:
                if line._fields.get("qty_done"):
                    line.qty_done = (line.qty_done or 0.0) + delta
                    break
        return {
            "picking": self._picking_payload(),
        }
