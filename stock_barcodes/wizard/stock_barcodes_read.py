# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

TYPE_ERROR = ["more_match", "not_found"]


class WizStockBarcodesRead(models.AbstractModel):
    _name = "wiz.stock.barcodes.read"
    _inherit = "barcodes.barcode_events_mixin"
    _description = "Wizard to read barcode"
    # To prevent remove the record wizard until 2 days old
    _transient_max_hours = 48
    _allowed_product_types = ["product", "consu"]
    _rec_name = "barcode"

    def _get_product_domain(self):
        return [("type", "in", self._allowed_product_types)]

    _barcode_scanned = fields.Char()
    barcode = fields.Char()
    res_model_id = fields.Many2one(comodel_name="ir.model", index=True)
    res_id = fields.Integer(index=True)
    product_id = fields.Many2one(
        comodel_name="product.product", domain=_get_product_domain
    )
    product_uom_id = fields.Many2one(comodel_name="uom.uom")
    product_tracking = fields.Selection(related="product_id.tracking", readonly=True)
    lot_id = fields.Many2one(comodel_name="stock.lot")
    lot_name = fields.Char(
        "Lot/Serial Number Name",
        compute="_compute_lot_name",
        readonly=False,
        store=True,
    )
    # Track last processed scan to suppress duplicate immediate calls (onchange + dummy)
    last_scan_barcode = fields.Char(store=True)
    last_scan_at = fields.Datetime(store=True)
    location_id = fields.Many2one(comodel_name="stock.location")
    location_dest_id = fields.Many2one(
        comodel_name="stock.location", string="Location dest."
    )
    packaging_id = fields.Many2one(comodel_name="product.packaging")
    product_packaging_ids = fields.One2many(related="product_id.packaging_ids")
    package_id = fields.Many2one(comodel_name="stock.quant.package")
    result_package_id = fields.Many2one(comodel_name="stock.quant.package")
    owner_id = fields.Many2one(comodel_name="res.partner")
    packaging_qty = fields.Float(string="Package Qty", digits="Product Unit of Measure")
    product_qty = fields.Float(digits="Product Unit of Measure")
    manual_entry = fields.Boolean(string="Manual", help="Entry manual data")
    confirmed_moves = fields.Boolean(
        string="Confirmed moves", related="option_group_id.confirmed_moves"
    )
    message_type = fields.Selection(
        [
            ("info", "Barcode read with additional info"),
            ("info_page", "Info page"),
            ("not_found", "No barcode found"),
            ("more_match", "More than one matches found"),
            ("success", "Barcode read correctly"),
        ],
        readonly=True,
    )
    message = fields.Char(readonly=True)
    message_step = fields.Char(readonly=True)
    guided_product_id = fields.Many2one(comodel_name="product.product")
    guided_location_id = fields.Many2one(comodel_name="stock.location")
    guided_location_dest_id = fields.Many2one(comodel_name="stock.location")
    guided_lot_id = fields.Many2one(comodel_name="stock.lot")
    action_ids = fields.Many2many(
        comodel_name="stock.barcodes.action", compute="_compute_action_ids"
    )
    option_group_id = fields.Many2one(comodel_name="stock.barcodes.option.group")
    visible_force_done = fields.Boolean()
    step = fields.Integer()
    is_manual_qty = fields.Boolean(compute="_compute_is_manual_qty")
    is_manual_confirm = fields.Boolean(compute="_compute_is_manual_qty")
    # Technical field to allow use in attrs
    display_menu = fields.Boolean()
    auto_lot = fields.Boolean(
        string="Get lots automatically",
        help="If checked the lot will be set automatically with the same "
        "removal startegy",
        compute="_compute_auto_lot",
        store=True,
        readonly=False,
    )
    create_lot = fields.Boolean(
        string="Allow create lot",
        help="Show lot name field",
        compute="_compute_create_lot",
    )
    display_assign_serial = fields.Boolean(compute="_compute_display_assign_serial")
    keep_result_package = fields.Boolean()
    total_product_uom_qty = fields.Float(
        string="Product Demand", digits="Product Unit of Measure", store=False
    )
    total_product_qty_done = fields.Float(
        string="Product Qty. Done", digits="Product Unit of Measure", store=False
    )

    enable_add_product = fields.Boolean(default=True)
    show_form_scan = fields.Boolean(compute="_compute_show_form_scan")
    product_in_stock = fields.Float(compute="_compute_product_in_stock")
    show_stock = fields.Boolean(related="option_group_id.show_stock")
    show_owner = fields.Boolean(related="option_group_id.show_owner")
    # Track last scanned combination to auto-increment quantities per lot/serial
    last_product_id = fields.Many2one(comodel_name="product.product")
    last_lot_identifier = fields.Char()

    def _compute_show_form_scan(self):
        for barcode in self:
            barcode.show_form_scan = barcode.option_group_id.show_form_scan

    @api.depends("product_id", "owner_id", "package_id")
    def _compute_product_in_stock(self):
        StockQuant = self.env["stock.quant"]
        for rec in self:
            rec.product_in_stock = StockQuant._get_available_quantity(
                product_id=rec.product_id,
                location_id=rec.location_id,
                package_id=rec.package_id,
                owner_id=rec.owner_id,
                allow_negative=True,
            )

    @api.depends("res_id")
    def _compute_action_ids(self):
        actions = self.env["stock.barcodes.action"].search(
            [("action_window_id", "!=", False)]
        )
        self.action_ids = actions

    @api.depends("option_group_id")
    def _compute_is_manual_qty(self):
        for rec in self:
            rec.is_manual_qty = rec.option_group_id.is_manual_qty
            rec.is_manual_confirm = rec.option_group_id.is_manual_confirm
            rec.auto_lot = rec.option_group_id.auto_lot

    @api.depends("option_group_id")
    def _compute_auto_lot(self):
        for rec in self:
            rec.auto_lot = rec.option_group_id.auto_lot

    @api.depends("option_group_id")
    def _compute_create_lot(self):
        for rec in self:
            rec.create_lot = rec.option_group_id.create_lot

    @api.depends("product_id")
    def _compute_display_assign_serial(self):
        for rec in self:
            rec.display_assign_serial = rec.product_id.tracking == "serial"

    @api.depends("lot_id")
    def _compute_lot_name(self):
        for rec in self:
            rec.lot_name = rec.lot_id.name

    @api.onchange("packaging_qty")
    def onchange_packaging_qty(self):
        if self.packaging_id:
            self.product_qty = self.packaging_qty * self.packaging_id.qty

    @api.onchange(
        "product_id",
        "lot_id",
        "package_id",
        "result_package_id",
        "packaging_qty",
        "product_qty",
    )
    def onchange_visible_force_done(self):
        self.visible_force_done = False

    def _set_messagge_info(self, message_type, message):
        """
        Set message type and message description.
        For manual entry mode barcode is not set so is not displayed
        """
        self.message_type = message_type
        # if self.barcode and self.message_type in ["more_match", "not_found"]:
        if self.barcode:
            self.message = _(
                "%(barcode)s (%(message)s)", barcode=self.barcode, message=message
            )
        else:
            if message_type in TYPE_ERROR:
                self.manual_entry = True
                self.send_bus_done(
                    "stock_barcodes_scan",
                    {
                        "type": "actions_barcode_notification",
                        "payload": {
                            "message": message,
                            "sticky": True,
                            "message_type": "danger"
                            if message_type in TYPE_ERROR
                            else message_type,
                        },
                    },
                )
            elif message_type != "info_page":
                self.send_bus_done(
                    "stock_barcodes_scan",
                    {
                        "type": "actions_barcode_notification",
                        "payload": {
                            "message": message,
                            "message_type": message_type,
                        },
                    },
                )
            else:
                self.message = f"{message}"

    def process_barcode_location_id(self):
        location = self.env["stock.location"].search(self._barcode_domain(self.barcode))
        if location:
            self.location_id = location
            return True
        return False

    def process_barcode_location_dest_id(self):
        location = self.env["stock.location"].search(self._barcode_domain(self.barcode))
        if location:
            self.location_dest_id = location
            return True
        return False

    def process_barcode_product_id(self):
        domain = self._barcode_domain(self.barcode)
        product = self.env["product.product"].search(domain)
        if product:
            if len(product) > 1:
                self._set_messagge_info("more_match", _("More than one product found"))
                return False
            elif product.type not in self._allowed_product_types:
                _logger.info(
                    "[BARCODE UI] product rejected by type | barcode=%s product=%s type=%s allowed=%s",
                    self.barcode,
                    product.display_name,
                    product.type,
                    self._allowed_product_types,
                )
                self._set_messagge_info(
                    "not_found", _("The product type is not allowed")
                )
                return False
            _logger.info(
                "[BARCODE UI] product hit | barcode=%s product=%s tracking=%s",
                self.barcode,
                product.display_name,
                product.tracking,
            )
            self.action_product_scaned_post(product)
            if (
                self.option_group_id.fill_fields_from_lot
                and self.location_id
                and self.product_id
            ):
                quant_domain = [
                    ("location_id", "=", self.location_id.id),
                    ("product_id", "=", product.id),
                ]
                if self.lot_id:
                    quant_domain.append(("lot_id", "=", self.lot_id.id))
                if self.package_id:
                    quant_domain.append(("package_id", "=", self.package_id.id))
                if self.owner_id:
                    quant_domain.append(("owner_id", "=", self.owner_id.id))
                quants = self.env["stock.quant"].search(quant_domain)
                if quants:
                    self.set_info_from_quants(quants)
            return True
        return False

    def process_barcode_lot_id(self):
        if self.env.user.has_group("stock.group_production_lot"):
            # Accept both lot name and lot reference so scanners can use either
            lot_domain = ["|", ("name", "=", self.barcode), ("ref", "=", self.barcode)]
            if self.product_id:
                lot_domain.append(("product_id", "=", self.product_id.id))
            lot = self.env["stock.lot"].search(lot_domain)
            if len(lot) == 1:
                _logger.info(
                    "[BARCODE UI] lot hit | barcode=%s lot=%s product=%s tracking=%s",
                    self.barcode,
                    lot.display_name,
                    lot.product_id.display_name,
                    lot.product_id.tracking,
                )
                # Always bind the scanned lot/product immediately to keep UI and logic in sync
                self.product_id = lot.product_id
                self.lot_id = lot
                self.lot_name = lot.name
                if self.option_group_id.fill_fields_from_lot:
                    quant_domain = [
                        ("lot_id.name", "=", self.barcode),
                        ("product_id", "=", lot.product_id.id),
                        ("quantity", ">", 0.0),
                    ]
                    if self.location_id:
                        quant_domain.append(("location_id", "=", self.location_id.id))
                    else:
                        quant_domain.append(("location_id.usage", "=", "internal"))
                    if self.owner_id:
                        quant_domain.append(("owner_id", "=", self.owner_id.id))
                    quants = self.env["stock.quant"].search(quant_domain)
                    if (
                        not self._name == "wiz.stock.barcodes.read.inventory"
                        and not quants
                        and not self.option_group_id.allow_negative_quant
                    ):
                        self._set_messagge_info(
                            "more_match",
                            _("No stock available for this lot with screen values"),
                        )
                        self.lot_id = False
                        self.lot_name = False
                        return False
                    if quants:
                        self.set_info_from_quants(quants)
                    else:
                        self.action_lot_scaned_post(lot)
                    return True
                else:
                    self.action_lot_scaned_post(lot)
                return True
            elif lot:
                self._set_messagge_info(
                    "more_match", _("More than one lot found\nScan product before")
                )
            elif (
                self.product_id
                and self.product_id.tracking != "none"
                and self.option_group_id.create_lot
            ):
                self.lot_name = self.barcode
                self.action_lot_scaned_post(self.lot_name)
                return True
        return False

    def process_barcode_package_id(self):
        if not self.env.user.has_group("stock.group_tracking_lot"):
            return False
        quant_domain = [
            ("package_id.name", "=", self.barcode),
            ("quantity", ">", 0.0),
        ]
        if self.option_group_id.get_option_value("location_id", "forced"):
            quant_domain.append(("location_id", "=", self.location_id.id))
        if self.owner_id:
            quant_domain.append(("owner_id", "=", self.owner_id.id))
        quants = self.env["stock.quant"].search(quant_domain)
        internal_quants = quants.filtered(lambda q: q.location_id.usage == "internal")
        if internal_quants:
            quants = internal_quants
        elif quants:
            self = self.with_context(ignore_quant_location=True)
            # self._set_messagge_info("more_match",
            # _("Package located external location"))
        else:
            # self._set_messagge_info("more_match", _("Package not fount or empty"))
            return False
        self.set_info_from_quants(quants)
        return True

    def process_barcode_result_package_id(self):
        if not self.env.user.has_group("stock.group_tracking_lot"):
            return False
        domain = [("name", "=", self.barcode)]
        package = self.env["stock.quant.package"].search(domain)
        if package:
            self.result_package_id = package[:1]
            return True
        return False

    def set_info_from_quants(self, quants):
        """
        Fill wizard fields from stock quants
        """
        if self.env.context.get("skip_set_info_from_quants"):
            return
        ignore_quant_location = self.env.context.get(
            "ignore_quant_location", self.option_group_id.ignore_quant_location
        )
        if len(quants) == 1:
            # All ok
            self.action_product_scaned_post(quants.product_id)
            self.package_id = quants.package_id
            self.result_package_id = quants.package_id
            if quants.lot_id:
                self.action_lot_scaned_post(quants.lot_id)
            if quants.owner_id:
                self.owner_id = quants.owner_id
            # Review conditions
            if (
                not ignore_quant_location
                and not self.option_group_id.get_option_value("location_id", "forced")
                and self.option_group_id.code != "IN"
            ):
                self.location_id = quants.location_id
            if self.option_group_id.code != "OUT" and not self.env.context.get(
                "skip_update_quantity_from_lot", False
            ):
                # For tracked products, always start with qty=1 per scan to avoid grouping different lots
                if self.product_id.tracking in ("lot", "serial"):
                    self.product_qty = 1.0
                else:
                    self.product_qty = quants.quantity
        elif len(quants) > 1:
            # More than one record found with same barcode.
            # Could be half lot in two distinct locations.
            # Empty location field to force a location barcode scan
            products = quants.mapped("product_id")
            if len(products) == 1:
                self.action_product_scaned_post(products[0])
            package = quants[0].package_id
            if not quants.filtered(lambda q: q.package_id != package):
                self.package_id = package
            lots = quants.mapped("lot_id")
            if len(lots) == 1:
                self.action_lot_scaned_post(lots[0])
            owner = quants[0].owner_id
            if not quants.filtered(lambda q: q.owner_id != owner):
                self.owner_id = owner
            if not ignore_quant_location:
                locations = quants.mapped("location_id")
                if len(locations) == 1:
                    if not self.location_id and self.option_group_id.code != "IN":
                        self.location_id = locations

    def process_barcode_packaging_id(self):
        domain = self._barcode_domain(self.barcode)
        if self.env.user.has_group("product.group_stock_packaging"):
            domain.append(("product_id", "!=", False))
            packaging = self.env["product.packaging"].search(domain)
            if packaging:
                if len(packaging) > 1:
                    self._set_messagge_info(
                        "more_match", _("More than one package found")
                    )
                    self.packaging_id = False
                    return False
                self.action_packaging_scaned_post(packaging)
                return True
        return False

    def process_barcode(self, barcode):
        """Product-first flow with context memory and simple lot/serial handling."""
        self.barcode = self._clean_barcode_scanned(barcode)
        self._log_debug_state("process_barcode_start")
        if not self.barcode:
            return False

        # 1) Try product first
        if self.process_barcode_product_id():
            # Product context set; auto-confirm for untracked, prompt lot/serial otherwise
            if self.product_tracking in ("none", False):
                self._log_debug_state("process_barcode_product_no_tracking")
                self.set_product_qty()
                res = self.action_confirm()
                if res:
                    self.last_scan_barcode = self.barcode
                    self.last_scan_at = fields.Datetime.now()
                return res
            self._log_debug_state("process_barcode_product_tracking")
            self._set_messagge_info("info", _("Scan lot/serial"))
            return True

        # 2) If no product context, any non-product barcode is invalid -> ask for product
        if not self.product_id:
            self._set_messagge_info("info", _("Scan product"))
            return False

        # 3) We have product context
        tracking = self.product_tracking
        if tracking in ("lot", "serial"):
            if self.process_barcode_lot_id():
                self._log_debug_state("process_barcode_lot")
                res = self.action_confirm()
                if res:
                    self.last_scan_barcode = self.barcode
                    self.last_scan_at = fields.Datetime.now()
                return res
            self._set_messagge_info(
                "not_found", _("Invalid lot/serial for this product")
            )
            self.play_sounds(False)
            return False

        # 4) Untracked product context: only product scans are valid
        self._set_messagge_info("info", _("Scan product"))
        self.play_sounds(False)
        self._log_debug_state("process_barcode_not_found")
        return False

    def check_option_required(self):
        options = self.option_group_id.option_ids
        options_required = options.filtered("required")
        for option in options_required:
            if not getattr(self, option.field_name, False):
                if self.is_manual_qty and option.field_name in [
                    "product_qty",
                    "packaging_qty",
                ]:
                    self._set_focus_on_qty_input("product_qty")
                if option.field_name == "lot_id" and (
                    self.product_id.tracking == "none"
                    or self.auto_lot
                    or (self.lot_name and self.create_lot)
                ):
                    continue
                if self._option_required_hook(option):
                    continue
                self.display_notification(
                    _("{name} is required").format(name=option.name),
                    message_type="danger",
                    title=_("Empty field"),
                    sticky=False,
                )
                self.action_show_step()
                return False
        return True

    def _option_required_hook(self, option_required):
        """Hook to evaluate is an option is required"""
        return False

    def _scanned_location(self, barcode):
        location = self.env["stock.location"].search(self._barcode_domain(barcode))
        if location:
            self.location_id = location
            self._set_messagge_info("info", _("Waiting product"))
            return True
        else:
            return False

    def _barcode_domain(self, barcode):
        field_name = self.env.context.get("barcode_domain_field", "barcode")
        return [(field_name, "=", barcode)]

    def _clean_barcode_scanned(self, barcode):
        return barcode.rstrip()

    def _log_debug_state(self, label, extra=None):
        """Emit detailed scan state to help diagnose UI refresh issues."""
        payload = {
            "label": label,
            "barcode": self.barcode,
            "product_id": self.product_id.id if self.product_id else False,
            "product": self.product_id.display_name if self.product_id else False,
            "tracking": self.product_id.tracking
            if self.product_id
            else self.product_tracking,
            "lot_id": self.lot_id.id if self.lot_id else False,
            "lot_name": self.lot_name,
            "instruction_text": getattr(self, "instruction_text", False),
            "instruction_override": getattr(self, "instruction_override", False),
            "qty": self.product_qty,
            "packaging_qty": self.packaging_qty,
            "location_id": self.location_id.id if self.location_id else False,
            "location_dest_id": self.location_dest_id.id
            if self.location_dest_id
            else False,
            "manual_entry": self.manual_entry,
        }
        if extra:
            payload.update(extra)
        _logger.debug("[BARCODE UI][DEBUG] %s | %s", label, payload)

    def _is_recent_duplicate_scan(self, barcode, threshold_ms=600):
        """Return True when the same barcode was just processed moments ago."""
        if not barcode:
            return False
        if barcode != self.last_scan_barcode:
            return False
        if not self.last_scan_at:
            return False
        delta = fields.Datetime.now() - self.last_scan_at
        return delta <= timedelta(milliseconds=threshold_ms)

    def on_barcode_scanned(self, barcode):
        self.barcode = self._clean_barcode_scanned(barcode)
        if self._is_recent_duplicate_scan(self.barcode):
            _logger.info(
                "[BARCODE UI] duplicate scan suppressed (onchange) | barcode=%s",
                self.barcode,
            )
            return self._prepare_onchange_result()
        _logger.info("[BARCODE UI] on_barcode_scanned | barcode=%s", self.barcode)
        self._log_debug_state("before_process")
        # Process immediately so the UI reacts to scans dispatched by barcode_handler
        self.process_barcode(self.barcode)
        self._barcode_scanned = False
        self._log_debug_state("after_process")
        return self._prepare_onchange_result()

    def dummy_on_barcode_scanned(self, barcode=None):
        """To avoid execute operations in onchange environment"""
        cleaned_barcode = (
            self._clean_barcode_scanned(barcode) if barcode else self.barcode
        )
        if self._is_recent_duplicate_scan(cleaned_barcode):
            _logger.info(
                "[BARCODE UI] duplicate scan suppressed (dummy) | barcode=%s",
                cleaned_barcode,
            )
            return self._prepare_onchange_result()
        if cleaned_barcode:
            self.barcode = cleaned_barcode
        _logger.info("[BARCODE UI] dummy_on_barcode_scanned | barcode=%s", self.barcode)
        self._log_debug_state("dummy_before_process")
        self.process_barcode(self.barcode)
        self._barcode_scanned = False
        self._log_debug_state("dummy_after_process")
        return self._prepare_onchange_result()

    def _prepare_onchange_result(self):
        """Return onchange-like payload so the form updates after scans."""
        self.ensure_one()
        values = self.read()[0]
        values.pop("__last_update", None)
        self._log_debug_state("onchange_payload", {"payload_keys": list(values.keys())})
        return {"value": values}

    def check_location_contidion(self):
        if not self.location_id:
            self._set_messagge_info("info", _("Waiting location"))
            # Remove product when no location has been scanned
            _logger.info(
                "[BARCODE UI] clearing product due to missing location | product_id=%s",
                self.product_id.id if self.product_id else None,
            )
            self.product_id = False
            return False
        return True

    def check_lot_contidion(self):
        if self.product_id.tracking != "none" and not self.lot_id and not self.lot_name:
            self._set_messagge_info("info", _("Waiting lot"))
            return False
        return True

    def check_done_conditions(self):
        result_ok = self.check_location_contidion()
        if not result_ok:
            return False
        if not self.product_id:
            self._set_messagge_info("info", _("Waiting product"))
            return False
        result_ok = self.check_lot_contidion()
        if not result_ok:
            return False
        if (
            not self.product_qty
            and not self._name == "wiz.stock.barcodes.read.inventory"
        ):
            self._set_messagge_info("info", _("Waiting quantities"))
            return False
        if (
            self.option_group_id.barcode_guided_mode == "guided"
            and not self._check_guided_values()
        ):
            return False
        if self.manual_entry:
            self._set_messagge_info("success", _("Manual entry OK"))
        return True

    def _check_guided_values(self):
        if (
            self.product_id != self.guided_product_id
            and self.option_group_id.get_option_value("product_id", "forced")
        ):
            self._set_messagge_info("more_match", _("Wrong product"))
            self.product_qty = 0.0
            return False
        if (
            self.guided_product_id.tracking != "none"
            and self.lot_id != self.guided_lot_id
            and self.option_group_id.get_option_value("lot_id", "forced")
        ):
            self._set_messagge_info("more_match", _("Wrong lot"))
            return False
        if (
            self.location_id != self.guided_location_id
            and self.option_group_id.get_option_value("location_id", "forced")
        ):
            self._set_messagge_info("more_match", _("Wrong location"))
            return False
        if (
            self.location_dest_id != self.guided_location_dest_id
            and self.option_group_id.get_option_value("location_dest_id", "forced")
        ):
            self._set_messagge_info("more_match", _("Wrong location dest"))
            return False
        return True

    def action_done(self):
        if not self.product_id:
            self._set_messagge_info("info", _("Scan product"))
            return False
        if self.product_tracking not in ("none", False) and not (
            self.lot_id or self.lot_name
        ):
            self._set_messagge_info("info", _("Scan lot/serial"))
            return False
        if not self.product_qty:
            self.product_qty = 1.0
        self.process_lot_before_done()
        return True

    def action_cancel(self):
        return True

    def action_product_scaned_post(self, product):
        self.package_id = False
        if self.product_id != product and self.lot_id.product_id != product:
            self.lot_id = False
        self.product_id = product
        self.product_uom_id = self.product_id.uom_id
        _logger.info(
            "[BARCODE UI] action_product_scaned_post | product_id=%s",
            self.product_id.id if self.product_id else None,
        )
        self.set_product_qty()

    def action_packaging_scaned_post(self, packaging):
        self.packaging_id = packaging
        if (
            self.product_id != packaging.product_id
            and self.lot_id.product_id != packaging.product_id
        ):
            self.lot_id = False
        self.product_id = packaging.product_id
        self.set_product_qty()

    def action_lot_scaned_post(self, lot):
        if isinstance(lot, str):
            self.lot_name = lot
        else:
            self.lot_id = lot
        self.set_product_qty()

    def set_product_qty(self):
        prev_qty = self.product_qty
        if (
            self.manual_entry
            or self.is_manual_qty
            or self.option_group_id.get_option_value("product_qty", "filled_default")
        ):
            return
        elif self.packaging_id:
            self.packaging_qty = 1.0
            self.product_qty = self.packaging_id.qty * self.packaging_qty
            self.last_product_id = self.product_id
            self.last_lot_identifier = False
        else:
            self.packaging_qty = 0.0
            current_lot_identifier = self.lot_id.id or self.lot_name
            if (
                self.product_id
                and self.product_id.tracking in ("lot", "serial")
                and current_lot_identifier
            ):
                same_product = self.last_product_id == self.product_id
                same_lot = self.last_lot_identifier == str(current_lot_identifier)
                if same_product and same_lot:
                    self.product_qty = (self.product_qty or 0.0) + 1.0
                else:
                    self.product_qty = 1.0
                self.last_product_id = self.product_id
                self.last_lot_identifier = str(current_lot_identifier)
            else:
                self.product_qty = 1.0
                self.last_product_id = self.product_id
                self.last_lot_identifier = False
        _logger.info(
            "[BARCODE UI] set_product_qty | product=%s tracking=%s lot_id=%s lot_name=%s prev_qty=%s new_qty=%s last_product_id=%s last_lot=%s manual=%s packaging=%s",
            self.product_id.display_name if self.product_id else None,
            self.product_id.tracking if self.product_id else None,
            self.lot_id.id if self.lot_id else None,
            self.lot_name,
            prev_qty,
            self.product_qty,
            self.last_product_id.id if self.last_product_id else None,
            self.last_lot_identifier,
            self.manual_entry,
            self.packaging_id.id if self.packaging_id else None,
        )

    def action_clean_lot(self):
        self.lot_id = False
        self.lot_name = False
        self.last_lot_identifier = False
        self.action_show_step()

    def action_clean_product(self):
        _logger.info(
            "[BARCODE UI] action_clean_product | product_id=%s",
            self.product_id.id if self.product_id else None,
        )
        self.product_id = False
        self.last_product_id = False
        self.last_lot_identifier = False
        self.action_show_step()

    def action_clean_package(self):
        self.package_id = False
        self.result_package_id = False
        self.action_show_step()

    def action_create_package(self):
        self.result_package_id = self.env["stock.quant.package"].create({})

    def action_change_location_filter(self):
        options = self.option_group_id.option_ids
        options_to_clean = options.filtered(
            lambda op: op.clean_after_done and op.field_name in self
        )
        for option in options_to_clean:
            if option.field_name == "result_package_id" and self.keep_result_package:
                continue
            if option.field_name:
                if option.field_name == "product_id" and getattr(
                    self, option.field_name, False
                ):
                    _logger.info(
                        "[BARCODE UI] action_change_location_filter clearing product_id=%s",
                        self.product_id.id,
                    )
                setattr(self, option.field_name, False)
        self.action_show_step()
        self.product_qty = 0.0
        self.packaging_qty = 0.0
        self.lot_name = False

    # Backward compatibility shim; prefer action_change_location_filter
    def action_clean_values(self):
        return self.action_change_location_filter()

    def action_manual_entry(self):
        return True

    def reset_qty(self):
        self.product_qty = 0
        self.packaging_qty = 0

    def open_actions(self):
        self.display_menu = True
        return self.env.ref(
            "stock_barcodes.action_stock_barcodes_action_client"
        ).read()[0]

    def action_back(self):
        return self.env.ref("stock.stock_picking_type_action").read()[0]

    def open_records(self):
        action = self.action_ids
        return action

    def get_option_value(self, field_name, attribute):
        option = self.option_group_id.option_ids.filtered(
            lambda op: op.field_name == field_name
        )[:1]
        return option[attribute]

    def action_force_done(self):
        res = self.with_context(force_create_move=True).action_confirm()
        self.visible_force_done = False
        return res

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wiz in wizards:
            wiz.action_show_step()
        return wizards

    def action_manual_quantity(self):
        action = self.get_formview_action()
        form_view = self.env.ref(
            "stock_barcodes.view_stock_barcodes_read_form_manual_qty"
        )
        action["views"] = [(form_view.id, "form")]
        action["res_id"] = self.ids[0]
        return action

    def action_reopen_wizard(self):
        return self.get_formview_action()

    @api.onchange("step")
    def action_show_step(self):
        options_required = self.option_group_id.option_ids.filtered("required")
        self.step = 0
        for option in options_required:
            if not getattr(self, option.field_name, False):
                if option.field_name == "lot_id" and self.product_id.tracking == "none":
                    continue
                self.step = option.step
                break
        if not self.step:
            self.step = options_required[:1].step

        options = self.option_group_id.option_ids.filtered(
            lambda op: op.step == self.step and op.to_scan
        )
        self._set_messagge_info(
            "info_page", _("Scan {}").format(", ".join(options.mapped("name")))
        )

    @api.onchange("package_id")
    def onchange_package_id(self):
        if self.manual_entry:
            self.barcode = self.package_id.name
            self.process_barcode_package_id()

    def action_confirm(self):
        record = self.browse(self.ids)
        record.write(self._convert_to_write(self._cache))
        self = record
        if not self.product_qty:
            self.product_qty = 1.0
        res = self.action_done()
        self.invalidate_recordset()
        self.play_sounds(res)
        return res

    def action_add_scan_manual(self):
        self.manual_entry = True
        self.send_bus_done(
            "stock_barcodes_scan",
            {"type": "stock_barcodes_edit_manual", "payload": {"manual_entry": True}},
        )

    def process_lot_before_done(self):
        if (
            not self.lot_id
            and self.lot_name
            and self.product_id
            and self.product_id.tracking != "none"
            and self.option_group_id.create_lot
        ):
            self.lot_id = self._create_new_lot()
        return True

    def play_sounds(self, res=False):
        if res:
            self.send_bus_done(
                "stock_barcodes_scan",
                {
                    "type": "stock_barcodes_sound",
                    "payload": {
                        "sound": "ok",
                        "res_model": self._name,
                        "res_id": self.ids[0],
                    },
                },
            )

        else:
            self.send_bus_done(
                "stock_barcodes_scan",
                {
                    "type": "stock_barcodes_sound",
                    "payload": {
                        "sound": "ko",
                        "res_model": self._name,
                        "res_id": self.ids[0],
                    },
                },
            )

    def _set_focus_on_qty_input(self, field_name=None):
        if field_name is None:
            field_name = "product_qty"
        if field_name == "product_qty" and self.packaging_id:
            field_name = "packaging_qty"

        self.send_bus_done(
            "stock_barcodes_scan",
            {
                "type": "stock_barcodes_focus",
                "payload": {
                    "action": "focus",
                    "field_name": field_name,
                    "res_model": self._name,
                    "res_id": self.ids[0],
                },
            },
        )

    @api.onchange("product_id")
    def onchange_product_id(self):
        self.product_uom_id = self.product_id.uom_id

    @api.onchange("manual_entry")
    def onchange_manual_entry(self):
        if self.manual_entry and self.option_group_id.manual_entry_field_focus:
            self._set_focus_on_qty_input(self.option_group_id.manual_entry_field_focus)

    def _prepare_lot_vals(self):
        return {
            "name": self.lot_name,
            "product_id": self.product_id.id,
            "company_id": self.env.company.id,
        }

    def _create_new_lot(self):
        StockProductionLot = self.env["stock.lot"]
        lot_domain = [
            ("name", "=", self.lot_name),
            ("product_id", "=", self.product_id.id),
        ]
        new_lot = StockProductionLot.search(lot_domain)
        if not new_lot:
            new_lot = StockProductionLot.create(self._prepare_lot_vals())
        return new_lot

    def action_clean_message(self):
        self.message = False
        self.check_option_required()

    def action_keep_result_package(self):
        self.keep_result_package = not self.keep_result_package

    def display_notification(
        self, message, message_type="warning", title=False, sticky=True
    ):
        """Send notifications to web client
        message_type:
         [options.type='warning'] 'info', 'success', 'warning', 'danger' or ''
         sticky: Permanent notification until user removes it
        """
        if self.option_group_id.display_notification and not self.env.context.get(
            "skip_display_notification", False
        ):
            message = {
                "message": message,
                "type": message_type,
                "sticky": sticky,
                "res_model": self._name,
                "res_id": self.ids[0],
            }
            if title:
                message["title"] = title
            self.send_bus_done(
                f"stock_barcodes-{self.ids[0]}",
                {"type": f"stock_barcodes_notify-{self.ids[0]}", "payload": message},
            )
