# Copyright 2023 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import _, api, models

MODEL_UPDATE_INVENTORY = ["wiz.stock.barcodes.read.inventory"]


class StockQuant(models.Model):
    _name = "stock.quant"
    _inherit = ["stock.quant", "barcodes.barcode_events_mixin"]

    def action_barcode_inventory_quant_unlink(self):
        self.with_context(inventory_mode=True).write(
            {"inventory_quantity": 0.0, "inventory_quantity_set": False}
        )
        self._after_inventory_quant_update()

    def _get_fields_to_edit(self):
        return [
            "location_id",
            "product_id",
            "product_uom_id",
            "lot_id",
            "package_id",
        ]

    def action_barcode_inventory_quant_edit(self):
        # Lot editing on inventory quants is disabled.
        return

    def enable_current_operations(self):
        self.send_bus_done(
            "stock_barcodes_kanban_update",
            {
                "type": "enable_operations",
                "payload": {
                    "id": self.id,
                },
            },
        )

    def operation_quantities_rest(self):
        new_qty = max(self.inventory_quantity - 1, 0.0)
        self.write(
            {"inventory_quantity": new_qty, "inventory_quantity_set": bool(new_qty)}
        )
        self.enable_current_operations()
        self._after_inventory_quant_update()

    def operation_quantities(self):
        new_qty = (self.inventory_quantity or 0.0) + 1
        self.write({"inventory_quantity": new_qty, "inventory_quantity_set": True})
        self.enable_current_operations()
        self._after_inventory_quant_update()

    def action_apply_inventory(self):
        res = super().action_apply_inventory()
        self.send_bus_done(
            "stock_barcodes_scan",
            {"type": "actions_barcode", "payload": {"apply_inventory": True}},
        )
        return res

    def _after_inventory_quant_update(self):
        wiz_barcode_id = self.env.context.get("wiz_barcode_id", False)
        if not wiz_barcode_id:
            return
        wiz = self.env["wiz.stock.barcodes.read.inventory"].browse(wiz_barcode_id)
        if not wiz:
            return
        wiz._compute_inventory_quant_ids()
        wiz._compute_inventory_quant_groups()
        wiz._compute_instruction_text()
        wiz.send_bus_done(
            "stock_barcodes_form_update",
            {
                "type": "count_apply_inventory",
                "payload": {"count": wiz.count_inventory_quants},
            },
        )

    @api.model
    def _get_forbidden_fields_write(self):
        res = super()._get_forbidden_fields_write()
        if self.env.context.get("allow_edit_owner"):
            res.remove("owner_id")
        return res
