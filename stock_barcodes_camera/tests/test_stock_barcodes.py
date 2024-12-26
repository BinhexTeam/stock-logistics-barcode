# Copyright 2108-2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.tests.common import tagged

from .common import TestCommonStockBarcodes


@tagged("post_install", "-at_install")
class TestStockBarcodes(TestCommonStockBarcodes):
    def test_location_hash(self):
        valid_hash = self.camera_barcode_scanner(self.location_hash)
        self.assertEqual(valid_hash, True)
        empty_hash = self.camera_barcode_scanner()
        self.assertEqual(empty_hash, False)
        with self.assertRaises(IndexError):
            invalid_loc_hash = self.location_hash.replace("id=", "idd=")
            self.camera_barcode_scanner(invalid_loc_hash)
        with self.assertRaises(IndexError):
            invalid_loc_hash = self.location_hash.replace("model=", "modell=")
            self.camera_barcode_scanner(invalid_loc_hash)

    def test_open_inventory_action_valid_context(self):
        test_context = {"default_model": "stock.barcodes.action"}
        action = self.stock_barcodes_action.open_inventory_action(test_context)
        self.assertIn("res_id", action, "The action should contain a 'res_id'.")
        self.assertIn("context", action, "The action should contain a 'context'.")
        self.assertEqual(
            action["context"],
            test_context,
            "The context should match the provided one.",
        )

    def test_open_inventory_action_missing_option_group(self):
        option_group = self.env.ref(
            "stock_barcodes.stock_barcodes_option_group_inventory"
        )
        if option_group:
            option_group.unlink()
        with self.assertRaises(
            ValueError, msg="Expected exception for missing option group."
        ):
            self.stock_barcodes_action.open_inventory_action({})

    def test_open_inventory_action_camera_barcode_scanner_disabled(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "stock_barcodes.enable_camera_barcode_scanner", False
        )
        action = self.stock_barcodes_action.open_inventory_action({})
        res_id = action.get("res_id")
        wiz = self.env["wiz.stock.barcodes.read.inventory"].browse(res_id)
        self.assertFalse(
            wiz.show_barcode_scanner, "Barcode scanner should be disabled."
        )

    def test_open_inventory_action_camera_barcode_scanner_enabled(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "stock_barcodes.enable_camera_barcode_scanner", True
        )
        action = self.stock_barcodes_action.open_inventory_action({})
        res_id = action.get("res_id")
        wiz = self.env["wiz.stock.barcodes.read.inventory"].browse(res_id)
        self.assertTrue(wiz.show_barcode_scanner, "Barcode scanner should be enabled.")
