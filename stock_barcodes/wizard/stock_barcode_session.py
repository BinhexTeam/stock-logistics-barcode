# Copyright 2025 Tecnativa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Transient record used by the upcoming OWL barcode interface."""

from odoo import _, api, fields, models
from odoo.tools import html2plaintext


class WizStockBarcodeSession(models.TransientModel):
    _name = "wiz.stock.barcode.session"
    _description = "Barcode Session"

    profile_id = fields.Many2one(
        comodel_name="stock.barcode.profile",
        string="Profile",
        help="Concrete profile that dictates how the wizard behaves.",
    )
    picking_id = fields.Many2one(
        comodel_name="stock.picking",
        string="Picking",
    )
    picking_type_id = fields.Many2one(
        comodel_name="stock.picking.type",
        string="Operation Type",
    )
    inventory_id = fields.Many2one(
        comodel_name="stock.inventory",
        string="Inventory Adjustment",
    )
    mode = fields.Selection(
        selection=[
            ("picking", "Picking"),
            ("inventory", "Inventory"),
        ],
        default="picking",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._ensure_profile()
        return records

    def _ensure_profile(self):
        """Fill ``profile_id`` by looking at context or related records."""
        for session in self:
            if session.profile_id:
                continue
            profile = session._get_related_profile()
            if profile:
                session.profile_id = profile.id

    def _get_related_profile(self):
        self.ensure_one()
        if self.profile_id:
            return self.profile_id
        if self.picking_type_id:
            return self.picking_type_id.get_barcode_profile()
        if self.picking_id:
            return self.picking_id.picking_type_id.get_barcode_profile()
        if self.mode == "inventory":
            return self._default_inventory_profile()
        return self.env["stock.barcode.profile"]

    def _default_inventory_profile(self):
        domain = [
            ("scope", "=", "inventory"),
            ("operation_usage", "=", "inventory"),
            ("active", "=", True),
        ]
        return self.env["stock.barcode.profile"].search(domain, limit=1)

    def action_open_interface(self):
        self.ensure_one()
        profile = self._get_related_profile()
        return {
            "type": "ir.actions.client",
            "tag": "stock_barcode_session",
            "name": _("Barcode Session"),
            "context": {
                "session_id": self.id,
                "default_profile_id": profile.id,
            },
        }

    @api.model
    def open_from_client_action(self):
        """Helper used by ir.actions.client entries.

        The PoC wants OWL to be the only UI entrypoint. Some menu shortcuts are
        naturally expressed as an `ir.actions.client` with a context.

        Expected context keys:
        - session_mode: 'picking' | 'inventory'
        - picking_id: optional
        - picking_type_id: optional
        """
        mode = (self.env.context.get("session_mode") or "picking").strip()
        vals = {"mode": mode}
        picking_id = self.env.context.get("picking_id")
        if picking_id:
            vals["picking_id"] = picking_id
        picking_type_id = self.env.context.get("picking_type_id")
        if picking_type_id:
            vals["picking_type_id"] = picking_type_id
        session = self.create(vals)
        return session.action_open_interface()

    def get_session_payload(self):
        self.ensure_one()
        payload = {
            "session": self._session_payload(),
            "profile": self._profile_payload(),
        }
        if self.mode == "picking" and self.picking_id:
            payload["picking"] = self._picking_payload()
        if self.mode == "inventory" and self.inventory_id:
            payload["inventory"] = self._inventory_payload()
        payload["messages"] = self._message_payload()
        return payload

    def _session_payload(self):
        self.ensure_one()
        picking_id = self.picking_id.id if self.picking_id else False
        inventory_id = self.inventory_id.id if self.inventory_id else False
        profile_id = self.profile_id.id if self.profile_id else False
        return {
            "id": self.id,
            "mode": self.mode,
            "picking_id": picking_id,
            "inventory_id": inventory_id,
            "profile_id": profile_id,
        }

    def _profile_payload(self):
        self.ensure_one()
        profile = self.profile_id
        if not profile:
            return {}
        return {
            "id": profile.id,
            "name": profile.name,
            "operation_usage": profile.operation_usage,
            "scope": profile.scope,
            "suggestion_mode": profile.suggestion_mode,
            "allow_manual_override": profile.allow_manual_override,
            "lot_policy": profile.lot_policy,
            "allow_lot_creation": profile.allow_lot_creation,
            "package_policy": profile.package_policy,
            "allow_packages_reuse": profile.allow_packages_reuse,
            "allow_gs1_parsing": profile.allow_gs1_parsing,
            "allow_partial_validation": profile.allow_partial_validation,
            "backorder_policy": profile.backorder_policy,
            "chatter_mode": profile.chatter_mode,
        }

    def _picking_payload(self):
        self.ensure_one()
        picking = self.picking_id
        moves = picking.move_ids.filtered(lambda m: m.state != "cancel")
        lines = []
        for move in moves:
            qty_done = self._get_move_quantity_done(move)
            qty_expected = move.product_uom_qty
            uom_name = self._get_move_uom_name(move)
            move_lines = []
            for ml in move.move_line_ids.filtered(lambda l: l.state != "cancel"):
                # Keep it resilient across Odoo variants / module combos.
                qty_ml = 0.0
                if ml._fields.get("qty_done"):
                    qty_ml = ml.qty_done
                elif ml._fields.get("quantity"):
                    qty_ml = ml.quantity
                lot_name = ""
                if ml._fields.get("lot_id") and ml.lot_id:
                    lot_name = ml.lot_id.display_name
                elif ml._fields.get("lot_name") and ml.lot_name:
                    lot_name = ml.lot_name
                package_name = ""
                if ml._fields.get("package_id") and ml.package_id:
                    package_name = ml.package_id.display_name
                result_package_name = ""
                if ml._fields.get("result_package_id") and ml.result_package_id:
                    result_package_name = ml.result_package_id.display_name
                loc_src = ""
                if ml._fields.get("location_id") and ml.location_id:
                    loc_src = ml.location_id.display_name
                loc_dest = ""
                if ml._fields.get("location_dest_id") and ml.location_dest_id:
                    loc_dest = ml.location_dest_id.display_name
                owner_name = ""
                if ml._fields.get("owner_id") and ml.owner_id:
                    owner_name = ml.owner_id.display_name

                move_lines.append(
                    {
                        "id": ml.id,
                        "qty_done": qty_ml,
                        "lot": lot_name,
                        "package": package_name,
                        "result_package": result_package_name,
                        "location": loc_src,
                        "location_dest": loc_dest,
                        "owner": owner_name,
                    }
                )
            lines.append(
                {
                    "id": move.id,
                    "product": move.product_id.display_name,
                    "product_id": move.product_id.id,
                    "qty_expected": qty_expected,
                    "qty_done": qty_done,
                    "uom": uom_name,
                    "state": move.state,
                    "tracking": move.product_id.tracking,
                    "pending_qty": max(qty_expected - qty_done, 0.0),
                    "move_lines": move_lines,
                }
            )
        return {
            "id": picking.id,
            "name": picking.name,
            "state": picking.state,
            "partner": picking.partner_id.display_name,
            "scheduled_date": picking.scheduled_date,
            "priority": picking.priority,
            "move_count": len(lines),
            "ready_count": len([l for l in lines if l["pending_qty"] <= 0.0]),
            "moves": lines,
            "picking_type_id": picking.picking_type_id.id,
            "operation_type": picking.picking_type_id.display_name,
        }

    def scan_barcode(self, barcode, quantity=1.0):
        self.ensure_one()
        normalized_barcode = (barcode or "").strip()
        if not normalized_barcode:
            return {
                "status": "warning",
                "message": _("Please scan a barcode first."),
            }
        qty = self._sanitize_scan_quantity(quantity)
        if self.mode == "picking" and self.picking_id:
            result = self._scan_picking(normalized_barcode, qty)
        elif self.mode == "inventory" and self.inventory_id:
            result = self._scan_inventory(normalized_barcode, qty)
        else:
            result = {
                "status": "warning",
                "message": _(
                    "This session is not linked to any picking or inventory yet."
                ),
            }
        if self.mode == "picking" and self.picking_id and "picking" not in result:
            result["picking"] = self._picking_payload()
        if self.mode == "inventory" and self.inventory_id and "inventory" not in result:
            result["inventory"] = self._inventory_payload()
        result["messages"] = self._message_payload()
        return result

    def _get_move_quantity_done(self, move):
        self.ensure_one()
        if move._fields.get("quantity_done"):
            return move["quantity_done"]
        if move._fields.get("quantity"):
            return move["quantity"]
        return sum(move.move_line_ids.mapped("quantity"))

    def _get_move_uom_name(self, move):
        if move._fields.get("product_uom_id") and move.product_uom_id:
            return move.product_uom_id.display_name
        if move._fields.get("product_uom") and move.product_uom:
            return move.product_uom.display_name
        return move.product_id.uom_id.display_name

    def _inventory_payload(self):
        self.ensure_one()
        inventory = self.inventory_id
        return {
            "id": inventory.id,
            "name": inventory.name,
            "state": inventory.state,
            "line_count": len(inventory.line_ids),
        }

    def _message_payload(self):
        self.ensure_one()
        record = self.picking_id or self.inventory_id
        if not record:
            return []
        messages = record.message_ids.sorted("date", reverse=True)[:5]
        payload = []
        for message in messages:
            payload.append(
                {
                    "id": message.id,
                    "author": message.author_id.display_name or message.email_from,
                    "body": html2plaintext(message.body or ""),
                    "date": fields.Datetime.to_string(message.date),
                    "subtype": message.subtype_id.display_name,
                }
            )
        return payload

    def _scan_picking(self, barcode, quantity):
        self.ensure_one()
        picking = self.picking_id
        product = self._match_product_token(barcode)
        if not product:
            return {
                "status": "warning",
                "message": _(
                    "No product matches the barcode %(barcode)s.", barcode=barcode
                ),
            }
        moves = picking.move_ids.filtered(
            lambda m: m.state not in ("cancel", "done") and m.product_id == product
        )
        if not moves:
            return {
                "status": "warning",
                "message": _(
                    "The product %(product)s is not part of the pending moves.",
                    product=product.display_name,
                ),
            }
        prioritized = sorted(
            moves, key=lambda move: self._pending_move_quantity(move), reverse=True
        )
        move = prioritized[0]
        updated_field = self._increment_move_done(move, quantity)
        uom_name = self._get_move_uom_name(move)
        if updated_field:
            message = _(
                "Registered %(qty)s %(uom)s for %(product)s.",
                qty=quantity,
                uom=uom_name,
                product=product.display_name,
            )
            status = "success"
        else:
            message = _(
                "Matched %(product)s but could not record the quantity. Please review the move lines.",
                product=product.display_name,
            )
            status = "warning"
        return {
            "status": status,
            "message": message,
            "picking": self._picking_payload(),
            "focus_move_id": move.id,
        }

    def _scan_inventory(self, barcode, quantity):
        self.ensure_one()
        return {
            "status": "warning",
            "message": _("Inventory scanning will arrive in a later iteration."),
            "inventory": self._inventory_payload(),
        }

    def _pending_move_quantity(self, move):
        expected = move.product_uom_qty
        done = self._get_move_quantity_done(move)
        return max(expected - done, 0.0)

    def _match_product_token(self, token):
        Product = self.env["product.product"]
        domain = ["|", ("barcode", "=", token), ("product_tmpl_id.barcode", "=", token)]
        product = Product.search(domain, limit=1)
        if product:
            return product
        return Product.search([("default_code", "=", token)], limit=1)

    def _increment_move_done(self, move, quantity):
        if move._fields.get("quantity_done"):
            move.quantity_done = move.quantity_done + quantity
            return "quantity_done"
        if move._fields.get("quantity"):
            move.quantity = move.quantity + quantity
            return "quantity"
        for line in move.move_line_ids:
            if line._fields.get("qty_done"):
                line.qty_done = line.qty_done + quantity
                return "qty_done"
        return False

    def _sanitize_scan_quantity(self, quantity):
        try:
            qty = float(quantity)
        except (TypeError, ValueError):
            qty = 0.0
        if qty <= 0.0:
            return 1.0
        return qty
