# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, models
from odoo.osv.expression import AND, OR


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _prepare_barcode_wiz_vals(self, option_group):
        vals = {
            "picking_id": self.id,
            "res_model_id": self.env.ref("stock.model_stock_picking").id,
            "res_id": self.id,
            "picking_type_code": self.picking_type_code,
            "option_group_id": option_group.id,
            "manual_entry": option_group.manual_entry,
            "picking_mode": "picking",
        }
        if self.picking_type_id.code == "outgoing":
            vals["location_dest_id"] = self.location_dest_id.id
        elif self.picking_type_id.code == "incoming":
            vals["location_id"] = self.location_id.id

        if option_group.get_option_value("location_id", "filled_default"):
            vals["location_id"] = self.location_id.id
        if option_group.get_option_value("location_dest_id", "filled_default"):
            vals["location_dest_id"] = self.location_dest_id.id
        return vals

    def action_barcode_scan(self, option_group=False):
        option_group = (
            option_group
            or self.picking_type_id.barcode_option_group_id
            or self.env.ref("stock_barcodes.stock_barcodes_option_group_operation")
        )
        wiz = self.env["wiz.stock.barcodes.read.picking"].create(
            self._prepare_barcode_wiz_vals(option_group)
        )
        wiz.fill_pending_moves()
        wiz.determine_todo_action()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock_barcodes.action_stock_barcodes_read_picking"
        )
        action["res_id"] = wiz.id
        return action

    def _name_search(
        self, name, args=None, operator="ilike", limit=100, name_get_uid=None
    ):
        """Allow barcode scans to find pickings by name, origin or products.

        Scanners usually send the barcode value, so we match product barcode
        exactly while keeping partial matches for picking names and product
        names/internal references.
        """

        args = args or []
        if not name:
            return super()._name_search(name, args, operator, limit, name_get_uid)

        search_domains = [
            [("name", operator, name)],
            [("origin", operator, name)],
            [("move_ids.product_id.barcode", "=", name)],
            [("move_ids.product_id.default_code", operator, name)],
            [("move_ids.product_id.display_name", operator, name)],
        ]

        domain = AND([OR(search_domains), args]) if args else OR(search_domains)

        return self._search(
            domain, limit=limit, access_rights_uid=name_get_uid, order=self._order
        )

    def set_quantity_from_picked(self):
        for sml in self.move_line_ids:
            sml.quantity = sml.qty_picked

    def button_validate(self):
        if self.env.context.get("stock_barcodes_validate_picking", False):
            self.set_quantity_from_picked()
        put_in_pack_picks = self.filtered(
            lambda p: p.picking_type_id.barcode_option_group_id.auto_put_in_pack
            and not p.move_line_ids.result_package_id
        )
        if put_in_pack_picks:
            put_in_pack_picks.action_put_in_pack()
        context = self.env.context
        if not context.get("picking_ids_not_to_backorder", False) and context.get(
            "skip_backorder", False
        ):
            res = super(
                StockPicking,
                self.with_context(skip_backorder=context.get("skip_backorder", False)),
            ).button_validate()
        else:
            res = super().button_validate()
        if res is True and self.env.context.get("show_picking_type_action_tree", False):
            res = self[:1].picking_type_id.get_action_picking_tree_ready()

        if self.env.context.get("stock_barcodes_validate_picking", False) and all(
            p.state == "done" for p in self
        ):
            self.env["bus.bus"]._sendone(
                "stock_barcodes_scan", "actions_barcode", {"valid_picking": True}
            )
        return res

    @api.model
    def filter_by_barcode(self, barcode=None, *args, **kwargs):
        """
        Simplified v17-style domain builder for barcode scans (kanban/list).
        Returns a domain to apply in the search bar.
        """
        try:
            # Normalize barcode from kwargs, positional arg, or context for robustness
            raw_barcode = kwargs.get("barcode") if kwargs else None
            if not raw_barcode:
                raw_barcode = barcode
            if not raw_barcode and args:
                raw_barcode = args[0]
            if not raw_barcode:
                raw_barcode = self.env.context.get("barcode")

            barcode = (raw_barcode or "").strip()
            if not barcode:
                return {
                    "domain": [("id", "=", False)],
                    "type": "not_found",
                    "message": "No barcode provided",
                }

            # 1) Exact picking name match
            picking = self.search([("name", "=", barcode)], limit=1)
            if picking:
                return {
                    "domain": [("name", "=", picking.name)],
                    "type": "picking",
                    "name": picking.name,
                    "message": f"Showing picking: {picking.display_name}",
                }

            # 2) Product match by barcode or internal reference
            product = self.env["product.product"].search(
                ["|", ("barcode", "=", barcode), ("default_code", "=", barcode)],
                limit=1,
            )
            if product:
                domain = [
                    "|",
                    ("move_ids.product_id", "=", product.id),
                    ("move_line_ids.product_id", "=", product.id),
                ]
                return {
                    "domain": domain,
                    "type": "product",
                    "product_id": product.id,
                    "product_name": product.display_name,
                    "message": f"Filtered by product: {product.display_name}",
                }

            # 3) Not found
            return {
                "domain": [("id", "=", False)],
                "type": "not_found",
                "message": f"No picking or product found for barcode: {barcode}",
            }
        except Exception as exc:
            return {
                "domain": [("id", "=", False)],
                "type": "not_found",
                "message": f"Error processing barcode: {exc}",
            }
