# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import logging
import traceback
from collections import OrderedDict, defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import first
from odoo.tools.float_utils import float_compare, float_round
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class WizStockBarcodesReadPicking(models.TransientModel):
    _name = "wiz.stock.barcodes.read.picking"
    _inherit = "wiz.stock.barcodes.read"
    _description = "Wizard to read barcode on picking"

    picking_id = fields.Many2one(
        comodel_name="stock.picking", string="Picking", readonly=True
    )
    picking_state = fields.Selection(related="picking_id.state")
    picking_ids = fields.Many2many(
        comodel_name="stock.picking", string="Pickings", readonly=True
    )
    picking_product_qty = fields.Float(
        string="Picking quantities", digits="Product Unit of Measure", readonly=True
    )
    picking_type_code = fields.Selection(
        [("incoming", "Vendors"), ("outgoing", "Customers"), ("internal", "Internal")],
        "Type of Operation",
    )

    move_line_ids = fields.One2many(
        comodel_name="stock.move.line", compute="_compute_move_line_ids"
    )
    todo_line_ids = fields.One2many(
        string="To Do Lines",
        comodel_name="wiz.stock.barcodes.read.todo",
        inverse_name="wiz_barcode_id",
    )
    todo_line_display_ids = fields.Many2many(
        comodel_name="wiz.stock.barcodes.read.todo",
        compute="_compute_todo_line_display_ids",
    )
    todo_line_id = fields.Many2one(comodel_name="wiz.stock.barcodes.read.todo")
    picking_mode = fields.Selection([("picking", "Picking mode")])
    pending_move_ids = fields.Many2many(
        comodel_name="wiz.stock.barcodes.read.todo",
        compute="_compute_pending_move_ids",
    )
    selected_pending_move_id = fields.Many2one(
        comodel_name="wiz.stock.barcodes.read.todo"
    )
    # Track UI toggle locally so it survives refreshes; initialized from option group on change
    show_detailed_operations = fields.Boolean(default=True, store=True)
    multiplier_factor = fields.Selection(
        selection=[("1", "x1"), ("5", "x5"), ("10", "x10"), ("50", "x50")],
        default="1",
        string="Barcode multiplier",
        help="Units added per scan or +/- when not serial-tracked.",
    )
    focused_move_id = fields.Many2one(
        comodel_name="stock.move",
        string="Focused move",
        help="When set, detailed lines are filtered to this move.",
    )
    lot_target_move_line_id = fields.Many2one(
        comodel_name="stock.move.line",
        string="Line awaiting lot",
        help="When set, the next scanned lot/serial is assigned to this move line.",
    )
    show_source_location = fields.Boolean(
        compute="_compute_location_visibility",
        store=True,
        help="Helper to drive source location button visibility by picking type.",
    )
    show_destination_location = fields.Boolean(
        compute="_compute_location_visibility",
        store=True,
        help="Helper to drive destination location button visibility by picking type.",
    )
    show_partner_card = fields.Boolean(
        compute="_compute_partner_visibility",
        store=True,
        help="Hide partner card when no partner is set.",
    )
    keep_screen_values = fields.Boolean(related="option_group_id.keep_screen_values")
    show_todo_list = fields.Boolean(default=True)
    chatter_message = fields.Text()
    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        relation="wiz_stock_barcodes_read_picking_attach_rel",
        column1="wiz_id",
        column2="attachment_id",
        string="Attachments",
    )
    # Extended from stock_barcodes_read base model
    total_product_uom_qty = fields.Float(compute="_compute_total_product")
    total_product_qty_done = fields.Float(compute="_compute_total_product")
    # Technical fields to compute locations domain based on picking location
    picking_location_id = fields.Many2one(related="picking_id.location_id")
    picking_location_dest_id = fields.Many2one(related="picking_id.location_dest_id")
    company_id = fields.Many2one(related="picking_id.company_id")
    todo_line_is_extra_line = fields.Boolean(related="todo_line_id.is_extra_line")
    forced_todo_key = fields.Char()
    qty_available = fields.Float(compute="_compute_qty_available")
    partner_id = fields.Many2one("res.partner", related="picking_id.partner_id")
    partner_name = fields.Char(related="partner_id.name")
    enable_add_product = fields.Boolean(compute="_compute_enable_add_product")
    picking_move_ids = fields.One2many(
        comodel_name="stock.move",
        related="picking_id.move_ids",
        string="Moves",
        readonly=True,
    )
    instruction_override = fields.Selection(
        [
            ("source", "Scan source location"),
            ("dest", "Scan destination location"),
            ("lot", "Scan lot/serial"),
        ],
        string="Instruction Override",
        default=False,
    )
    instruction_text = fields.Char(
        compute="_compute_instruction_text",
        store=False,
        readonly=True,
    )

    @api.depends(
        "picking_id",
        "picking_id.move_line_ids",
        "picking_id.move_line_ids.qty_done",
        "picking_id.move_line_ids.qty_picked",
    )
    def _compute_move_line_ids(self):
        """Expose picking move lines to the wizard view."""
        for rec in self:
            if rec.picking_id:
                lines = rec.picking_id.move_line_ids
                if rec.focused_move_id:
                    lines = lines.filtered(lambda l: l.move_id == rec.focused_move_id)
                rec.move_line_ids = lines
            else:
                rec.move_line_ids = False

    def action_show_detailed_operations(self):
        self.show_detailed_operations = not self.show_detailed_operations

    def action_cycle_multiplier(self):
        order = ["1", "5", "10", "50"]
        next_idx = (order.index(self.multiplier_factor) + 1) % len(order)
        self.multiplier_factor = order[next_idx]
        return True

    def _get_multiplier(self, product):
        if product.tracking == "serial":
            return 1.0
        return float(self.multiplier_factor or 1.0)

    def action_focus_move(self, todo_line_id):
        todo = self.env["wiz.stock.barcodes.read.todo"].browse(todo_line_id)
        if todo and todo.stock_move_ids:
            # Toggle focus: if already focused on this move, clear
            if self.focused_move_id == todo.stock_move_ids[:1]:
                self.focused_move_id = False
            else:
                self.focused_move_id = todo.stock_move_ids[:1]
        return True

    def action_toggle_todo_list(self):
        self.show_todo_list = not self.show_todo_list
        return True

    def action_clear_context(self):
        """Clear product/lot context so the next scan starts fresh."""
        self.ensure_one()
        self.product_id = False
        self.lot_id = False
        self.lot_name = False
        self.lot_target_move_line_id = False
        self.packaging_id = False
        self.packaging_qty = 0.0
        self.product_qty = 0.0
        self.manual_entry = False
        self.last_product_id = False
        self.last_lot_identifier = False
        self.last_scan_barcode = False
        self.last_scan_at = False
        self._reset_instruction_override()
        self._log_debug_state("clear_context")
        return True

    def action_post_chatter_message(self):
        self.ensure_one()
        if self.picking_id and self.chatter_message:
            self.picking_id.message_post(
                body=self.chatter_message, attachment_ids=self.attachment_ids.ids
            )
            self.chatter_message = False
            self.attachment_ids = [(5, 0, 0)]
        return True

    @api.depends(
        "instruction_override", "product_id", "product_tracking", "lot_id", "lot_name"
    )
    def _compute_instruction_text(self):
        for rec in self:
            _logger.info(
                "[BARCODE UI] compute instruction | override=%s product=%s tracking=%s lot_id=%s lot_name=%s",
                rec.instruction_override,
                rec.product_id.display_name if rec.product_id else None,
                rec.product_id.tracking if rec.product_id else rec.product_tracking,
                rec.lot_id.display_name if rec.lot_id else None,
                rec.lot_name,
            )
            if rec.instruction_override == "source":
                rec.instruction_text = _("Scan source location")
                continue
            if rec.instruction_override == "dest":
                rec.instruction_text = _("Scan destination location")
                continue
            if rec.instruction_override == "lot":
                rec.instruction_text = _("Scan lot/serial")
                continue

            if not rec.product_id:
                rec.instruction_text = _("Scan a product to start")
                continue

            product_name = rec.product_id.display_name
            lot_label = rec.lot_id.display_name or rec.lot_name
            tracking = rec.product_id.tracking or rec.product_tracking
            if tracking in ("none", False):
                rec.instruction_text = _(
                    "Product %(product)s: scan to add quantity, or scan another product to switch.",
                    product=product_name,
                )
            else:
                if rec.lot_id or rec.lot_name:
                    rec.instruction_text = _(
                        "Product %(product)s (L/SN %(lot)s): scan lot/serial to add quantity, or scan another product to switch.",
                        product=product_name,
                        lot=lot_label,
                    )
                else:
                    rec.instruction_text = _(
                        "Product %(product)s: scan lot/serial for this product to start counting.",
                        product=product_name,
                    )

    def _compute_total_product(self):
        for rec in self:
            rec.total_product_uom_qty = 0.0
            rec.total_product_qty_done = 0.0

    def _reset_instruction_override(self):
        if self.instruction_override:
            self.instruction_override = False
            self.lot_target_move_line_id = False
            self._compute_instruction_text()

    def _notify_qty_change(self):
        payload = {
            "type": "barcode_qty_change",
            "wiz_id": self.id,
        }
        bus = self.env["bus.bus"]
        try:
            bus._sendone(self._cr.dbname, "stock_barcodes_scan", payload)
        except TypeError:
            bus._sendone("stock_barcodes_scan", payload)

    def _refresh_todo_lines(self):
        self.todo_line_ids._compute_qty_done()
        self.todo_line_ids._compute_quantity()
        self.todo_line_ids._compute_state()
        self.todo_line_ids.invalidate_recordset()
        self.invalidate_recordset()

    @api.depends("picking_type_code")
    def _compute_location_visibility(self):
        for rec in self:
            rec.show_source_location = rec.picking_type_code in ("outgoing", "internal")
            rec.show_destination_location = rec.picking_type_code in (
                "incoming",
                "internal",
            )

    @api.depends("partner_id")
    def _compute_partner_visibility(self):
        for rec in self:
            rec.show_partner_card = bool(rec.partner_id)

    def _open_location_picker(self, target):
        self.ensure_one()
        default_location = False
        if target == "source":
            default_location = self.location_id or self.picking_id.location_id
        else:
            default_location = self.location_dest_id or self.picking_id.location_dest_id

        return {
            "type": "ir.actions.act_window",
            "res_model": "wiz.stock.barcodes.pick.location",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_picking_wiz_id": self.id,
                "default_target": target,
                "default_location_id": default_location.id
                if default_location
                else False,
            },
        }

    def action_open_source_location_picker(self):
        self.instruction_override = "source"
        self._compute_instruction_text()
        return True

    def action_open_destination_location_picker(self):
        self.instruction_override = "dest"
        self._compute_instruction_text()
        return True

    def action_request_lot_scan(self):
        self.instruction_override = "lot"
        self._compute_instruction_text()
        return True

    @api.onchange("_barcode_scanned")
    def _on_barcode_scanned_picking(self):
        """Override onchange to avoid double-calling on_barcode_scanned.

        We clear the field and do not process here; the explicit RPC call from
        the JS handler (`on_barcode_scanned`) is the single source of truth.
        """
        if not self._barcode_scanned:
            return
        _logger.info(
            "[BARCODE UI] onchange _barcode_scanned fired | barcode=%s | ctx=%s",
            self._barcode_scanned,
            dict(self.env.context or {}),
        )
        # Clear field to mimic base behavior, but skip processing
        self._barcode_scanned = ""

    def on_barcode_scanned(self, barcode):
        # Guard only nested reentry (not the primary RPC). Use a dedicated flag to avoid
        # skipping the main call when JS sets barcode_processing=True.
        if self.env.context.get("onchange"):
            _logger.info(
                "[BARCODE UI] skipping scan during onchange | barcode=%s | ctx=%s",
                barcode,
                dict(self.env.context or {}),
            )
            return self._prepare_onchange_result()
        if not self.env.context.get("barcode_processing") and not self.env.context.get(
            "barcode_processing_reentry"
        ):
            _logger.info(
                "[BARCODE UI] skipping scan without barcode_processing flag | barcode=%s | ctx=%s",
                barcode,
                dict(self.env.context or {}),
            )
            return self._prepare_onchange_result()
        if self.env.context.get("barcode_processing_reentry"):
            _logger.warning(
                "[BARCODE UI] reentry suppressed in picking.on_barcode_scanned | barcode=%s",
                barcode,
            )
            return self._prepare_onchange_result()

        cleaned = self._clean_barcode_scanned(barcode)
        # Skip if just processed moments ago (guards onchange + RPC double fire)
        if self._is_recent_duplicate_scan(cleaned, threshold_ms=1200):
            _logger.info(
                "[BARCODE UI] duplicate scan suppressed in picking.on_barcode_scanned | barcode=%s",
                cleaned,
            )
            return self._prepare_onchange_result()
        # Stack sample to trace double triggers
        _logger.info(
            "[BARCODE UI] picking.on_barcode_scanned entry | barcode=%s | ctx=%s | stack=%s",
            cleaned,
            dict(self.env.context or {}),
            "".join(traceback.format_stack(limit=6)),
        )
        # Propagate a context flag so nested calls won't re-run processing
        self = self.with_context(barcode_processing_reentry=True)

        # Allow base duplicate guard (sets last_scan_* after success)
        super().on_barcode_scanned(cleaned)
        # Mark last scan after successful processing to block immediate repeats
        self.last_scan_barcode = cleaned
        self.last_scan_at = fields.Datetime.now()
        self._reset_instruction_override()
        self._compute_instruction_text()
        self._broadcast_refresh()
        self._log_debug_state("picking_on_barcode_scanned")
        return self._prepare_onchange_result()

    def dummy_on_barcode_scanned(self, barcode=None):
        """Ignore dummy scan calls to avoid double-processing the same barcode."""
        cleaned_barcode = (
            self._clean_barcode_scanned(barcode) if barcode else self.barcode
        )
        _logger.info(
            "[BARCODE UI] dummy_on_barcode_scanned ignored | barcode=%s",
            cleaned_barcode,
        )
        # Just refresh the UI without processing a second time
        self._reset_instruction_override()
        self._compute_instruction_text()
        self._broadcast_refresh()
        return self._prepare_onchange_result()

    def _broadcast_refresh(self):
        """Nudge the client to reload the record after a scan.

        The barcode widget listens on channel "barcode_reload" and reacts to
        notifications of type "stock_barcodes_refresh_data" by reloading and
        re-rendering the form (including the instructions card).
        """
        payload = {"type": "stock_barcodes_refresh_data"}
        bus = self.env["bus.bus"]
        try:
            bus._sendone(self._cr.dbname, "barcode_reload", payload)
        except TypeError:
            bus._sendone("barcode_reload", payload)
        _logger.debug(
            "[BARCODE UI][DEBUG] broadcast refresh | channel=barcode_reload payload=%s",
            payload,
        )

    def process_barcode(self, barcode):
        """Handle special one-shot assignment flows before the default logic.

        When an instruction override is active (location or lot requests), we
        bypass the normal product-first flow and handle the requested entity,
        then let the standard logic take over otherwise. Overrides are reset by
        the barcode onchange wrapper after this call.
        """
        if self.instruction_override:
            self.barcode = self._clean_barcode_scanned(barcode)
            self._log_debug_state(
                "process_barcode_override_start",
                {"override": self.instruction_override, "barcode": self.barcode},
            )

            if self.instruction_override == "source":
                if self.process_barcode_location_id():
                    if self.picking_id:
                        self.picking_id.write({"location_id": self.location_id.id})
                    self._set_messagge_info("info", _("Source location set"))
                    self._log_debug_state("process_barcode_override_source_success")
                    return True
                self._set_messagge_info(
                    "not_found", _("Source location not recognized")
                )
                self.play_sounds(False)
                self._log_debug_state("process_barcode_override_source_fail")
                return False

            if self.instruction_override == "dest":
                if self.process_barcode_location_dest_id():
                    if self.picking_id:
                        self.picking_id.write(
                            {"location_dest_id": self.location_dest_id.id}
                        )
                    self._set_messagge_info("info", _("Destination location set"))
                    self._log_debug_state("process_barcode_override_dest_success")
                    return True
                self._set_messagge_info(
                    "not_found", _("Destination location not recognized")
                )
                self.play_sounds(False)
                self._log_debug_state("process_barcode_override_dest_fail")
                return False

            if self.instruction_override == "lot":
                res = self.process_barcode_lot_id()
                if res:
                    # If a specific move line requested the change, update its lot in place
                    target_line = self.lot_target_move_line_id
                    if target_line:
                        if target_line.product_id.tracking not in ("lot", "serial"):
                            self._set_messagge_info(
                                "not_found",
                                _(
                                    "Lot/serial change is only allowed for tracked storable products."
                                ),
                            )
                            self.play_sounds(False)
                            self._log_debug_state(
                                "process_barcode_override_lot_target_not_tracked",
                                {
                                    "target_line": target_line.id,
                                    "line_product": target_line.product_id.id,
                                },
                            )
                            return False
                        if (
                            self.product_id
                            and target_line.product_id != self.product_id
                        ):
                            self._set_messagge_info(
                                "not_found",
                                _("Scanned lot does not match the line product"),
                            )
                            self.play_sounds(False)
                            self._log_debug_state(
                                "process_barcode_override_lot_product_mismatch",
                                {
                                    "target_line": target_line.id,
                                    "line_product": target_line.product_id.id,
                                    "scan_product": self.product_id.id,
                                },
                            )
                            return False
                        vals = {}
                        if self.lot_id:
                            vals.update({"lot_id": self.lot_id.id, "lot_name": False})
                        elif self.lot_name:
                            vals.update({"lot_id": False, "lot_name": self.lot_name})
                        if vals:
                            target_line.write(vals)
                            # If another line already has this product/lot and matching keys, merge quantities
                            merge_candidates = (
                                target_line.picking_id.move_line_ids.filtered(
                                    lambda l: l.id != target_line.id
                                    and l.product_id == target_line.product_id
                                    and (
                                        (
                                            target_line.lot_id
                                            and l.lot_id == target_line.lot_id
                                        )
                                        or (
                                            target_line.lot_name
                                            and l.lot_name == target_line.lot_name
                                        )
                                    )
                                    and l.package_id == target_line.package_id
                                    and l.result_package_id
                                    == target_line.result_package_id
                                    and l.owner_id == target_line.owner_id
                                    and l.location_id == target_line.location_id
                                    and l.location_dest_id
                                    == target_line.location_dest_id
                                )
                            )
                            if merge_candidates:
                                dest_line = merge_candidates[0]
                                new_qty = (
                                    dest_line.qty_picked or dest_line.quantity or 0.0
                                ) + (
                                    target_line.qty_picked
                                    or target_line.quantity
                                    or 0.0
                                )
                                dest_line.write(
                                    {"qty_picked": new_qty, "quantity": new_qty}
                                )
                                target_line.unlink()
                                self._log_debug_state(
                                    "process_barcode_override_lot_merge",
                                    {
                                        "merged_into": dest_line.id,
                                        "removed": target_line.id,
                                        "new_qty": new_qty,
                                    },
                                )
                        # Clear the override/target and refresh UI/todo aggregates
                        self.lot_target_move_line_id = False
                        self._reset_instruction_override()
                        self._refresh_todo_lines()
                        self._notify_qty_change()
                        self._broadcast_refresh()
                        self._log_debug_state(
                            "process_barcode_override_lot_target_applied",
                            {"target_line": target_line.id, "vals": vals},
                        )
                        return True

                    # Fallback to standard flow: treat as a normal lot scan and confirm
                    if self.product_tracking in ("lot", "serial"):
                        confirm_res = self.action_confirm()
                        if confirm_res:
                            self.last_scan_barcode = self.barcode
                            self.last_scan_at = fields.Datetime.now()
                        self._log_debug_state(
                            "process_barcode_override_lot_success",
                            {"confirmed": bool(confirm_res)},
                        )
                        return confirm_res
                    self._log_debug_state(
                        "process_barcode_override_lot_success_untracked"
                    )
                    return True
                self._set_messagge_info(
                    "not_found", _("Lot/serial not recognized for this product")
                )
                self.play_sounds(False)
                self._log_debug_state("process_barcode_override_lot_fail")
                return False

        return super().process_barcode(barcode)

    def action_clear_focus(self):
        self.focused_move_id = False
        return True

    @api.depends("picking_state")
    def _compute_enable_add_product(self):
        for rec in self:
            rec.enable_add_product = rec.picking_state != "done"

    @api.depends("todo_line_id")
    def _compute_todo_line_display_ids(self):
        """Technical field to display only the first record in kanban view"""
        self.todo_line_display_ids = self.todo_line_id

    @api.depends("todo_line_ids", "picking_id.move_line_ids.qty_picked")
    def _compute_pending_move_ids(self):
        if self.option_group_id.show_pending_moves:
            self.pending_move_ids = self.todo_line_ids.filtered(
                lambda t: t.state == "pending"
                and any(
                    sm.barcode_backorder_action == "pending" for sm in t.stock_move_ids
                )
            )
        else:
            self.pending_move_ids = self.todo_line_ids.filtered(
                lambda t: not t.is_extra_line
            )

    @api.depends(
        "todo_line_ids", "todo_line_ids.qty_done", "picking_id.move_line_ids.qty_picked"
    )
    def _compute_qty_available(self):
        for rec in self:
            rec.qty_available = 0.0
            done_move_lines = rec.todo_line_ids.mapped(
                "stock_move_ids.move_line_ids"
            ).filtered(lambda sml: sml.qty_picked)
            for sml in done_move_lines:
                over_done_qty = float_round(
                    sml.quantity - sml.quantity_product_uom,
                    precision_rounding=sml.product_uom_id.rounding,
                )
                if over_done_qty > 0.0:
                    rec.qty_available -= over_done_qty

    def name_get(self):
        return [
            (
                rec.id,
                "{} - {} - {}".format(
                    _("Barcode reader"),
                    rec.picking_id.name or rec.picking_type_code,
                    self.env.user.name,
                ),
            )
            for rec in self
        ]

    @api.onchange("picking_id")
    def onchange_picking_id(self):
        self.fill_pending_moves()
        self.determine_todo_action()

    @api.onchange("option_group_id")
    def _onchange_option_group_id_show_detailed(self):
        if self.option_group_id:
            self.show_detailed_operations = (
                self.option_group_id.show_detailed_operations
            )

    def get_sorted_move_lines(self, move_lines):
        location_field = self.option_group_id.location_field_to_sort
        if not location_field:
            if self.picking_id.picking_type_code in ["incoming", "internal"]:
                location_field = "location_dest_id"
            else:
                location_field = "location_id"
        if self.option_group_id.source_pending_moves == "move_line_ids":
            move_lines = move_lines.sorted(
                lambda sml: (
                    sml[location_field].posx,
                    sml[location_field].posy,
                    sml[location_field].posz,
                    sml[location_field].name,
                )
            )
        else:
            # Stock moves
            move_lines = move_lines.sorted(
                lambda sm: (
                    (sm.move_line_ids[:1] or sm)[location_field].posx,
                    (sm.move_line_ids[:1] or sm)[location_field].posy,
                    (sm.move_line_ids[:1] or sm)[location_field].posz,
                    (sm.move_line_ids[:1] or sm)[location_field].name,
                )
            )
        return move_lines

    def _get_stock_move_lines_todo(self):
        move_lines = self.picking_id.move_line_ids.filtered(
            lambda ml: (not ml.barcode_scan_state or ml.barcode_scan_state == "pending")
            and ml.qty_picked < ml.quantity
        )
        return move_lines

    def fill_pending_moves(self):
        self.fill_todo_records()

    def get_moves_or_move_lines(self):
        if self.option_group_id.source_pending_moves == "move_line_ids":
            return self.picking_id.move_line_ids.filtered(lambda ln: ln.move_id)
        else:
            return self.picking_id.move_ids

    def get_moves(self):
        return self.picking_id.move_ids

    def fill_todo_records(self):
        move_lines = self.get_sorted_move_lines(self.get_moves_or_move_lines())
        self.fill_records([move_lines])

    @api.model
    def _get_fields_filled_special(self):
        return [
            "location_id",
            "location_dest_id",
            "package_id",
            "result_package_id",
            "product_qty",
        ]

    def determine_todo_action(self, forced_todo_line=False):
        self.visible_force_done = self.env.context.get("visible_force_done", False)
        if not self.option_group_id.barcode_guided_mode == "guided":
            return False
        self.todo_line_id = (
            forced_todo_line
            or self.todo_line_ids.filtered(lambda t: t._origin.state == "pending")[:1]
        )
        self.todo_line_id._compute_qty_done()
        move_line = self.todo_line_id
        self.guided_location_id = move_line.location_id
        self.guided_location_dest_id = move_line.location_dest_id
        self.guided_product_id = move_line.product_id
        self.guided_lot_id = move_line.lot_id

        if self.option_group_id.get_option_value("location_id", "filled_default"):
            self.location_id = move_line.location_id
        elif self.picking_type_code != "incoming":
            self.location_id = False
        if self.option_group_id.get_option_value("location_dest_id", "filled_default"):
            self.location_dest_id = move_line.location_dest_id
        elif self.picking_type_code != "outgoing":
            self.location_dest_id = False
        if self.option_group_id.get_option_value("package_id", "filled_default"):
            self.package_id = move_line.package_id
        if not self.keep_result_package and self.option_group_id.get_option_value(
            "result_package_id", "filled_default"
        ):
            self.result_package_id = move_line.result_package_id
        if self.option_group_id.get_option_value("product_qty", "filled_default"):
            self.product_qty = move_line.product_uom_qty - move_line.qty_picked
        else:
            if not self.visible_force_done:
                self.product_qty = 0.0
        # Try to fill data of any field defined in options
        processed_fields = self._get_fields_filled_special()
        for option in self.option_group_id.option_ids:
            if option.field_name in processed_fields:
                continue
            if option.field_name == "lot_id" and self.lot_id:
                # Keep the scanned lot when switching lots for the same product
                continue
            if option.filled_default:
                self[option.field_name] = move_line[option.field_name]
            else:
                if not self.env.context.get("skip_clean_values", False):
                    self[option.field_name] = False
        self.update_fields_after_determine_todo(move_line)
        self.action_show_step()

    def update_fields_after_determine_todo(self, move_line):
        # When guided mode selects a todo card (wiz.stock.barcodes.read.todo), reuse its
        # progress metric. Some todo records are aggregates and don't carry qty_picked;
        # fall back to qty_done/quantity to avoid attribute errors across operation types.
        if hasattr(move_line, "qty_picked"):
            self.picking_product_qty = move_line.qty_picked
        elif hasattr(move_line, "qty_done"):
            self.picking_product_qty = move_line.qty_done
        else:
            self.picking_product_qty = (
                move_line.quantity if hasattr(move_line, "quantity") else 0.0
            )

    def action_done(self):
        if not super().action_done():
            return False
        _logger.info(
            "[BARCODE PICK] action_done entry | pick=%s product=%s tracking=%s lot_id=%s lot_name=%s product_qty=%s",
            self.picking_id.name if self.picking_id else None,
            self.product_id.display_name if self.product_id else None,
            self.product_id.tracking if self.product_id else None,
            self.lot_id.id if self.lot_id else None,
            self.lot_name,
            self.product_qty,
        )
        if not self.picking_id:
            self._set_messagge_info("info", _("No picking selected"))
            return False
        return self._apply_scan_to_move_lines()

    def _apply_scan_to_move_lines(self):
        _logger.info(
            "[BARCODE PICK] apply_scan start | wiz=%s picking=%s product=%s lot_id=%s lot_name=%s product_qty=%s multiplier=%s",
            self.id,
            self.picking_id.name if self.picking_id else None,
            self.product_id.display_name if self.product_id else None,
            self.lot_id.id if self.lot_id else None,
            self.lot_name,
            self.product_qty,
            self.multiplier_factor,
        )
        picking = self.picking_id
        # Ensure we see freshly created move lines from previous scans
        picking.invalidate_recordset()
        picking.move_line_ids.invalidate_recordset()
        product = self.product_id
        lot = self.lot_id
        lot_name = self.lot_name
        qty = self.product_qty or 1.0
        raw_qty = qty
        multiplier = self._get_multiplier(product)
        # For tracked products, each scan represents a unit for the scanned lot/serial;
        # use the multiplier only for non-serial tracking. Ignore prefilled qty from guided mode.
        if product.tracking in ("lot", "serial") and (lot or lot_name):
            qty = 1.0 if product.tracking == "serial" else multiplier
        elif product.tracking != "serial":
            qty = qty * multiplier

        _logger.info(
            "[BARCODE PICK] qty compute | pick=%s product=%s tracking=%s lot_id=%s lot_name=%s product_qty_field=%s raw_qty=%s multiplier=%s final_qty=%s",
            picking.name,
            product.display_name,
            product.tracking,
            lot.id if lot else None,
            lot_name,
            self.product_qty,
            raw_qty,
            multiplier,
            qty,
        )

        # Resolve locations
        source = self.location_id or picking.location_id
        dest = self.location_dest_id or picking.location_dest_id

        moves = picking.move_ids.filtered(lambda m: m.product_id == product)
        if not moves:
            self._set_messagge_info("not_found", _("No move for this product"))
            return False

        # Block duplicate serials
        if product.tracking == "serial" and (lot or lot_name):
            dup = picking.move_line_ids.filtered(
                lambda l: l.product_id == product
                and ((lot and l.lot_id == lot) or (lot_name and l.lot_name == lot_name))
            )
            if dup:
                self._set_messagge_info("more_match", _("Serial already scanned"))
                return False

        def _lot_match(line):
            if lot:
                return line.lot_id == lot
            if lot_name:
                return line.lot_name == lot_name
            return not line.lot_id and not line.lot_name

        package = self.package_id or False
        result_package = self.result_package_id or False
        owner = self.owner_id or False

        def _field_match(line_value, scanned_value):
            """Match many2one fields treating a falsy scanned value as empty."""
            if scanned_value:
                return line_value == scanned_value
            return not bool(line_value)

        def _match_common(line):
            return (
                line.product_id == product
                and _lot_match(line)
                and _field_match(line.package_id, package)
                and _field_match(line.result_package_id, result_package)
                and _field_match(line.owner_id, owner)
            )

        def _debug_line(line):
            return {
                "id": line.id,
                "move": line.move_id.id,
                "qty_picked": line.qty_picked,
                "qty": line.quantity,
                "lot_id": line.lot_id.id if line.lot_id else False,
                "lot_name": line.lot_name,
                "package_id": line.package_id.id if line.package_id else False,
                "result_package_id": line.result_package_id.id
                if line.result_package_id
                else False,
                "owner_id": line.owner_id.id if line.owner_id else False,
                "location_id": line.location_id.id if line.location_id else False,
                "location_dest_id": line.location_dest_id.id
                if line.location_dest_id
                else False,
            }

        # Strict match: all key fields including source/dest
        candidate_lines = picking.move_line_ids.filtered(
            lambda l: _match_common(l)
            and (not source or l.location_id == source)
            and (not dest or l.location_dest_id == dest)
        )

        _logger.debug(
            "[BARCODE PICK] candidate pass1 | product=%s lot=%s lot_name=%s source=%s dest=%s package=%s result_package=%s owner=%s count=%s ids=%s",
            product.display_name,
            lot.id if lot else None,
            lot_name,
            source.id if source else None,
            dest.id if dest else None,
            package.id if package else None,
            result_package.id if result_package else None,
            owner.id if owner else None,
            len(candidate_lines),
            candidate_lines.ids,
        )

        # If nothing found, prefer lines within the current todo/focused move, relaxing locations
        if (
            not candidate_lines
            and self.todo_line_id
            and self.todo_line_id.stock_move_ids
        ):
            moves_scope = self.todo_line_id.stock_move_ids
            candidate_lines = picking.move_line_ids.filtered(
                lambda l: _match_common(l) and l.move_id in moves_scope
            )
            _logger.debug(
                "[BARCODE PICK] candidate pass2 (todo scoped) | moves_scope=%s count=%s ids=%s",
                moves_scope.ids,
                len(candidate_lines),
                candidate_lines.ids,
            )

        # Final fallback: any line in the picking that matches product/lot/package/owner, ignoring locations
        if not candidate_lines:
            candidate_lines = picking.move_line_ids.filtered(_match_common)
            _logger.debug(
                "[BARCODE PICK] candidate pass3 (fallback) | count=%s ids=%s",
                len(candidate_lines),
                candidate_lines.ids,
            )

        if not candidate_lines:
            all_product_lines = picking.move_line_ids.filtered(
                lambda l: l.product_id == product
            )
            _logger.debug(
                "[BARCODE PICK] no candidate found; product lines snapshot=%s",
                [_debug_line(l) for l in all_product_lines[:5]],
            )
            _logger.info(
                "[BARCODE PICK] no candidate found; product lines count=%s ids=%s",
                len(all_product_lines),
                all_product_lines.ids,
            )

        _logger.info(
            "[BARCODE PICK] candidate lines | pick=%s product=%s tracking=%s lot=%s lot_name=%s source=%s dest=%s count=%s",
            picking.name,
            product.display_name,
            product.tracking,
            lot.id if lot else None,
            lot_name,
            source.id if source else None,
            dest.id if dest else None,
            len(candidate_lines),
        )

        def _clean_vals(values):
            allowed_fields = self.env["stock.move.line"]._fields
            return {k: v for k, v in values.items() if k in allowed_fields}

        line = candidate_lines[:1]
        if line:
            # If lot differs from the line, force a new line instead of mutating the lot on the existing one
            if (lot and line.lot_id and line.lot_id != lot) or (
                lot_name and line.lot_name and line.lot_name != lot_name
            ):
                _logger.info(
                    "[BARCODE PICK] new line due to lot mismatch | pick=%s product=%s existing_lot=%s scanned_lot=%s scanned_name=%s",
                    picking.name,
                    product.display_name,
                    line.lot_id.display_name,
                    lot.display_name if lot else None,
                    lot_name,
                )
                line = False

        if line:
            new_qty = (line.qty_picked or 0.0) + qty
            vals = _clean_vals({"qty_picked": new_qty, "quantity": new_qty})
            _logger.info(
                "[BARCODE PICK] increment line | pick=%s product=%s lot=%s lot_name=%s old_qty=%s add=%s new_qty=%s",
                picking.name,
                product.display_name,
                line.lot_id.display_name,
                line.lot_name,
                line.qty_picked,
                qty,
                new_qty,
            )
            line.write(vals)
        else:
            move = moves[:1]
            vals = _clean_vals(
                {
                    "picking_id": picking.id,
                    "move_id": move.id,
                    "product_id": product.id,
                    "product_uom_id": move.product_uom.id,
                    "qty_picked": qty,
                    "quantity": qty,
                    "location_id": source.id if source else move.location_id.id,
                    "location_dest_id": dest.id if dest else move.location_dest_id.id,
                    "lot_id": lot.id if lot else False,
                    "lot_name": lot_name if lot_name else False,
                    "barcode_scan_state": "done",
                }
            )
            _logger.info(
                "[BARCODE PICK] create line | pick=%s product=%s lot=%s lot_name=%s qty=%s source=%s dest=%s",
                picking.name,
                product.display_name,
                lot.display_name if lot else None,
                lot_name,
                qty,
                source.display_name if source else None,
                dest.display_name if dest else None,
            )
            self.env["stock.move.line"].create(vals)

        # Recompute todo aggregates and notify UI listeners so cards reorder
        self._refresh_todo_lines()
        self._notify_qty_change()
        return True

    def update_keep_values(self, keep_vals):
        options = self.option_group_id.option_ids
        fields_to_keep = options.filtered(
            lambda op: self._fields[op.field_name].type != "float"
        ).mapped("field_name")
        self.update({f_name: keep_vals[f_name] for f_name in fields_to_keep})

    def action_manual_entry(self):
        result = super().action_manual_entry()
        if result:
            self.action_done()
        return result

    def action_go_back(self):
        """Navigate back: prefer browser history/back, else barcode menu."""
        show_menu = self.env.context.get(
            "default_display_menu"
        ) or self.env.context.get("display_menu")
        _logger.info(
            "[BARCODE UI] back pressed | show_menu_ctx=%s | navigating to barcode menu",
            show_menu,
        )
        action = self.env.ref("stock_barcodes.action_stock_barcodes_menu").read()[0]
        _logger.info(
            "[BARCODE UI] navigating to barcode menu action_id=%s", action.get("id")
        )
        return action

    def _prepare_move_line_values(self, candidate_move, available_qty):
        """When we've got an out picking, the logical workflow is that
        the scanned location is the location we're getting the stock
        from"""
        picking = self.env.context.get("picking", self.picking_id)
        if not picking:
            raise ValidationError(
                _("You can not add extra moves if you have not set a picking")
            )
        # If we move all package units the result package is the same
        if (
            self.package_id
            and not self.result_package_id
            and sum(self.package_id.quant_ids.mapped("quantity")) <= self.product_qty
        ):
            self.result_package_id = self.package_id
        vals = {
            "picking_id": picking.id,
            "move_id": candidate_move.id,
            "qty_picked": available_qty,
            "product_uom_id": candidate_move.product_uom.id or self.product_id.uom_id.id
            if not self.packaging_id
            else self.packaging_id.product_uom_id.id,
            "product_id": self.product_id.id,
            "location_id": self.location_id.id,
            "location_dest_id": self.location_dest_id.id,
            "lot_id": self.lot_id.id,
            "lot_name": self.lot_id.name,
            "barcode_scan_state": "done_forced",
            "package_id": self.package_id.id,
            "result_package_id": self.result_package_id.id,
        }
        if self.owner_id:
            vals["owner_id"] = self.owner_id.id
        return vals

    def _states_move_allowed(self):
        move_states = ["assigned", "partially_available"]
        if self.confirmed_moves:
            move_states.append("confirmed")
        return move_states

    def _prepare_stock_moves_domain(self):
        domain = [
            ("product_id", "=", self.product_id.id),
            ("picking_id.picking_type_id.code", "=", self.picking_type_code),
            ("state", "in", self._states_move_allowed()),
        ]
        if self.picking_id:
            domain.append(("picking_id", "=", self.picking_id.id))
        return domain

    def _check_guided_restrictions(self):
        # Check restrictions in guided mode
        if self.option_group_id.barcode_guided_mode == "guided":
            if (
                self.option_group_id.get_option_value("product_id", "forced")
                and self.product_id != self.todo_line_id.product_id
            ):
                self._set_messagge_info("more_match", _("Wrong product"))
                return False
        return True

    def _get_candidate_stock_move_lines(self, moves_todo, sml_vals):
        candidate_lines = moves_todo.mapped("move_line_ids").filtered(
            lambda line: (
                # l.picking_id == self.picking_id and
                line.location_id == self.location_id
                and line.location_dest_id == self.location_dest_id
                and line.product_id == self.product_id
            )
        )
        # Try to reuse existing stock move lines updating locations
        if not candidate_lines:
            location_option = self.option_group_id.option_ids.filtered(
                lambda op: op.field_name == "location_id"
            )
            if not location_option.forced:
                candidate_lines = moves_todo.mapped("move_line_ids").filtered(
                    lambda line: (
                        line.location_dest_id == self.location_dest_id
                        and line.product_id == self.product_id
                        and line.location_id == self.picking_location_id
                    )
                )
                if candidate_lines and self.location_id:
                    sml_vals.update({"location_id": self.location_id.id})
        if not candidate_lines:
            location_dest_option = self.option_group_id.option_ids.filtered(
                lambda op: op.field_name == "location_dest_id"
            )
            if not location_dest_option.forced:
                candidate_lines = moves_todo.mapped("move_line_ids").filtered(
                    lambda line: (
                        line.location_id == self.location_id
                        and line.product_id == self.product_id
                        and line.location_dest_id == self.picking_location_dest_id
                    )
                )
                if candidate_lines and self.location_dest_id:
                    sml_vals.update({"location_dest_id": self.location_dest_id.id})
        return candidate_lines

    def _get_candidate_line_domain(self):
        """To be extended for other modules"""
        domain = []
        if self.env.user.has_group("stock.group_tracking_lot"):
            # Check if sml is created with complete content so we fill result package to
            # set the complete package
            if (
                len(self.package_id.quant_ids) == 1
                and float_compare(
                    self.package_id.quant_ids.quantity,
                    self.product_qty,
                    precision_rounding=self.product_id.uom_id.rounding,
                )
                == 0
            ):
                self.result_package_id = self.package_id
            domain.extend(
                [
                    ("package_id", "=", self.package_id.id),
                    ("result_package_id", "=", self.result_package_id.id),
                ]
            )
        return domain

    def _process_stock_move_line(self):  # noqa: C901
        """
        Search assigned or confirmed stock moves from a picking operation type
        or a picking. If there is more than one picking with demand from
        scanned product the interface allow to select what picking to work.
        If only there is one picking the scan data is assigned to it.
        """
        StockMove = self.env["stock.move"]
        domain = self._prepare_stock_moves_domain()
        if self.option_group_id.barcode_guided_mode == "guided":
            moves_todo = self.todo_line_id.stock_move_ids
        elif self.picking_id:
            moves_todo = self.picking_id.move_ids.filtered(
                lambda sm: sm.product_id == self.product_id
            )
        else:
            moves_todo = StockMove.search(domain)
        sml_vals = {}
        candidate_lines = self._get_candidate_stock_move_lines(moves_todo, sml_vals)
        lines = candidate_lines.filtered(
            lambda line: (
                line.lot_id == self.lot_id and line.barcode_scan_state == "pending"
            )
        )
        # Check if exists lines with lot created if product has tracking serial
        if self.product_id.tracking == "serial":
            serial_lines = self.picking_id.move_line_ids.filtered(
                lambda sml: (
                    sml.lot_id == self.lot_id or sml.lot_name == self.lot_id.name
                )
                and sml.qty_picked >= 1.0
            )
            if serial_lines:
                self._set_messagge_info("more_match", _("S/N Already in picking"))
                return False
        # For incoming pickings the lot is not filled so we try fill it with
        # the lot scanned
        if (
            not lines
            and self.picking_type_code == "incoming"
            and self.product_id.tracking != "none"
        ):
            if (
                self.option_group_id.create_lot
                and self.product_id.tracking == "serial"
                and candidate_lines.filtered(lambda ln: ln.lot_name == self.lot_id.name)
            ):
                self.lot_id = False
                self._set_messagge_info("more_match", _("S/N already created"))
                return False
            lines = candidate_lines.filtered(
                lambda line: (not line.lot_id and line.barcode_scan_state == "pending")
            )
            if lines:
                sml_vals.update(
                    {"lot_id": self.lot_id.id, "lot_name": self.lot_id.name}
                )
        candidate_domain = self._get_candidate_line_domain()
        if candidate_domain:
            lines = lines.filtered_domain(candidate_domain)
        # Take into account all smls to get a line to update
        if not lines:
            lines = candidate_lines.filtered(lambda ln: (ln.lot_id == self.lot_id))
            if candidate_domain:
                lines = lines.filtered_domain(candidate_domain)
        available_qty = self.product_qty
        max_quantity = sum(
            sm.product_uom_qty
            - (sm.qty_picked if sm.qty_picked != sm.product_uom_qty else 0)
            for sm in moves_todo
        )
        if (
            not self.option_group_id.code == "REL"
            and not self.env.context.get("force_create_move", False)
            and not self.env.context.get("manual_picking", False)
            and float_compare(
                available_qty,
                max_quantity,
                precision_rounding=self.product_id.uom_id.rounding,
            )
            > 0
        ):
            self._set_messagge_info(
                "more_match", _("Quantities scanned are higher than necessary.")
            )
            self.visible_force_done = True
            self._set_focus_on_qty_input("product_qty")
            return False
        move_lines_dic = {}
        context = self.env.context
        lot_info = {}
        if self.lot_id:
            lot_info = {"lot_id": self.lot_id.id, "lot_name": self.lot_id.name}
        elif self.lot_name:
            lot_info = {"lot_id": False, "lot_name": self.lot_name}
        for line in lines:
            if line.quantity_product_uom and len(lines) > 1:
                assigned_qty = min(
                    max(line.quantity_product_uom - line.quantity, 0.0), available_qty
                )
            else:
                assigned_qty = available_qty
            # Not increase qty done if user reads a complete package
            if (
                self.result_package_id
                and self.package_id
                and self.result_package_id == self.package_id
            ):
                qty_done = assigned_qty
            elif context.get("no_increase_qty_done", False) and assigned_qty > 0:
                # Do not increase the quantity, if the quantity is > 0
                qty_done = assigned_qty
            else:
                qty_done = line.qty_picked + assigned_qty
            sml_vals.update(
                {
                    "qty_picked": qty_done,
                    # "quantity": qty_done,
                    "result_package_id": self.result_package_id.id,
                }
            )
            if lot_info:
                sml_vals.update(lot_info)
            # Add or remove result_pselfackage_id
            package_qty_available = sum(
                self.package_id.quant_ids.filtered(
                    lambda q: q.lot_id == self.lot_id
                ).mapped("quantity")
            )
            if sml_vals["qty_picked"] >= package_qty_available:
                if not self.result_package_id:
                    sml_vals.update({"result_package_id": self.package_id.id})
            elif line.result_package_id == line.package_id:
                sml_vals.update({"result_package_id": False})
            self._update_stock_move_line(line, sml_vals)
            if line.qty_picked >= line.quantity:
                line.barcode_scan_state = "done"
            elif self.env.context.get("done_forced"):
                line.barcode_scan_state = "done_forced"
            available_qty -= assigned_qty
            if assigned_qty:
                move_lines_dic[line.id] = assigned_qty
            if (
                float_compare(
                    available_qty,
                    0.0,
                    precision_rounding=line.product_id.uom_id.rounding,
                )
                < 1
            ):
                break
        if (
            float_compare(
                available_qty, 0, precision_rounding=self.product_id.uom_id.rounding
            )
            > 0
        ):
            # Create an extra stock move line if this product has an
            # initial demand.
            # When the sml is created we need to link to a stock move but user can read
            # any other product in guided mode so we must ensure that the sm linked to
            # moves todo records have the same product. If not we search any sm linked
            # to the picking.
            moves_to_link = moves_todo.filtered(
                lambda mv: mv.product_id == self.product_id
            )
            move_to_link_in_todo_line = True
            if not moves_to_link:
                move_to_link_in_todo_line = False
                moves_to_link = self.picking_id.move_ids.filtered(
                    lambda mv: mv.product_id == self.product_id
                )
            # Do not create new stock moves from the barcode UI. If no move matches
            # this product, abort and notify the user so they adjust the picking
            # manually in the form view.
            if not moves_to_link:
                self._set_messagge_info(
                    "not_found",
                    _(
                        "No move found for this product in the picking. Update the picking first."
                    ),
                )
                self.play_sounds(False)
                _logger.info(
                    "[BARCODE PICK] no move to link; skipping creation | pick=%s product=%s",
                    self.picking_id.name if self.picking_id else None,
                    self.product_id.display_name,
                )
                return move_lines_dic
            stock_move_lines = self.create_new_stock_move_line(
                moves_to_link, available_qty
            )
            for sml in stock_move_lines:
                # Do not create or alter stock moves here; barcode UI must only work
                # with existing moves/lines.
                move_lines_dic[sml.id] = sml.qty_picked
            # Ensure that the state of stock_move linked to the sml read is assigned
            stock_move_lines.move_id.filtered(
                lambda sm: sm.state == "draft"
            ).state = "assigned"
            # When create new stock move lines and we are in guided mode we need
            # link this new lines to the todo line details
            # If user scan a product distinct of the todo line we need link to other
            # alternative move
            if self.option_group_id.source_pending_moves != "move_line_ids":
                if move_to_link_in_todo_line and self.todo_line_id:
                    todo_line = self.todo_line_id
                else:
                    todo_line = self.todo_line_ids.filtered(
                        lambda ln: ln.product_id == self.product_id
                    )
                todo_line.line_ids = [(4, sml.id) for sml in stock_move_lines]
        self.update_fields_after_process_stock(moves_todo)
        return move_lines_dic

    def _update_stock_move_line(self, line, sml_vals):
        """Update stock move line with values. Helper method to be inherited"""
        line.write(sml_vals)

    def create_new_stock_move_line(self, moves_todo, available_qty):
        """Create a new stock move line when a sml is not available
        for the wizard values.
        """
        return self.env["stock.move.line"].create(
            self._prepare_move_line_values(moves_todo[:1], available_qty)
        )

    def create_new_stock_move(self, sml):
        vals = {
            "name": _("New Move:") + sml.product_id.display_name,
            "product_uom": sml.product_uom_id.id,
            "product_uom_qty": sml.qty_picked,
            "state": "assigned",
            "additional": True,
            "product_id": sml.product_id.id,
            "location_id": sml.location_id.id,
            "location_dest_id": sml.location_dest_id.id,
            "picking_id": sml.picking_id.id,
        }
        new_move = self.env["stock.move"].create(vals)
        sml.move_id = new_move

    def update_fields_after_process_stock(self, moves):
        self.picking_product_qty = sum(moves.mapped("quantity"))

    def check_done_conditions(self):
        res = super().check_done_conditions()
        if (
            self.picking_type_code != "incoming"
            and float_compare(
                self.product_qty,
                self.qty_available,
                precision_rounding=self.product_id.uom_id.rounding or 1,
            )
            > 0
            and not self.env.context.get("force_create_move", False)
            and not self.option_group_id.allow_negative_quant
        ):
            self._set_messagge_info(
                "more_match", _("Quantities not available in location")
            )
            if self.option_group_id.allow_negative_quant:
                self.visible_force_done = True
            # Set focus on product_qty input box
            self._set_focus_on_qty_input("product_qty")
            return False
        if self.picking_mode == "picking_batch":
            return res
        if not self.picking_id:
            self._set_messagge_info("info", _("No picking selected"))
            return False
        return res

    def get_lot_by_removal_strategy(self):
        quants = first(
            self.env["stock.quant"]._gather(self.product_id, self.location_id)
        )
        # TODO: Perhaps update location_id from quant??
        self.lot_id = quants.lot_id

    def action_product_scaned_post(self, product):
        res = super().action_product_scaned_post(product)
        if self.auto_lot and self.picking_type_code != "incoming":
            self.get_lot_by_removal_strategy()
        return res

    def action_assign_serial(self):
        move = self.env["stock.move"].search(self._prepare_stock_moves_domain())
        if len(move) > 1:
            smls = move.move_line_ids.filtered(
                lambda ln: ln.barcode_scan_state == "pending"
            )
            move = smls[:1].move_id
        if move:
            return move.action_assign_serial()
        raise ValidationError(_("No pending lines for this product"))

    def action_put_in_pack(self):
        for picking in self.mapped("picking_id"):
            picking.action_put_in_pack()

    def action_clean_values(self):
        # Preserve current product/lot context so consecutive scans keep counting
        current_product = self.product_id
        current_lot = self.lot_id
        current_lot_name = self.lot_name
        current_last_product = getattr(self, "last_product_id", False)
        current_last_lot = getattr(self, "last_lot_identifier", False)

        res = super().action_clean_values()

        # Restore context after cleaning
        if current_product:
            self.product_id = current_product
        if current_lot:
            self.lot_id = current_lot
        if current_lot_name:
            self.lot_name = current_lot_name
        if current_last_product:
            self.last_product_id = current_last_product
        if current_last_lot:
            self.last_lot_identifier = current_last_lot

        self.selected_pending_move_id = False
        self.visible_force_done = False
        # Hide Form Edit
        self.manual_entry = False
        self.send_bus_done(
            "stock_barcodes_scan",
            {
                "type": "stock_barcodes_edit_manual",
                "payload": {
                    "manual_entry": False,
                },
            },
        )
        return res

    def _option_required_hook(self, option_required):
        if (
            option_required.field_name == "location_dest_id"
            and self.option_group_id.use_location_dest_putaway
        ):
            self.location_dest_id = self.picking_id.location_dest_id.with_context(
                avoid_location_with_reserve=True
            )._get_putaway_strategy(
                self.product_id,
                quantity=self.product_qty,
                package=self.result_package_id,
                packaging=self.packaging_id,
            )
            return bool(self.location_dest_id)
        return super()._option_required_hook(option_required)

    def _group_key(self, line):
        group_key_for_todo_records = self.option_group_id.group_key_for_todo_records
        if group_key_for_todo_records:
            return safe_eval(group_key_for_todo_records, globals_dict={"object": line})
        if self.option_group_id.source_pending_moves == "move_line_ids":
            # Group by stock move to avoid one todo card per reserved move line. When
            # receiving an already-built todo wizard record, fallback to its linked
            # stock_move_ids.
            move = False
            if hasattr(line, "move_id"):
                move = line.move_id
            elif hasattr(line, "stock_move_ids"):
                move = line.stock_move_ids[:1]
            if move:
                return (move.id,)
            return (
                line.location_id.id if hasattr(line, "location_id") else False,
                line.product_id.id if hasattr(line, "product_id") else False,
            )
        else:
            return (line.location_id.id, line.product_id.id)

    def _get_all_products_quantities_in_package(self, package):
        res = {}
        # TODO: Check if domain is applied and we must recover _get_contained_quants
        for quant in package.quant_ids:
            if quant.product_id not in res:
                res[quant.product_id] = 0
            res[quant.product_id] += quant.quantity
        return res

    def _prepare_fill_record_values(self, line, position):
        vals = {
            "wiz_barcode_id": self.id,
            "product_id": line.product_id.id,
            "name": "To do action",
            "position_index": position,
            "picking_code": line.picking_code,
        }
        if line._name == "stock.move.line":
            package_product_dic = self._get_all_products_quantities_in_package(
                line.package_id
            )
            vals.update(
                {
                    "location_id": line.location_id.id,
                    "location_dest_id": line.location_dest_id.id,
                    "lot_id": line.lot_id.id,
                    "package_id": line.package_id.id,
                    "result_package_id": line.result_package_id.id,
                    "uom_id": line.product_uom_id.id,
                    "product_uom_qty": line.move_id.product_uom_qty,
                    "product_qty_reserved": line.quantity_product_uom,
                    "line_ids": [(6, 0, line.ids)],
                    "stock_move_ids": [(6, 0, line.move_id.ids)],
                    "package_product_qty": package_product_dic
                    and package_product_dic[line.product_id]
                    or 0.0,
                    "is_stock_move_line_origin": True,
                }
            )
        else:
            vals.update(
                {
                    "location_id": (line.move_line_ids[:1] or line).location_id.id,
                    "location_dest_id": (
                        line.move_line_ids[:1] or line
                    ).location_dest_id.id,
                    "uom_id": line.product_uom.id,
                    "product_uom_qty": line.product_uom_qty,
                    "product_qty_reserved": line.move_line_ids
                    # TODO: Use reserved_qty or reserved_uom_qty
                    and sum(line.move_line_ids.mapped("quantity"))
                    or line.product_uom_qty,
                    "line_ids": [(6, 0, line.move_line_ids.ids)],
                    "stock_move_ids": [(6, 0, line.ids)],
                    "is_stock_move_line_origin": False,
                }
            )
        return vals

    def _update_fill_record_values(self, line, vals):
        if vals["is_stock_move_line_origin"]:
            if line.move_id.id not in vals["stock_move_ids"][0][2]:
                vals["product_uom_qty"] += sum(line.mapped("move_id.product_uom_qty"))
                vals["stock_move_ids"][0][2].append(line.move_id.id)
            vals["product_qty_reserved"] += line.quantity
            vals["line_ids"][0][2].append(line.id)
            # If multiple move lines diverge on lot/package/location, clear them to avoid
            # misleading detail on the aggregated todo card.
            if vals.get("lot_id") and vals["lot_id"] != line.lot_id.id:
                vals["lot_id"] = False
            if vals.get("package_id") and vals["package_id"] != line.package_id.id:
                vals["package_id"] = False
            if (
                vals.get("result_package_id")
                and vals["result_package_id"] != line.result_package_id.id
            ):
                vals["result_package_id"] = False
            if vals.get("location_id") and vals["location_id"] != line.location_id.id:
                vals["location_id"] = False
            if (
                vals.get("location_dest_id")
                and vals["location_dest_id"] != line.location_dest_id.id
            ):
                vals["location_dest_id"] = False
        else:
            vals["product_uom_qty"] += line.product_uom_qty
            vals["product_qty_reserved"] += (
                line.move_line_ids
                # TODO: Use reserved_qty or reserved_uom_qty
                and sum(line.move_line_ids.mapped("quantity"))
                or line.product_uom_qty
            )
            vals["line_ids"][0][2].extend(line.move_line_ids.ids)
            vals["stock_move_ids"][0][2].extend(line.ids)
        return vals

    @api.model
    def fill_records(self, lines_list):
        """
        :param lines_list: browse list
        :return:
        """
        self.forced_todo_key = str(
            self._group_key(self.todo_line_id or self.selected_pending_move_id)
        )
        self.todo_line_ids.unlink()
        self.todo_line_id = False
        # self.position_index = 0
        todo_vals = OrderedDict()
        position = 0
        move_qty_dic = defaultdict(float)
        is_stock_move_line_origin = lines_list[0]._name == "stock.move.line"
        for lines in lines_list:
            for line in lines:
                key = self._group_key(line)
                if key not in todo_vals:
                    todo_vals[key] = self._prepare_fill_record_values(line, position)
                    position += 1
                else:
                    todo_vals[key] = self._update_fill_record_values(
                        line, todo_vals[key]
                    )
                # Max between the reserved and picked..
                # Ups!! in 18.0 not reserved quantities on sml... so???
                if is_stock_move_line_origin:
                    move_qty_dic[line.move_id] += max(
                        sum(line.mapped("move_id.product_uom_qty")), line.qty_picked
                    )
                else:
                    move_qty_dic[line] += max(line.product_uom_qty, line.qty_picked)
        for move in self.get_moves():
            qty = move_qty_dic[move]
            if (
                move.barcode_backorder_action == "pending"
                and move.product_uom_qty > qty
            ):
                vals = self._prepare_fill_record_values(move, position)
                vals.update(
                    {
                        "product_uom_qty": move.product_uom_qty - qty,
                        "product_qty_reserved": 0.0,
                        "line_ids": False,
                        "is_extra_line": True,
                    }
                )
                todo_vals[
                    (
                        move,
                        "M",
                    )
                ] = vals
                position += 1
        self.todo_line_ids = self.env["wiz.stock.barcodes.read.todo"].create(
            list(todo_vals.values())
        )

    def action_open_picking(self):
        return self.picking_id.with_context(
            control_panel_hidden=False
        ).get_formview_action()

    def _get_picking_to_validate(self):
        """Inject context show_picking_type_action_tree to redirect to picking list
        after validate picking in barcodes environment.
        The stock_barcodes_validate_picking key allows to know when a picking has been
        validated from stock barcodes interface.
        """
        return self.picking_id.with_context(
            show_picking_type_action_tree=True, stock_barcodes_validate_picking=True
        )

    def action_validate_picking(self):
        picking = self._get_picking_to_validate()
        return picking.button_validate()
