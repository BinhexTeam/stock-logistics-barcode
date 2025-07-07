# Copyright 2025 Binhex <https://www.binhex.cloud>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        res = super().button_validate()
        if self.state == "done" and self.env.context.get(
            "stock_barcodes_validate_picking", False
        ):
            return self.picking_type_id.get_action_picking_tree_ready()
        return res
