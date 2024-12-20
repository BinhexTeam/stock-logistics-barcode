# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class WizStockBarcodesRead(models.AbstractModel):
    _inherit = "wiz.stock.barcodes.read"

    show_barcode_scanner = fields.Boolean(default=False)

    @api.model
    def camera_barcode_scanner(self, **kwargs):
        location_hash = kwargs.get("location_hash", "")
        if location_hash:
            wiz_stock_id = location_hash.split("id=")[1].split("&")[0]
            wiz_model_name = location_hash.split("model=")[1].split("&")[0]
            if wiz_stock_id and wiz_model_name:
                wiz_stock = self.env[wiz_model_name].sudo().browse(int(wiz_stock_id))
                if wiz_stock:
                    wiz_stock.sudo().write({"barcode": kwargs.get("barcode", False)})
                wiz_stock.process_barcode(kwargs.get("barcode", False))

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
        context = dict(self.env.context)
        domain = self._barcode_domain(self.barcode or context.get("barcode", False))
        product = self.env["product.product"].search(domain)
        if product:
            if len(product) > 1:
                self._set_messagge_info("more_match", _("More than one product found"))
                return False
            elif product.type not in self._allowed_product_types:
                self._set_messagge_info(
                    "not_found", _("The product type is not allowed")
                )
                return False
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
            lot_domain = [("name", "=", self.barcode)]
            if self.product_id:
                lot_domain.append(("product_id", "=", self.product_id.id))
            lot = self.env["stock.lot"].search(lot_domain)
            if len(lot) == 1:
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
                        self.product_id = lot.product_id
                        self.action_lot_scaned_post(lot)
                    return True
                else:
                    self.product_id = lot.product_id
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
            # self._set_messagge_info("more_match", _("Package located external location"))
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

    def process_barcode(self, barcode):
        self._set_messagge_info("success", _("OK"))
        options = self.option_group_id.option_ids
        barcode_found = False
        options_to_scan = options.filtered("to_scan")
        options_required = options.filtered("required")
        options_to_scan = options_to_scan.filtered(lambda op: op.step == self.step)
        for option in options_to_scan:
            if (
                self.option_group_id.ignore_filled_fields
                and option in options_required
                and getattr(self, option.field_name, False)
            ):
                continue
            option_func = getattr(
                self.with_context(barcode=barcode),
                "process_barcode_%s" % option.field_name,
                False,
            )
            if option_func:
                res = option_func()
                if res:
                    barcode_found = True
                    self.play_sounds(barcode_found)
                    break
                elif self.message_type != "success":
                    self.play_sounds(False)
                    return False
        if not barcode_found:
            self.play_sounds(barcode_found)
            if self.option_group_id.ignore_filled_fields:
                self._set_messagge_info(
                    "info", _("Barcode not found or field already filled")
                )
            else:
                self._set_messagge_info(
                    "not_found", _("Barcode not found with this screen values")
                )
            self.display_notification(
                self.barcode,
                message_type="danger",
                title=_("Barcode not found"),
                sticky=False,
            )
            return False
        if not self.check_option_required():
            return False
        if self.is_manual_confirm or self.manual_entry:
            self._set_messagge_info("info", _("Review and confirm"))
            return False
        return self.action_confirm()
