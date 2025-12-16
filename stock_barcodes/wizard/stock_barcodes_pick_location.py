# Copyright 2025 Tecnativa
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models


class WizStockBarcodesPickLocation(models.TransientModel):
    _name = "wiz.stock.barcodes.pick.location"
    _description = "Select location for barcode picking wizard"

    picking_wiz_id = fields.Many2one(
        comodel_name="wiz.stock.barcodes.read.picking",
        required=True,
        ondelete="cascade",
    )
    target = fields.Selection(
        selection=[("source", "Source"), ("dest", "Destination")],
        required=True,
    )
    location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Location",
        required=True,
        domain=[("usage", "in", ["internal", "transit"])],
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        wiz = False
        if self.env.context.get("default_picking_wiz_id"):
            wiz = self.env["wiz.stock.barcodes.read.picking"].browse(
                self.env.context.get("default_picking_wiz_id")
            )
        target = self.env.context.get("default_target")
        if wiz:
            if target == "source" and not res.get("location_id"):
                res["location_id"] = wiz.location_id.id or wiz.picking_id.location_id.id
            if target == "dest" and not res.get("location_id"):
                res["location_id"] = (
                    wiz.location_dest_id.id or wiz.picking_id.location_dest_id.id
                )
        return res

    def action_apply(self):
        self.ensure_one()
        if not self.picking_wiz_id:
            return {"type": "ir.actions.act_window_close"}
        if self.target == "source":
            self.picking_wiz_id.location_id = self.location_id
        else:
            self.picking_wiz_id.location_dest_id = self.location_id
        # Refresh the wizard UI so dependent domains recompute
        self.picking_wiz_id.invalidate_recordset()
        return {"type": "ir.actions.act_window_close"}
