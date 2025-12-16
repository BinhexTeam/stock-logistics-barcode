# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _prepare_barcode_wiz_vals(self, option_group):
        vals = {
            "picking_id": self.id,
            "res_model_id": self.env.ref("stock.model_stock_picking").id,
            "res_id": self.id,
            "picking_type_code": self.picking_type_code,
            "option_group_id": option_group.id,
            "manual_entry": option_group.manual_entry,
            "picking_mode": "picking",
            "show_barcode_scanner": self.env["ir.config_parameter"]
            .sudo()
            .get_param("stock_barcodes.enable_camera_barcode_scanner", False),
        }
        if self.picking_type_id.code == "outgoing":
            vals["location_dest_id"] = self.location_dest_id.id
        elif self.picking_type_id.code == "incoming":
            vals["location_id"] = self.location_id.id

        if option_group.get_option_value("location_id", "filled_default"):
            vals["location_id"] = self.location_id.id
        if option_group.get_option_value("location_dest_id", "filled_default"):
            vals["location_dest_id"] = self.location_dest_id.id
        return vals
