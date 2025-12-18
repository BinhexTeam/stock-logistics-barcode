# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Stock Barcodes Delivery Proof",
    "summary": "Capture delivery proof photos via barcode scanner per move line",
    "version": "17.0.6.4.0",
    "author": "Binhex, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/stock-logistics-barcode",
    "license": "AGPL-3",
    "category": "Warehouse",
    "depends": [
        "stock_barcodes",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/stock_barcodes_read_picking_views.xml",
        "views/stock_delivery_proof_image_views.xml",
        "views/stock_picking_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_barcodes_delivery_proof/static/src/components/**/*.esm.js",
            "stock_barcodes_delivery_proof/static/src/components/**/*.xml",
            "stock_barcodes_delivery_proof/static/src/components/**/*.scss",
            "stock_barcodes_delivery_proof/static/src/actions/**/*.esm.js",
            "stock_barcodes_delivery_proof/static/src/scss/**/*.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
