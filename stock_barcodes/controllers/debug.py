# Copyright 2025
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class StockBarcodesDebugController(http.Controller):
    @http.route(
        "/stock_barcodes/debug_log",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def debug_log(self, **payload):
        # Intentionally minimal: log whatever the client sends for field diagnostics.
        partner = request.env.user.partner_id
        _logger.info("[stock_barcodes][debug] partner=%s payload=%s", partner.id, payload)
        return {"status": "ok"}
