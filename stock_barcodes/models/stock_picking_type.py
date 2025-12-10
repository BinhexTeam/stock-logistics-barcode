# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from ast import literal_eval

from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    barcode_option_group_id = fields.Many2one(
        comodel_name="stock.barcodes.option.group"
    )

    barcode_profile_id = fields.Many2one(
        comodel_name="stock.barcode.profile",
        string="Barcode Profile",
        help="Single source of configuration used by the new barcode"
        " interface. Leave empty to fall back on a profile that matches"
        " the operation usage (incoming/outgoing/internal).",
    )

    new_picking_barcode_option_group_id = fields.Many2one(
        comodel_name="stock.barcodes.option.group",
        help="This Barcode Option Group will be selected when clicking the 'New' button"
        " in an operation type. It will be used to create a non planned picking.",
    )

    def get_barcode_profile(self):
        self.ensure_one()
        profile = self.barcode_profile_id
        if profile:
            return profile
        return self._find_fallback_barcode_profile()

    def _find_fallback_barcode_profile(self):
        usage = self._get_barcode_operation_usage()
        if not usage:
            return self.env["stock.barcode.profile"]
        domain = [
            ("operation_usage", "=", usage),
            ("scope", "=", "picking"),
            ("active", "=", True),
        ]
        return self.env["stock.barcode.profile"].search(domain, limit=1)

    def _get_barcode_operation_usage(self):
        self.ensure_one()
        return {
            "incoming": "incoming",
            "outgoing": "outgoing",
            "internal": "internal",
        }.get(self.code or False, False)

    def action_barcode_scan(self):
        session = self._create_barcode_session()
        return session.action_open_interface()

    def action_barcode_new_picking(self):
        self.ensure_one()
        picking = (
            self.env["stock.picking"]
            .with_context(default_immediate_transfer=True)
            .create(
                {
                    "picking_type_id": self.id,
                    "location_id": self.default_location_src_id.id,
                    "location_dest_id": self.default_location_dest_id.id,
                }
            )
        )
        option_group = self.new_picking_barcode_option_group_id
        return picking.action_barcode_scan(option_group=option_group)

    def _create_barcode_session(self):
        self.ensure_one()
        session_vals = {
            "picking_type_id": self.id,
            "mode": "picking",
        }
        return self.env["wiz.stock.barcode.session"].create(session_vals)

    def get_action_picking_tree_ready(self):
        context = dict(self.env.context)
        if context.get("operations_mode", False):
            return self._get_action(
                "stock_barcodes.stock_barcodes_action_picking_tree_ready"
            )
        return super().get_action_picking_tree_ready()

    def _get_action(self, action_xmlid):
        action = self.env["ir.actions.actions"]._for_xml_id(action_xmlid)
        if self:
            action["display_name"] = self.display_name

        default_immediate_tranfer = True
        if (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("stock.no_default_immediate_tranfer")
        ):
            default_immediate_tranfer = False

        context = {
            "search_default_picking_type_id": [self.id],
            "default_picking_type_id": self.id,
            "default_immediate_transfer": default_immediate_tranfer,
            "default_company_id": self.company_id.id,
        }

        action_context = literal_eval(action["context"].strip())
        context = {**action_context, **context}
        if "operations_mode" in self.env.context:
            context["operations_mode"] = self.env.context["operations_mode"]
        action["context"] = context
        return action
