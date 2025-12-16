# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.tools.float_utils import float_compare, float_round


class WizStockBarcodesReadTodo(models.TransientModel):
    _name = "wiz.stock.barcodes.read.todo"
    _description = "Wizard to read barcode todo"
    _order = "completion_priority asc, state_priority asc, position_index asc, id asc"

    # To prevent remove the record wizard until 2 days old
    _transient_max_hours = 48

    name = fields.Char()
    wiz_barcode_id = fields.Many2one(comodel_name="wiz.stock.barcodes.read.picking")
    picking_state = fields.Selection(related="wiz_barcode_id.picking_state")
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        readonly=True,
        string="Partner",
    )
    state = fields.Selection(
        [("pending", "Pending"), ("done", "Done"), ("done_forced", "Done forced")],
        string="Scan State",
        default="pending",
        compute="_compute_state",
        store=True,
        readonly=False,
    )
    state_priority = fields.Integer(compute="_compute_state_priority", store=True)
    completion_priority = fields.Integer(
        compute="_compute_completion_priority", store=True
    )

    product_qty_reserved = fields.Float(
        "Reserved",
        digits="Product Unit of Measure",
        readonly=True,
    )
    product_uom_qty = fields.Float(
        "Demand",
        digits="Product Unit of Measure",
        readonly=True,
    )
    quantity = fields.Float(
        "Quantity",
        digits="Product Unit of Measure",
        compute="_compute_quantity",
        store=True,
    )
    qty_done = fields.Float(
        "Done",
        digits="Product Unit of Measure",
        compute="_compute_qty_done",
        store=True,
    )
    qty_done_rest = fields.Float(compute="_compute_qty_done_rest", store=True)
    location_id = fields.Many2one(comodel_name="stock.location")
    location_name = fields.Char(related="location_id.name")
    location_dest_id = fields.Many2one(comodel_name="stock.location")
    location_dest_name = fields.Char(
        string="Destinatino Name", related="location_dest_id.name"
    )
    product_id = fields.Many2one(comodel_name="product.product")
    lot_id = fields.Many2one(comodel_name="stock.lot")
    uom_id = fields.Many2one(comodel_name="uom.uom")
    package_id = fields.Many2one(comodel_name="stock.quant.package")
    result_package_id = fields.Many2one(comodel_name="stock.quant.package")
    package_product_qty = fields.Float()

    res_model_id = fields.Many2one(comodel_name="ir.model")
    res_ids = fields.Char()
    line_ids = fields.Many2many(comodel_name="stock.move.line")
    stock_move_ids = fields.Many2many(comodel_name="stock.move")
    position_index = fields.Integer()
    picking_code = fields.Char("Type of Operation")
    is_extra_line = fields.Boolean()
    # Used in kanban view
    is_stock_move_line_origin = fields.Boolean()
    is_focused = fields.Boolean(compute="_compute_is_focused")

    @api.depends("state")
    def _compute_state_priority(self):
        for rec in self:
            if rec.state == "pending":
                rec.state_priority = 0
            elif rec.state == "done":
                rec.state_priority = 1
            else:
                rec.state_priority = 2

    @api.depends("quantity", "product_uom_qty", "state", "uom_id")
    def _compute_completion_priority(self):
        for rec in self:
            if rec.state in ("done", "done_forced"):
                rec.completion_priority = 1
                continue
            if (
                float_compare(
                    rec.quantity,
                    rec.product_uom_qty,
                    precision_rounding=(rec.uom_id and rec.uom_id.rounding) or 0.01,
                )
                >= 0
            ):
                rec.completion_priority = 1
            else:
                rec.completion_priority = 0

    @api.depends("wiz_barcode_id.focused_move_id", "stock_move_ids")
    def _compute_is_focused(self):
        for rec in self:
            rec.is_focused = bool(
                rec.wiz_barcode_id.focused_move_id
                and rec.wiz_barcode_id.focused_move_id in rec.stock_move_ids
            )

    @api.depends("qty_done", "product_uom_qty")
    def _compute_qty_done_rest(self):
        for rec in self:
            rec.qty_done_rest = rec.product_uom_qty - rec.qty_done

    def action_todo_next(self):
        self.state = "done_forced"
        self.line_ids.barcode_scan_state = "done_forced"
        for sml in self.line_ids:
            if (
                float_compare(
                    sml.quantity_product_uom,
                    sml.quantity,
                    precision_rounding=sml.product_uom_id.rounding,
                )
                == 0
            ):
                continue
            if sml.move_id.state == "confirmed" and sml.qty_picked:
                sml.move_id.state = "partially_available"
            if sml.move_id.state in ["partially_available", "assigned"]:
                sml.quantity_product_uom = sml.quantity
        if self.is_extra_line or not self.is_stock_move_line_origin:
            barcode_backorder_action = self.env.context.get(
                "barcode_backorder_action", "create_backorder"
            )
            self.stock_move_ids.barcode_backorder_action = barcode_backorder_action
            if barcode_backorder_action == "pending":
                self.stock_move_ids.move_line_ids.unlink()
                self.stock_move_ids._action_assign()
        wiz_barcode = self.wiz_barcode_id
        self.wiz_barcode_id.fill_todo_records()
        self.wiz_barcode_id = wiz_barcode
        self.wiz_barcode_id.determine_todo_action()
        self.wiz_barcode_id._refresh_todo_lines()
        self.wiz_barcode_id._notify_qty_change()

    def action_reset_lines(self):
        self.state = "pending"
        self.line_ids.barcode_scan_state = "pending"
        self.line_ids.qty_picked = 0.0
        self.wiz_barcode_id.action_clean_values()
        self.wiz_barcode_id.fill_todo_records()
        self.wiz_barcode_id.determine_todo_action()
        self.wiz_barcode_id._refresh_todo_lines()
        self.wiz_barcode_id._notify_qty_change()

    def action_back_line(self):
        if self.position_index > 0:
            record = self.wiz_barcode_id.todo_line_ids[self.position_index - 1]
            self.wiz_barcode_id.determine_todo_action(forced_todo_line=record)

    def action_next_line(self):
        if self.position_index < len(self.wiz_barcode_id.todo_line_ids) - 1:
            record = self.wiz_barcode_id.todo_line_ids[self.position_index + 1]
            self.wiz_barcode_id.determine_todo_action(forced_todo_line=record)

    def action_barcode_noop(self):
        """Placeholder to avoid errors from UI buttons."""
        return True

    def _create_move_line(self, move, qty):
        location = move.location_id
        dest = move.location_dest_id
        vals = {
            "picking_id": move.picking_id.id,
            "move_id": move.id,
            "product_id": move.product_id.id,
            "product_uom_id": move.product_uom.id,
            "qty_picked": qty,
            "quantity": qty,
            "location_id": location.id,
            "location_dest_id": dest.id,
            "barcode_scan_state": "pending",
        }
        return self.env["stock.move.line"].create(vals)

    def _adjust_quantity(self, delta):
        self.ensure_one()
        if not self.stock_move_ids:
            return True

        move = self.stock_move_ids[:1]
        product = move.product_id
        rounding = product.uom_id.rounding
        multiplier = (
            float(self.wiz_barcode_id.multiplier_factor or 1.0)
            if product.tracking != "serial"
            else 1.0
        )
        delta = delta * multiplier

        # Select a target line (prefer one without lot for non-serial)
        target_line = self.line_ids[:1]

        def _find_existing_candidate():
            return move.move_line_ids.filtered(
                lambda l: l.product_id == product
                and not l.lot_id
                and not l.lot_name
                and l.location_id == move.location_id
                and l.location_dest_id == move.location_dest_id
                and l.package_id == self.package_id
                and l.result_package_id == self.result_package_id
                and l.owner_id == move.move_orig_ids.mapped("picking_id.partner_id")[:1]
            )[:1]

        if delta > 0:
            if product.tracking == "serial":
                # Serial: create a new clean line with qty 1
                new_line = self._create_move_line(move, 1.0)
                self.line_ids |= new_line
            else:
                if target_line:
                    new_qty = float_round(
                        target_line.qty_picked + delta,
                        precision_rounding=rounding,
                    )
                    target_line.write({"qty_picked": new_qty, "quantity": new_qty})
                else:
                    # Try to reuse an existing move line to avoid duplicate lines
                    candidate = _find_existing_candidate()
                    if candidate:
                        target_line = candidate
                        new_qty = float_round(
                            target_line.qty_picked + delta,
                            precision_rounding=rounding,
                        )
                        target_line.write({"qty_picked": new_qty, "quantity": new_qty})
                        self.line_ids |= target_line
                    else:
                        new_line = self._create_move_line(
                            move, float_round(delta, precision_rounding=rounding)
                        )
                        self.line_ids |= new_line
        elif delta < 0:
            if not target_line:
                return True
            if product.tracking == "serial":
                # Drop link to keep the transient record alive in the view
                self.line_ids = [(3, target_line.id, 0)]
                target_line.unlink()
            else:
                new_qty = float_round(
                    target_line.qty_picked + delta,
                    precision_rounding=rounding,
                )
                if new_qty <= 0:
                    self.line_ids = [(3, target_line.id, 0)]
                    target_line.unlink()
                else:
                    target_line.write({"qty_picked": new_qty, "quantity": new_qty})
        # Recompute aggregates so the todo card progress matches detailed move lines
        self._compute_qty_done()
        self._compute_quantity()
        if not self.line_ids:
            self.qty_done = 0.0
            self.quantity = 0.0
        self._compute_state()
        self.invalidate_recordset()
        self.wiz_barcode_id.invalidate_recordset()

        # Notify UI listeners via bus so the kanban card refreshes without manual reload
        if self.wiz_barcode_id:
            payload = {
                "type": "barcode_qty_change",
                "wiz_id": self.wiz_barcode_id.id,
            }
            bus = self.env["bus.bus"]
            try:
                bus._sendone(self._cr.dbname, "stock_barcodes_scan", payload)
            except TypeError:
                bus._sendone("stock_barcodes_scan", payload)
        return True

    def action_barcode_add_one(self):
        for rec in self:
            rec._adjust_quantity(1.0)
        return True

    def action_barcode_remove_one(self):
        for rec in self:
            rec._adjust_quantity(-1.0)
        return True

    def action_barcode_complete_remaining(self):
        for rec in self:
            if not rec.product_id:
                continue
            remaining = rec.product_uom_qty - rec.quantity
            if remaining <= 0:
                continue
            product = rec.product_id
            multiplier = (
                float(rec.wiz_barcode_id.multiplier_factor or 1.0)
                if product.tracking != "serial"
                else 1.0
            )
            delta = remaining if product.tracking == "serial" else remaining
            # For serial, force unitary additions
            if product.tracking == "serial":
                for _i in range(int(delta)):
                    rec._adjust_quantity(1.0)
            else:
                rec._adjust_quantity(delta / multiplier)
        return True

    def action_barcode_focus_move(self, todo_id=None):
        self.ensure_one()
        target_id = todo_id or self.id
        self.wiz_barcode_id.action_focus_move(target_id)
        return True

    @api.depends("line_ids.qty_picked")
    def _compute_qty_done(self):
        for rec in self:
            rec.qty_done = sum(rec.line_ids.mapped("qty_picked"))

    @api.depends(
        "line_ids.qty_picked",
        "line_ids.quantity",
        "stock_move_ids.move_line_ids.qty_picked",
    )
    def _compute_quantity(self):
        for rec in self:
            # Prefer aggregating over all move lines linked to the todo's moves to catch
            # multiple lots/lines; fallback to the explicit line_ids if needed.
            move_line_qty = sum(rec.stock_move_ids.mapped("move_line_ids.qty_picked"))
            rec.quantity = (
                move_line_qty
                if move_line_qty
                else sum(rec.line_ids.mapped("qty_picked"))
            )

    @api.depends(
        "line_ids",
        "line_ids.qty_picked",
        "line_ids.quantity_product_uom",
        "line_ids.barcode_scan_state",
        "qty_done",
        "product_uom_qty",
    )
    def _compute_state(self):
        for rec in self:
            if float_compare(
                rec.qty_done,
                rec.product_uom_qty,
                precision_rounding=rec.uom_id.rounding,
            ) > -1 or (
                rec.wiz_barcode_id.option_group_id.source_pending_moves
                == "move_line_ids"
                and rec.line_ids
                and (
                    sum(rec.line_ids.mapped("qty_picked"))
                    >= sum(rec.stock_move_ids.mapped("product_uom_qty"))
                    or not any(
                        ln.barcode_scan_state == "pending" for ln in rec.line_ids
                    )
                )
            ):
                rec.state = "done"
            else:
                rec.state = "pending"

    @api.model
    def fields_to_fill_from_pending_line(self):
        res = [
            "location_id",
            "location_dest_id",
            "product_id",
            "lot_id",
            "package_id",
        ]
        if not self.wiz_barcode_id.keep_result_package:
            res.append("result_package_id")
        return res

    def fill_from_pending_line(self):
        self.wiz_barcode_id.selected_pending_move_id = self
        self.wiz_barcode_id.determine_todo_action(forced_todo_line=self)
        for field in self.fields_to_fill_from_pending_line():
            self.wiz_barcode_id[field] = self[field]
        # Force fill product_qty if filled_default is set
        self.wiz_barcode_id.product_qty = 0.0
        if self.wiz_barcode_id.option_group_id.get_option_value(
            "product_qty", "filled_default"
        ):
            self.wiz_barcode_id.product_qty = self.product_uom_qty - sum(
                self.line_ids.mapped("qty_picked")
            )
        self.wiz_barcode_id.product_uom_id = self.uom_id
        self.wiz_barcode_id.action_show_step()
        self.wiz_barcode_id._set_focus_on_qty_input()

    def operation_quantities(self):
        self.fill_from_pending_line()
        self.wiz_barcode_id.manual_entry = True
        self.wiz_barcode_id.product_qty = self.qty_done_rest
        if self.wiz_barcode_id.picking_id.picking_type_id.code != "incoming":
            self.wiz_barcode_id.qty_available = self.qty_done_rest
            self.wiz_barcode_id.location_id = self.location_id.id
        self.wiz_barcode_id.with_context(manual_picking=True).action_confirm()

    def _get_fields_to_edit(self):
        return [
            "location_dest_id",
            "location_id",
            "product_id",
            "lot_id",
            "package_id",
        ]

    def action_barcode_inventory_quant_edit(self):
        wiz_barcode_id = self.env.context.get("wiz_barcode_id", False)
        wiz_barcode = self.env["wiz.stock.barcodes.read.picking"].browse(wiz_barcode_id)
        wiz_barcode.manual_entry = True
        self.fill_from_pending_line()
        self.env["bus.bus"]._sendone(
            "stock_barcodes_scan",
            "stock_barcodes_edit_manual",
            {
                "manual_entry": True,
            },
        )
