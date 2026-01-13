{
    "name": "Stock Barcodes OWL PoC Extension",
    "summary": "Extends stock_barcodes OWL session via Python + JS patch + XML (t-inherit)",
    "version": "17.0.1.0.0",
    "license": "AGPL-3",
    "author": "OCA",
    "website": "https://github.com/OCA/stock-logistics-barcode",
    "category": "Warehouse",
    "depends": ["stock_barcodes"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "stock_barcodes_owl_poc/static/src/**/*.esm.js",
            "stock_barcodes_owl_poc/static/src/components/session/qty_adjustment.xml",
        ],
    },
    "installable": True,
}
