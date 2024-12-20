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
