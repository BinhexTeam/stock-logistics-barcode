/** @odoo-module */

// IMPORTANT (Odoo 17):
// Do NOT register a custom "views" type for this feature.
// We use a global patch on FormRenderer (see form_renderer.esm.js) gated by js_class="barcode_scanner".
// This avoids Owl errors like: Renderer is undefined.
