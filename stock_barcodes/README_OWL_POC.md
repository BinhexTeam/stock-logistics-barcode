# OWL barcode session (Proof of Concept)

This addon ships an **OWL-first** barcode scanning interface for stock operations.

The point of this PoC is not perfect scan business logic, but to demonstrate the
**extensibility and modularity** that OWL enables compared to the classic “giant wizard
form” approach.

## What opens when you click “Barcode Scan”

- `stock.picking.action_barcode_scan()` returns an **OWL client action**
  (`type=ir.actions.client`, `tag=stock_barcode_session`).
- `stock.picking.type.action_barcode_scan()` returns the same OWL client action.

No wizard UI is used as the entrypoint.

## Backend ↔ Frontend contract

The OWL root component loads everything with a single RPC:

- Model: `wiz.stock.barcode.session`
- Method: `get_session_payload(session_id)`

Payload shape is intentionally **UI-oriented** and stable:

- `payload.session`: session metadata (mode, picking_id/inventory_id, profile_id)
- `payload.profile`: barcode profile flags (used for badges + hints)
- `payload.picking` (when mode = picking):
  - `moves[]` contains nested `move_lines[]` so the UI can render a complete hierarchy
    without extra RPCs
- `payload.messages`: latest chatter messages

## UI extensibility (2 complementary patterns)

### 1) XML-first (classic QWeb inheritance)

`stock_barcodes/static/src/components/session/session.xml` calls dedicated hook
templates:

- `stock_barcodes.BarcodeSessionHeaderExtension`
- `stock_barcodes.BarcodeSessionScanExtension`
- `stock_barcodes.BarcodeSessionMovesExtension`
- `stock_barcodes.BarcodeSessionChatterExtension`

Any downstream module can inject content using:

- `t-inherit="stock_barcodes.BarcodeSessionScanExtension"`
- `t-inherit-mode="extension"`
- `xpath` targeting `.` (root)

A demo is included in:

- `stock_barcodes/views/stock_barcode_session_extension_demo.xml`

### 2) JS-first (registry-based panels)

For cases where a module needs JS behavior, the session provides a registry panel
system:

- Category: `stock_barcodes.barcode_session_panels`
- Renderer: `BarcodeSessionExtensionPanels`

Panels can be ordered with a `sequence` and can be shipped as separate addons without
patching the root component.

## Notes

- This is a PoC. The UI contract is the focus.
- Old wizard views are intentionally not loaded by the manifest to avoid confusion
  during demos.
