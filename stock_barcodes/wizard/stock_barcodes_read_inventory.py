# Copyright 2023 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import logging
import traceback

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class WizStockBarcodesReadInventory(models.TransientModel):
    _name = "wiz.stock.barcodes.read.inventory"
    _inherit = "wiz.stock.barcodes.read"
    _description = "Wizard to read barcode on inventory"
    # Accept storable and consumable products during inventory counts
    _allowed_product_types = ["product", "consu"]

    def write(self, vals):
        """Log product/lot changes to detect unexpected resets between scans."""
        self.ensure_one()
        prev_pid = self.product_id.id
        prev_lot = self.lot_id.id
        res = super().write(vals)
        new_pid = self.product_id.id
        new_lot = self.lot_id.id
        if prev_pid != new_pid or prev_lot != new_lot:
            _logger.info(
                "[INV BARCODE] product/lot changed | prev_product=%s new_product=%s prev_lot=%s new_lot=%s vals_keys=%s",
                prev_pid,
                new_pid,
                prev_lot,
                new_lot,
                list(vals.keys()),
            )
        return res

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wiz, vals in zip(wizards, vals_list, strict=False):
            _logger.info(
                "[INV BARCODE] wizard created | wiz_id=%s vals_keys=%s stack=%s",
                wiz.id,
                list(vals.keys()),
                "".join(traceback.format_stack(limit=4)),
            )
        return wizards

    multiplier_factor = fields.Selection(
        selection=[("1", "x1"), ("5", "x5"), ("10", "x10"), ("50", "x50")],
        default="1",
        string="Multiplier",
    )
    instruction_text = fields.Char(compute="_compute_instruction_text")

    def _get_product_domain(self):
        return [("type", "in", self._allowed_product_types)]

    # Overwrite is needed to take into account new domain values
    product_id = fields.Many2one(domain=_get_product_domain)
    inventory_product_qty = fields.Float(
        string="Inventory quantities", digits="Product Unit of Measure", readonly=True
    )
    inventory_quant_ids = fields.Many2many(
        comodel_name="stock.quant", compute="_compute_inventory_quant_ids"
    )
    inventory_quant_ids_to_count = fields.Many2many(
        comodel_name="stock.quant", compute="_compute_inventory_quant_groups"
    )
    inventory_quant_ids_counted = fields.Many2many(
        comodel_name="stock.quant", compute="_compute_inventory_quant_groups"
    )
    count_inventory_quants = fields.Integer(
        compute="_compute_count_inventory_quants", store=True
    )
    display_read_quant = fields.Boolean(string="Read items", default=True)
    show_to_count = fields.Boolean(default=True)
    show_counted = fields.Boolean(default=True)

    def action_display_read_quant(self):
        self.display_read_quant = not self.display_read_quant

    def action_toggle_to_count(self):
        self.show_to_count = not self.show_to_count

    def action_toggle_counted(self):
        self.show_counted = not self.show_counted

    @api.depends("inventory_quant_ids")
    def _compute_count_inventory_quants(self):
        for wiz in self:
            wiz.count_inventory_quants = len(wiz.inventory_quant_ids)

    def action_cycle_multiplier(self):
        order = ["1", "5", "10", "50"]
        next_idx = (order.index(self.multiplier_factor) + 1) % len(order)
        self.multiplier_factor = order[next_idx]
        return True

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Force no preselected location; require an initial scan
        res.setdefault("location_id", False)
        return res

    @api.depends(
        "location_id", "product_id", "product_id.tracking", "lot_id", "lot_name"
    )
    def _compute_instruction_text(self):
        for wiz in self:
            location_label = wiz.location_id.display_name if wiz.location_id else False
            product_label = wiz.product_id.display_name if wiz.product_id else False
            lot_label = wiz.lot_id.display_name or wiz.lot_name

            if not wiz.location_id:
                wiz.instruction_text = _("Scan a location to start counting")
            elif not wiz.product_id:
                wiz.instruction_text = _(
                    "Location %(location)s: scan a product (lot/serial if required)",
                    location=location_label,
                )
            elif wiz.product_id.tracking in ("lot", "serial") and not (
                wiz.lot_id or wiz.lot_name
            ):
                wiz.instruction_text = _(
                    "Product %(product)s: scan lot/serial in %(location)s to start counting",
                    product=product_label,
                    location=location_label,
                )
            else:
                wiz.instruction_text = _(
                    "%(product)s%(lot)s in %(location)s: scan again to add or scan another product to switch",
                    product=product_label,
                    lot=f" (L/SN {lot_label})" if lot_label else "",
                    location=location_label,
                )

            wiz._log_debug_state(
                "inventory_instruction",
                {
                    "instruction_text": wiz.instruction_text,
                    "location": location_label,
                    "product": product_label,
                    "lot_label": lot_label,
                },
            )

    @api.depends("location_id", "owner_id", "show_owner")
    def _compute_inventory_quant_ids(self):
        Quant = self.env["stock.quant"]
        empty_quants = Quant
        for wiz in self:
            if not wiz.location_id:
                wiz.inventory_quant_ids = empty_quants
                wiz.send_bus_done(
                    "stock_barcodes_form_update",
                    {"type": "count_apply_inventory", "payload": {"count": 0}},
                )
                continue

            domain = [
                ("location_id", "=", wiz.location_id.id),
                "|",
                ("quantity", ">", 0),
                ("inventory_quantity_set", "=", True),
            ]
            _logger.info(
                "[INV BARCODE] compute quants | location=%s owner=%s domain=%s",
                wiz.location_id.id,
                wiz.owner_id.id if wiz.owner_id else None,
                domain,
            )
            quants = Quant.search(domain)
            if wiz.show_owner and wiz.owner_id:
                quants.with_context(allow_edit_owner=True).write(
                    {"owner_id": wiz.owner_id.id}
                )
            quants = quants.sorted(
                lambda q: (
                    q.location_id.complete_name or "",
                    q.product_id.display_name or "",
                    q.lot_id.name or "",
                    q.package_id.name or "",
                )
            )
            wiz.inventory_quant_ids = quants
            _logger.info(
                "[INV BARCODE] quants loaded | location=%s count=%s ids=%s",
                wiz.location_id.id,
                len(quants),
                quants.ids,
            )

            wiz.send_bus_done(
                "stock_barcodes_form_update",
                {
                    "type": "count_apply_inventory",
                    "payload": {"count": len(quants)},
                },
            )

    @api.depends("inventory_quant_ids", "inventory_quant_ids.inventory_quantity")
    def _compute_inventory_quant_groups(self):
        empty_quants = self.env["stock.quant"]
        for wiz in self:
            if not wiz.inventory_quant_ids:
                wiz.inventory_quant_ids_counted = empty_quants
                wiz.inventory_quant_ids_to_count = empty_quants
                continue

            counted = wiz.inventory_quant_ids.filtered(
                lambda q: (q.inventory_quantity or 0.0) > 0.0
            )
            wiz.inventory_quant_ids_counted = counted
            wiz.inventory_quant_ids_to_count = wiz.inventory_quant_ids - counted

    def process_barcode(self, barcode):
        _logger.info(
            "[INV BARCODE] process start | wiz_id=%s barcode=%s location=%s product=%s lot=%s qty=%s",
            self.id,
            barcode,
            self.location_id.id if self.location_id else None,
            self.product_id.id if self.product_id else None,
            self.lot_id.id if self.lot_id else None,
            self.product_qty,
        )
        self.barcode = self._clean_barcode_scanned(barcode)
        # Require location first; ignore location scans once a location is set
        if not self.location_id:
            if self.process_barcode_location_id():
                self._set_messagge_info(
                    "info", _("Location set. Scan products to count.")
                )
                self._compute_inventory_quant_ids()
                self._compute_instruction_text()
                return True
            self._set_messagge_info("info", _("Scan a location to start counting"))
            return False
        # else:
        #     # If already on a location, ignore location barcodes; fall through to product/lot handling
        #     if self.process_barcode_location_id():
        #         _logger.info(
        #             "[INV BARCODE] location barcode ignored because location already set"
        #         )
        #         self._set_messagge_info("info", _("Location already selected"))
        #         return True
        # # After location, fall back to standard flow (product-first)
        res = super().process_barcode(barcode)

        _logger.info(
            "[INV BARCODE] process end | wiz_id=%s res=%s product=%s lot=%s lot_name=%s qty=%s msg=%s msg_type=%s",
            self.id,
            res,
            self.product_id.id if self.product_id else None,
            self.lot_id.id if self.lot_id else None,
            self.lot_name,
            self.product_qty,
            self.message,
            self.message_type,
        )
        return res

    @api.onchange("_barcode_scanned")
    def _on_barcode_scanned_inventory(self):
        """Mirror picking onchange: clear field, log, avoid double processing."""
        if not self._barcode_scanned:
            return
        _logger.info(
            "[INV BARCODE] onchange _barcode_scanned fired | barcode=%s | ctx=%s",
            self._barcode_scanned,
            dict(self.env.context or {}),
        )
        self._barcode_scanned = ""

    def on_barcode_scanned(self, barcode):
        # Emulate picking-level guards while keeping inventory flow intact
        if self.env.context.get("onchange"):
            _logger.info(
                "[INV BARCODE] skipping scan during onchange | barcode=%s | ctx=%s",
                barcode,
                dict(self.env.context or {}),
            )
            return self._prepare_onchange_result()
        if self.env.context.get("barcode_processing_reentry"):
            _logger.warning(
                "[INV BARCODE] reentry suppressed in on_barcode_scanned | barcode=%s",
                barcode,
            )
            return self._prepare_onchange_result()
        if not self.env.context.get("barcode_processing"):
            _logger.info(
                "[INV BARCODE] skipping scan without barcode_processing flag | barcode=%s | ctx=%s",
                barcode,
                dict(self.env.context or {}),
            )
            return self._prepare_onchange_result()

        cleaned = self._clean_barcode_scanned(barcode)
        if self._is_recent_duplicate_scan(cleaned, threshold_ms=1200):
            _logger.info(
                "[INV BARCODE] duplicate scan suppressed | barcode=%s", cleaned
            )
            return self._prepare_onchange_result()

        _logger.info(
            "[INV BARCODE] on_barcode_scanned entry | wiz_id=%s barcode=%s product_before=%s lot_before=%s ctx=%s | stack=%s",
            self.id,
            cleaned,
            self.product_id.id if self.product_id else None,
            self.lot_id.id if self.lot_id else None,
            dict(self.env.context or {}),
            "".join(traceback.format_stack(limit=6)),
        )

        # Prevent nested reentry during super().on_barcode_scanned calls
        self = self.with_context(barcode_processing_reentry=True)

        super().on_barcode_scanned(cleaned)
        self.last_scan_barcode = cleaned
        self.last_scan_at = fields.Datetime.now()
        # Persist the wizard state so subsequent onchange calls reload product/lot
        # context even if the JS payload omits them (we see this in inventory flows
        # where barcode_processing flag is missing and the client does not echo
        # current field values back).
        self.write(self._convert_to_write(self._cache))
        self._compute_instruction_text()
        self._log_debug_state("inventory_on_barcode_scanned")
        _logger.info(
            "[INV BARCODE] on_barcode_scanned exit | wiz_id=%s product_after=%s lot_after=%s qty=%s msg=%s msg_type=%s",
            self.id,
            self.product_id.id if self.product_id else None,
            self.lot_id.id if self.lot_id else None,
            self.product_qty,
            self.message,
            self.message_type,
        )
        return self._prepare_onchange_result()

    def action_confirm(self):
        _logger.info(
            "[INV BARCODE] action_confirm | product=%s lot=%s qty=%s tracking=%s",
            self.product_id.id if self.product_id else None,
            self.lot_id.id if self.lot_id else None,
            self.product_qty,
            self.product_id.tracking if self.product_id else None,
        )
        return super().action_confirm()

    def _prepare_stock_quant_values(self):
        return {
            "product_id": self.product_id.id,
            "location_id": self.location_id.id,
            "inventory_quantity": self.product_qty,
            "lot_id": self.lot_id.id,
            "package_id": self.package_id.id,
        }

    def _inventory_quant_domain(self, product, lot=None):
        domain = [
            ("location_id", "=", self.location_id.id),
            ("product_id", "=", product.id),
            "|",
            ("quantity", ">", 0.0),
            ("inventory_quantity_set", "=", True),
        ]
        if lot:
            domain.append(("lot_id", "=", lot.id))
        if self.package_id:
            domain.append(("package_id", "=", self.package_id.id))
        if self.owner_id:
            domain.append(("owner_id", "=", self.owner_id.id))
        return domain

    def _add_inventory_quant(self):
        StockQuant = self.env["stock.quant"]
        product = self.product_id
        lot = self.lot_id
        quant_domain = self._inventory_quant_domain(product, lot)
        _logger.info("[INV BARCODE] find quant | domain=%s", quant_domain)
        quant = StockQuant.search(quant_domain, limit=1).with_context(
            inventory_mode=True
        )
        if not quant:
            _logger.info("[INV BARCODE] quant miss, creating inventory line")
            quant = StockQuant.with_context(inventory_mode=True).create(
                {
                    "product_id": product.id,
                    "location_id": self.location_id.id,
                    "lot_id": lot.id if lot else False,
                    "package_id": self.package_id.id if self.package_id else False,
                    "owner_id": self.owner_id.id if self.owner_id else False,
                    "inventory_quantity": 0.0,
                    "inventory_quantity_set": True,
                }
            )

        _logger.info(
            "[INV BARCODE] quant hit | quant_id=%s inventory_qty=%s product=%s lot=%s pkg=%s loc=%s",
            quant.id,
            quant.inventory_quantity,
            quant.product_id.id,
            quant.lot_id.id,
            quant.package_id.id,
            quant.location_id.id,
        )

        # Derive the increment for this scan. Apply multiplier for non-serial products;
        # serials are always counted as single units.
        multiplier = 1.0
        try:
            multiplier = float(self.multiplier_factor or 1.0)
        except Exception:
            multiplier = 1.0

        if product.tracking == "serial":
            scan_qty = 1.0
        elif product.tracking == "lot":
            scan_qty = multiplier
        else:
            scan_qty = (self.product_qty or 1.0) * multiplier

        if product.tracking == "serial" and (
            quant.inventory_quantity > 0.0 or scan_qty != 1.0
        ):
            self._serial_tracking_message_fail()
            return False

        prev_inv_qty = quant.inventory_quantity
        accumulate = True  # Inventory should always add per scan
        if accumulate:
            quant.inventory_quantity += scan_qty
        else:
            quant.inventory_quantity = scan_qty

        _logger.info(
            "[INV BARCODE] quant updated | quant_id=%s prev_inv_qty=%s new_inv_qty=%s scan_qty=%s accumulate=%s tracking=%s",
            quant.id,
            prev_inv_qty,
            quant.inventory_quantity,
            scan_qty,
            accumulate,
            product.tracking,
        )

        self.inventory_product_qty = quant.quantity
        return True

    def _serial_tracking_message_fail(self):
        self._set_messagge_info(
            "more_match",
            _("Inventory line with more than one unit in serial tracked product"),
        )

    def action_done(self):
        _logger.info(
            "[INV BARCODE] action_done start | product=%s lot=%s lot_name=%s qty=%s tracking=%s",
            self.product_id.id if self.product_id else None,
            self.lot_id.id if self.lot_id else None,
            self.lot_name,
            self.product_qty,
            self.product_id.tracking if self.product_id else None,
        )
        result = super().action_done()
        _logger.info("[INV BARCODE] action_done after super | result=%s", result)
        if result:
            result = self._add_inventory_quant()
            _logger.info(
                "[INV BARCODE] action_done after add_quant | result=%s", result
            )
        return result

    def action_manual_entry(self):
        # Prep UI to start a new line: expect a product scan (and lot/serial if required)
        self.product_id = False
        self.lot_id = False
        self.lot_name = False
        self.product_qty = 0.0
        self.packaging_qty = 0.0
        self.inventory_product_qty = 0.0
        self.last_product_id = False
        self.last_lot_identifier = False
        self.manual_entry = False
        # Refresh guidance and keep current location context
        self._compute_instruction_text()
        prompt = (
            _("Scan a product (lot/serial if required) to add a new inventory line")
            if self.location_id
            else _("Scan location to start counting")
        )
        self.instruction_text = prompt
        self._set_messagge_info("info", prompt)
        # Ensure manual overlay is hidden
        self.send_bus_done(
            "stock_barcodes_scan",
            {
                "type": "stock_barcodes_edit_manual",
                "payload": {
                    "manual_entry": False,
                },
            },
        )
        return True

    def action_change_location_filter(self):
        """Reset to location-first state and clear current scan context."""
        clear_location = bool(self.env.context.get("clear_location"))
        # Clear scan context
        self.product_id = False
        self.lot_id = False
        self.lot_name = False
        self.product_qty = 0.0
        self.packaging_qty = 0.0
        self.inventory_product_qty = 0.0
        self.package_id = False
        self.last_product_id = False
        self.last_lot_identifier = False
        self.manual_entry = False
        if clear_location:
            self.location_id = False
            self.inventory_quant_ids = self.env["stock.quant"]
        # Hide Form Edit
        self.send_bus_done(
            "stock_barcodes_scan",
            {
                "type": "stock_barcodes_edit_manual",
                "payload": {
                    "manual_entry": False,
                },
            },
        )
        self._compute_instruction_text()
        self._compute_inventory_quant_ids()
        if clear_location:
            self._set_messagge_info("info", _("Scan location to start counting"))
        return True

    # Backward compatibility shim
    def action_clean_values(self):
        return self.action_change_location_filter()

    def action_clear_context(self):
        """Reset product/lot so user can keep counting in the same location."""
        self.product_id = False
        self.lot_id = False
        self.lot_name = False
        self.product_qty = 0.0
        self.packaging_qty = 0.0
        self.last_product_id = False
        self.last_lot_identifier = False
        self.manual_entry = False
        self._compute_instruction_text()
        return True

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id != self.lot_id.product_id:
            self.lot_id = False

    @api.onchange("lot_id")
    def _onchange_lot_id(self):
        if self.lot_id and not self.env.context.get("keep_auto_lot"):
            self.auto_lot = False

    def apply_inventory(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock.action_stock_inventory_adjustement_name"
        )
        action["context"] = {"default_quant_ids": self.inventory_quant_ids.ids}
        return action
