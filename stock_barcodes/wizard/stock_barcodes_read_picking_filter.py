# Copyright 2024 Binhex
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
import traceback

from odoo import _, fields, models


_logger = logging.getLogger(__name__)


class WizStockBarcodesReadPicking(models.TransientModel):
    _inherit = "wiz.stock.barcodes.read.picking"

    # Field to store the filter domain
    picking_filter_domain = fields.Char(
        string="Picking Filter Domain",
        help="Technical field to store the current filter domain",
    )
    filtered_picking_ids = fields.Many2many(
        comodel_name="stock.picking",
        string="Filtered Pickings",
        compute="_compute_filtered_picking_ids",
        help="List of pickings after applying barcode filter",
    )
    is_filter_active = fields.Boolean(
        string="Filter Active",
        default=False,
        help="Indicates if a filter is currently applied",
    )
    filter_message = fields.Char(
        string="Filter Information",
        help="Message showing what filter is applied",
    )

    def _compute_filtered_picking_ids(self):
        """Compute filtered pickings based on the filter domain"""
        for rec in self:
            if rec.picking_filter_domain and rec.is_filter_active:
                try:
                    domain = eval(rec.picking_filter_domain)
                    rec.filtered_picking_ids = self.env["stock.picking"].search(domain)
                except Exception:
                    rec.filtered_picking_ids = rec.picking_ids
            else:
                rec.filtered_picking_ids = rec.picking_ids

    def process_barcode_for_filter(self, barcode):
        """
        Process barcode to determine if it's a picking or product
        and apply the appropriate filter
        """
        _logger.info(
            "[BARCODE FILTER] process_barcode_for_filter entry | barcode=%s | ctx=%s",
            barcode,
            dict(self.env.context or {}),
        )
        # Clean the barcode
        barcode = self._clean_barcode_scanned(barcode)

        # First, try to find a picking with this name/barcode
        picking_domain = [
            "|",
            ("name", "=", barcode),
            ("name", "ilike", barcode),
        ]
        # Add context-specific filtering (incoming/outgoing)
        if hasattr(self, "picking_type_code") and self.picking_type_code:
            picking_domain.append(("picking_type_code", "=", self.picking_type_code))

        pickings = self.env["stock.picking"].search(picking_domain, limit=1)

        if pickings:
            # Barcode matches a picking
            return self._apply_picking_filter(pickings, barcode)
        else:
            # Try to find as a product
            return self._try_product_filter(barcode)

    def _apply_picking_filter(self, picking, barcode):
        """Apply filter to show only the specific picking"""
        _logger.info(
            "[BARCODE FILTER] _apply_picking_filter | barcode=%s | picking_id=%s",
            barcode,
            picking.id,
        )
        self.picking_filter_domain = str(
            [("id", "=", picking.id)]
            + (
                [("picking_type_code", "=", self.picking_type_code)]
                if hasattr(self, "picking_type_code") and self.picking_type_code
                else []
            )
        )
        self.is_filter_active = True
        self.filter_message = _("Showing picking: %s") % picking.name
        self._set_messagge_info(
            "success", _("Filter applied: Picking %s") % picking.name
        )
        # Update the picking_ids to show only filtered results
        self.picking_ids = picking
        return True

    def _try_product_filter(self, barcode):
        """Try to find product and filter pickings containing it"""
        # Search for product by barcode
        _logger.info(
            "[BARCODE FILTER] _try_product_filter | barcode=%s",
            barcode,
        )
        product_domain = self._barcode_domain(barcode)
        product = self.env["product.product"].search(product_domain, limit=1)

        if not product:
            # Also try by default_code (internal reference)
            product = self.env["product.product"].search(
                [("default_code", "=", barcode)], limit=1
            )

        if product:
            return self._apply_product_filter(product, barcode)
        else:
            self._set_messagge_info(
                "not_found", _("No picking or product found for barcode: %s") % barcode
            )
            return False

    def _apply_product_filter(self, product, barcode):
        """Apply filter to show only pickings containing the product"""
        _logger.info(
            "[BARCODE FILTER] _apply_product_filter | barcode=%s | product_id=%s",
            barcode,
            product.id,
        )
        # Build domain to find pickings containing this product
        domain = [
            "|",
            ("move_ids.product_id", "=", product.id),
            ("move_line_ids.product_id", "=", product.id),
        ]

        # Add context-specific filtering
        if hasattr(self, "picking_type_code") and self.picking_type_code:
            domain.append(("picking_type_code", "=", self.picking_type_code))

        # Only show pickings that are in the original list
        if self.picking_ids:
            domain.append(("id", "in", self.picking_ids.ids))

        pickings_with_product = self.env["stock.picking"].search(domain)

        if pickings_with_product:
            self.picking_filter_domain = str(domain)
            self.is_filter_active = True
            self.filter_message = (
                _("Showing pickings with product: %s") % product.display_name
            )
            self._set_messagge_info(
                "success",
                _("Filter applied: Product %s (%d pickings found)")
                % (product.display_name, len(pickings_with_product)),
            )
            # Update the picking_ids to show only filtered results
            self.picking_ids = pickings_with_product
            return True
        else:
            self._set_messagge_info(
                "not_found",
                _("No pickings found containing product: %s") % product.display_name,
            )
            return False

    def action_clear_filter(self):
        """Clear the current filter and show all pickings"""
        _logger.info("[BARCODE FILTER] action_clear_filter")
        self.picking_filter_domain = False
        self.is_filter_active = False
        self.filter_message = False
        # Reset to original picking_ids if you have them stored
        # You might need to store the original list in another field
        self._set_messagge_info("info", _("Filter cleared"))
        return True

    def on_barcode_scanned(self, barcode):
        """
        Override to intercept barcode scanning in filter mode.
        Instrumented heavily to trace duplicate calls.
        """
        if self.env.context.get("onchange"):
            _logger.info(
                "[BARCODE FILTER] skipping scan during onchange | barcode=%s | ctx=%s",
                barcode,
                dict(self.env.context or {}),
            )
            return self._prepare_onchange_result()
        if not self.env.context.get("barcode_processing") and not self.env.context.get(
            "barcode_processing_reentry"
        ):
            _logger.info(
                "[BARCODE FILTER] skipping scan without barcode_processing flag | barcode=%s | ctx=%s",
                barcode,
                dict(self.env.context or {}),
            )
            return self._prepare_onchange_result()
        stack = "".join(traceback.format_stack(limit=8))
        _logger.info(
            "[BARCODE FILTER] on_barcode_scanned entry | barcode=%s | ctx=%s | stack=%s",
            barcode,
            dict(self.env.context or {}),
            stack,
        )
        # Check if we're in a context where we want to filter pickings
        # (e.g., viewing the list of pending pickings)
        if self._is_filter_mode():
            _logger.info(
                "[BARCODE FILTER] filter mode TRUE | picking_ids=%s | picking_id=%s",
                self.picking_ids.ids,
                self.picking_id.id,
            )
            return self.process_barcode_for_filter(barcode)
        else:
            # Otherwise, use the standard barcodIme processing
            _logger.info(
                "[BARCODE FILTER] delegating to super.on_barcode_scanned | picking_id=%s",
                self.picking_id.id,
            )
            return super().on_barcode_scanned(barcode)

    def _is_filter_mode(self):
        """
        Determine if we're in filter mode
        This could be based on:
        - A specific view/context
        - The current state of the wizard
        - Whether we're viewing the picking list vs working within a picking
        """
        # If we have multiple pickings and no specific picking selected,
        # we're in filter mode
        in_filter_mode = (
            len(self.picking_ids) > 1
            and not self.picking_id
            and self.env.context.get("barcode_filter_mode", False)
        )
        _logger.info(
            "[BARCODE FILTER] _is_filter_mode=%s | picking_ids=%s | picking_id=%s | ctx=%s",
            in_filter_mode,
            self.picking_ids.ids,
            self.picking_id.id,
            dict(self.env.context or {}),
        )
        return in_filter_mode
