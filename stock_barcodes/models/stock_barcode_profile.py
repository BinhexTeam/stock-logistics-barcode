# Copyright 2025 Tecnativa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Barcode operation profile.

This model centralises every configuration knob that was previously split across
``stock.barcodes.action``, ``stock.barcodes.option.group`` and
``stock.barcodes.option``.  The goal is to expose a single source of truth that
any OWL component (or future batch-picking extension) can consume in order to
know how to behave for each operation type.
"""

from odoo import api, fields, models


class StockBarcodeProfile(models.Model):
    _name = "stock.barcode.profile"
    _description = "Barcode Operation Profile"

    name = fields.Char(required=True, translate=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    operation_usage = fields.Selection(
        selection=[
            ("incoming", "Receipts"),
            ("outgoing", "Deliveries"),
            ("internal", "Internal Transfers"),
            ("return", "Returns"),
            ("inventory", "Inventory Adjustments"),
        ],
        required=True,
        default="outgoing",
        tracking=True,
        help="Primary operation family this profile targets. The wizard will use"
        " it to propose defaults when no picking type is explicitly linked.",
    )
    scope = fields.Selection(
        selection=[
            ("picking", "Pickings"),
            ("inventory", "Inventory"),
        ],
        required=True,
        default="picking",
        help="Whether the profile is intended for transfers or inventory counts.",
    )
    suggestion_mode = fields.Selection(
        selection=[
            ("guided", "Suggest next move"),
            (
                "hybrid",
                "Suggest but allow override",
            ),
        ],
        default="hybrid",
        help="In hybrid mode the wizard highlights the ideal line but never"
        " blocks operators from picking a different one.",
    )
    allow_manual_override = fields.Boolean(
        default=True,
        help="If disabled the wizard will insist on the suggested move and"
        " prevent operators from jumping to another line.",
    )
    default_manual_entry = fields.Boolean(
        string="Manual entry default",
        help="Mark to load the wizard in manual-input mode instead of waiting"
        " for a first scan.",
    )
    lot_policy = fields.Selection(
        selection=[
            ("disabled", "Ignore lots/serials"),
            ("optional", "Allow lots when needed"),
            ("required", "Always require lots"),
        ],
        default="optional",
        help="Controls how lot/serial numbers are handled for tracked products.",
    )
    allow_lot_creation = fields.Boolean(
        help="Enable this if operators should be allowed to create lots/serials"
        " on the fly when scanning.",
    )
    package_policy = fields.Selection(
        selection=[
            ("disabled", "No packages"),
            ("optional", "Optional packages"),
            ("required", "Packages required"),
        ],
        default="optional",
    )
    allow_packages_reuse = fields.Boolean(
        help="If active, scanning an existing package reuses it as both source"
        " and destination when the entire content is moved.",
    )
    allow_gs1_parsing = fields.Boolean(
        string="Parse GS1", default=True, help="Enable GS1 application identifiers."
    )
    allow_negative_stock = fields.Boolean(
        help="Allow confirming moves that would bring the source location below"
        " zero without forcing a manual correction first.",
    )
    allow_partial_validation = fields.Boolean(
        default=True,
        help="If disabled the wizard forces operators to finish every reserved"
        " line before validating the transfer.",
    )
    backorder_policy = fields.Selection(
        selection=[
            ("ask", "Ask user"),
            ("auto", "Create backorder"),
            ("skip", "No backorder"),
        ],
        default="ask",
        help="Default behaviour when the transfer cannot be fully completed.",
    )
    chatter_mode = fields.Selection(
        selection=[
            ("none", "Hidden"),
            ("notes", "Notes only"),
            ("full", "Notes, activities & attachments"),
        ],
        default="notes",
        help="Controls how much of the chatter widget is exposed inside the"
        " barcode interface.",
    )
    chatter_placeholder = fields.Char(
        help="Optional helper text shown inside the chatter composer.",
    )
    color = fields.Integer(default=0)
    description = fields.Text(translate=True)

    picking_type_ids = fields.Many2many(
        comodel_name="stock.picking.type",
        compute="_compute_picking_type_ids",
        inverse="_inverse_picking_type_ids",
        string="Operation Types",
        store=False,
    )

    _sql_constraints = [
        (
            "stock_barcode_profile_name_unique",
            "unique(name)",
            "Barcode profile names must be unique.",
        )
    ]

    def _compute_picking_type_ids(self):
        for profile in self:
            profile.picking_type_ids = self.env["stock.picking.type"].search(
                [("barcode_profile_id", "=", profile.id)]
            )

    def _inverse_picking_type_ids(self):
        if not self:
            return
        PickingType = self.env["stock.picking.type"]
        for profile in self:
            if not profile.id:
                continue
            current = PickingType.search([("barcode_profile_id", "=", profile.id)])
            to_assign = profile.picking_type_ids - current
            to_clear = current - profile.picking_type_ids
            if to_assign:
                to_assign.write({"barcode_profile_id": profile.id})
            if to_clear:
                to_clear.write({"barcode_profile_id": False})

    @api.model
    def get_navigation_payload(self):
        profiles = self.search([("active", "=", True)], order="operation_usage, name")
        if not profiles:
            return []
        picking_types = profiles.mapped("picking_type_ids")
        pending_map = self._get_pending_counts_by_type(picking_types)
        usage_labels = dict(self._fields["operation_usage"].selection)
        scope_labels = dict(self._fields["scope"].selection)
        lot_labels = dict(self._fields["lot_policy"].selection)
        package_labels = dict(self._fields["package_policy"].selection)
        picking_labels = dict(self.env["stock.picking.type"]._fields["code"].selection)
        payload = []
        for profile in profiles:
            operations = []
            for picking_type in profile.picking_type_ids:
                operations.append(
                    {
                        "id": picking_type.id,
                        "name": picking_type.display_name,
                        "code": picking_type.code,
                        "code_label": picking_labels.get(
                            picking_type.code, picking_type.code
                        ),
                        "warehouse": picking_type.warehouse_id.display_name,
                        "barcode": picking_type.barcode,
                        "pending_count": pending_map.get(picking_type.id, 0),
                        "default_location_src": picking_type.default_location_src_id.display_name,
                        "default_location_dest": picking_type.default_location_dest_id.display_name,
                    }
                )
            payload.append(
                {
                    "id": profile.id,
                    "name": profile.name,
                    "operation_usage": profile.operation_usage,
                    "operation_usage_label": usage_labels.get(
                        profile.operation_usage, profile.operation_usage
                    ),
                    "scope": profile.scope,
                    "scope_label": scope_labels.get(profile.scope, profile.scope),
                    "color": profile.color,
                    "description": profile.description or "",
                    "allow_gs1_parsing": profile.allow_gs1_parsing,
                    "lot_policy": profile.lot_policy,
                    "lot_policy_label": lot_labels.get(
                        profile.lot_policy, profile.lot_policy
                    ),
                    "package_policy": profile.package_policy,
                    "package_policy_label": package_labels.get(
                        profile.package_policy, profile.package_policy
                    ),
                    "allow_manual_override": profile.allow_manual_override,
                    "backorder_policy": profile.backorder_policy,
                    "picking_types": operations,
                }
            )
        return payload

    @api.model
    def _get_pending_counts_by_type(self, picking_types):
        result = {}
        if not picking_types:
            return result
        domain = [
            ("picking_type_id", "in", picking_types.ids),
            ("state", "not in", ("done", "cancel")),
        ]
        groups = self.env["stock.picking"].read_group(
            domain, ["picking_type_id"], ["picking_type_id"]
        )
        for entry in groups:
            picking_type_id = entry["picking_type_id"][0]
            result[picking_type_id] = entry.get(
                "picking_type_id_count", entry.get("__count", 0)
            )
        return result
