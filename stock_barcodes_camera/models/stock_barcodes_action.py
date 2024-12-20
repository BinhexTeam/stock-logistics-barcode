# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models


class StockBarcodesAction(models.Model):
    _inherit = "stock.barcodes.action"

    def open_inventory_action(self, ctx):
        option_group = self.env.ref(
            "stock_barcodes.stock_barcodes_option_group_inventory"
        )
        vals = {
            "option_group_id": option_group.id,
            "manual_entry": option_group.manual_entry,
            "display_read_quant": option_group.display_read_quant,
            "show_barcode_scanner": self.env["ir.config_parameter"]
            .sudo()
            .get_param("stock_barcodes.enable_camera_barcode_scanner", False),
        }
        if option_group.get_option_value("location_id", "filled_default"):
            vals["location_id"] = (
                self.env["stock.warehouse"].search([], limit=1).lot_stock_id.id
            )
        wiz = self.env["wiz.stock.barcodes.read.inventory"].create(vals)
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock_barcodes.action_stock_barcodes_read_inventory"
        )
        action["res_id"] = wiz.id
        action["context"] = ctx
        return action
