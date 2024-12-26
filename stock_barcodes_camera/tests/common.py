# Copyright 2108-2019 Francois Poizat <francois.poizat@gmail.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase


class TestCommonStockBarcodes(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.location_hash = (
            "#id=17&model=wiz.stock.barcodes.read.inventory&view_type=form"
        )
        cls.stock_barcodes_action = cls.env["stock.barcodes.action"]

    def camera_barcode_scanner(self, location_hash=""):
        if location_hash:
            wiz_stock_id = location_hash.split("id=")[1].split("&")[0]
            wiz_model_name = location_hash.split("model=")[1].split("&")[0]
            if not wiz_stock_id or not wiz_model_name:
                return False
            return True
        else:
            return False
