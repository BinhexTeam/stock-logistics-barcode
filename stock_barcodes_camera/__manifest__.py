# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Stock Barcodes Camera",
    "summary": "Provides barcode reading with webcam, in stock operations.",
    "version": "16.0.1.0.0",
    "author": "Binhex, " "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/stock-logistics-barcode",
    "license": "AGPL-3",
    "category": "Extra Tools",
    "depends": ["stock_barcodes"],
    "data": [
        "wizard/stock_barcodes_read_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "/stock_barcodes_camera/static/src/**/*.esm.js",
        ],
    },
    "installable": True,
}
