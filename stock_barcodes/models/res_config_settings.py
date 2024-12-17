# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    enable_camera_barcode_scanner = fields.Boolean(
        "Barcode Scanner",
        config_parameter="stock_barcodes.enable_camera_barcode_scanner",
    )
