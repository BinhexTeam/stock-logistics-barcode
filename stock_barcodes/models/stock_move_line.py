# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    barcode_scan_state = fields.Selection(
        [("pending", "Pending"), ("done", "Done"), ("done_forced", "Done forced")],
        string="Scan State",
        default="pending",
        compute="_compute_barcode_scan_state",
        readonly=False,
        store=True,
    )
    product_tracking = fields.Selection(
        related="product_id.tracking", readonly=True, store=True
    )
    product_type = fields.Selection(related="product_id.type", readonly=True, store=True)
    qty_picked = fields.Float(
        "Quantity picked",
        digits="Product Unit of Measure",
        readonly=False,
        store=True,
        compute="_compute_qty_picked",
    )

    @api.depends("picked", "quantity")
    def _compute_qty_picked(self):
        for line in self:
            if line.picked or line.state == "done":
                line.qty_picked = line.quantity

    @api.depends("qty_picked", "quantity_product_uom")
    def _compute_barcode_scan_state(self):
        for line in self:
            if line.qty_picked >= line.quantity_product_uom:
                line.barcode_scan_state = "done"
            else:
                line.barcode_scan_state = "pending"

    def _barcodes_process_line_to_unlink(self):
        self.qty_picked = 0.0

    def action_barcode_detailed_operation_unlink(self):
        for sml in self:
            stock_move = sml.move_id
            stock_move.barcode_backorder_action = "pending"
            sml.unlink()
        # Find a barcode wizard for this picking (current user) to recompute and notify UI
        wiz_id = (
            self.env.context.get("wiz_barcode_id")
            or self.env["wiz.stock.barcodes.read.picking"]
            .sudo()
            .search(
                [
                    ("picking_id", "=", stock_move.picking_id.id),
                    ("create_uid", "=", self.env.uid),
                ],
                limit=1,
                order="id desc",
            )
            .id
        )
        if wiz_id:
            wiz = self.env["wiz.stock.barcodes.read.picking"].browse(wiz_id)
            wiz.fill_todo_records()
            wiz.determine_todo_action()
            payload = {
                "type": "barcode_move_line_unlink",
                "wiz_id": wiz_id,
            }
            bus = self.env["bus.bus"]
            try:
                bus._sendone(self._cr.dbname, "stock_barcodes_scan", payload)
            except TypeError:
                # Fallback for signature (channel, message)
                bus._sendone("stock_barcodes_scan", payload)
        return True

    def action_barcode_noop(self):
        """Placeholder for UI buttons; intentionally does nothing."""
        return True

    def _get_wizard(self):
        wiz_id = self.env.context.get("wiz_barcode_id")
        if wiz_id:
            return self.env["wiz.stock.barcodes.read.picking"].browse(wiz_id)
        return False

    def _get_multiplier(self, wiz, product):
        if product.tracking == "serial" or not wiz:
            return 1.0
        return float(wiz.multiplier_factor or 1.0)

    def _notify_wizard_ui(self, wiz, payload_type="barcode_qty_change"):
        if not wiz:
            return
        payload = {
            "type": payload_type,
            "wiz_id": wiz.id,
        }
        bus = self.env["bus.bus"]
        try:
            bus._sendone(self._cr.dbname, "stock_barcodes_scan", payload)
        except TypeError:
            # Fallback for legacy signature (channel, message)
            bus._sendone("stock_barcodes_scan", payload)

    def _recompute_todo_cards(self, wiz):
        if not wiz:
            return
        move_ids = self.mapped("move_id")
        todos = wiz.todo_line_ids.filtered(lambda t: bool(t.stock_move_ids & move_ids))
        if not todos:
            return
        todos._compute_qty_done()
        todos._compute_quantity()
        todos._compute_state()
        todos.invalidate_recordset()
        wiz.invalidate_recordset()
        self._notify_wizard_ui(wiz)

    def action_barcode_increment_line(self):
        wiz = self._get_wizard()
        for line in self:
            product = line.product_id
            multiplier = self._get_multiplier(wiz, product)
            if product.tracking == "serial":
                # Create a new serial line with qty 1
                line.copy(
                    default={
                        "qty_picked": 1.0,
                        "quantity": 1.0,
                        "lot_id": False,
                        "lot_name": False,
                    }
                )
            else:
                new_qty = (line.qty_picked or 0.0) + multiplier
                line.write({"qty_picked": new_qty, "quantity": new_qty})
        self._recompute_todo_cards(wiz)
        return True

    def action_barcode_decrement_line(self):
        wiz = self._get_wizard()
        for line in self:
            product = line.product_id
            multiplier = self._get_multiplier(wiz, product)
            if product.tracking == "serial":
                # Keep the line but zero it out to avoid stale references client-side
                line.write(
                    {
                        "qty_picked": 0.0,
                        "quantity": 0.0,
                        "lot_id": False,
                        "lot_name": False,
                        "barcode_scan_state": "pending",
                    }
                )
            else:
                new_qty = (line.qty_picked or 0.0) - multiplier
                if new_qty <= 0:
                    line.write(
                        {
                            "qty_picked": 0.0,
                            "quantity": 0.0,
                            "barcode_scan_state": "pending",
                        }
                    )
                else:
                    line.write({"qty_picked": new_qty, "quantity": new_qty})
        self._recompute_todo_cards(wiz)
        return True

    def action_barcode_change_lot(self):
        wiz = self._get_wizard()
        if wiz:
            line = self[:1]
            product = line.product_id
            if product.tracking not in ("lot", "serial"):
                wiz._set_messagge_info(
                    "not_found",
                    "Lot/serial change is only allowed for tracked storable products.",
                )
                wiz.play_sounds(False)
                wiz.lot_target_move_line_id = False
                wiz._broadcast_refresh()
                return True
            wiz.instruction_override = "lot"
            # Set the wizard context to this line so the next scanned lot updates it
            wiz.lot_target_move_line_id = line
            wiz.product_id = line.product_id
            wiz.location_id = line.location_id
            wiz.location_dest_id = line.location_dest_id
            wiz.lot_id = False
            wiz.lot_name = False
            wiz.product_qty = 1.0
            wiz._compute_instruction_text()
            if hasattr(wiz, "_broadcast_refresh"):
                wiz._broadcast_refresh()
        self._recompute_todo_cards(wiz)
        return True
