# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Stock Barcodes Camera",
    "summary": "Provides barcode reading with webcam, in stock operations.",
    "version": "17.0.1.0.0",
    "author": "Binhex, " "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/stock-logistics-barcode",
    "license": "AGPL-3",
    "category": "Extra Tools",
    "depends": ["stock", "stock_barcodes"],
    "data": [
        "wizard/stock_barcodes_read_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_barcodes_camera/static/src/polyfills/request_idle_callback.esm.js",
            "stock_barcodes_camera/static/src/views/form/form_renderer.esm.js",
            "stock_barcodes_camera/static/src/views/barcode_scanner/barcode_scanner.esm.js",
            
        ],
    },
    "installable": True,
}
