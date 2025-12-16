# Barcode Filtering in Stock Picking List/Kanban View

## How It Works

When you're viewing the **stock.picking list or kanban view**, you can now scan a
barcode to automatically filter the records:

### Workflow

1. **Open stock.picking list/kanban** (e.g., "Picking Operations" or "All Operations")
2. **Scan a barcode** with your barcode scanner (or type it manually)
3. **System automatically filters** the view based on what the barcode matches:
   - **Picking Name**: Shows only that specific picking
   - **Product Barcode**: Shows all pickings containing that product
4. **Notification** appears showing what filter was applied
5. **View updates** to show only filtered records

### What Gets Scanned

The system checks in this order:

1. **Picking Name** - exact or partial match

   - Example: Scan "WH/IN/00042" → Shows only that picking

2. **Product Barcode** - exact match on product barcode

   - Example: Scan "8712345678901" → Shows pickings with that product

3. **Product Internal Reference** - exact match on default_code
   - Example: Scan "PROD001" → Shows pickings with that product

### Technical Details

#### Backend (Python)

**File**: `models/stock_picking.py`

Added method:

```python
def filter_by_barcode(self, barcode):
    # Returns domain and metadata for filtering
```

#### Frontend (JavaScript)

**File**: `static/src/views/stock_picking_barcode_filter.esm.js`

- Patches `ListController` and `KanbanController`
- Listens for keyboard input (barcode scanner)
- Calls backend filter method
- Applies domain to current view
- Shows notifications

#### How Barcode Input Works

```javascript
1. User scans barcode → Scanner sends keystrokes rapidly
2. JavaScript captures keypress events
3. Buffers characters (ignores input in text fields)
4. After Enter key OR 100ms pause → processes barcode
5. Calls filter_by_barcode() on backend
6. Receives domain and applies to view
7. Shows success/error notification
```

### View Integration

**File**: `views/stock_picking_barcode_filter_view.xml`

- Adds search filter hint
- Shows barcode filtering is available

## Usage Examples

### Example 1: Filter by Picking Name

```
View: 50 pending pickings visible
Action: Scan "WH/IN/00042"
Result: View shows only WH/IN/00042
Notification: "Showing picking: WH/IN/00042"
```

### Example 2: Filter by Product

```
View: 50 pending pickings visible
Action: Scan "8712345678901" (product barcode)
Result: View shows 7 pickings containing that product
Notification: "Showing 7 pickings with product: Widget A"
```

### Example 3: Not Found

```
View: 50 pending pickings visible
Action: Scan "XXXXX" (invalid barcode)
Result: View shows no records
Notification: "No picking or product found for barcode: XXXXX"
```

## Resetting Filter

To clear the filter and see all pickings again:

- **Option 1**: Click "Clear" button in the search bar
- **Option 2**: Refresh the page (F5)
- **Option 3**: Click on the "Picking Operations" menu again

## Configuration

### No Configuration Needed!

The feature works automatically on all stock.picking views:

- ✅ List view
- ✅ Kanban view
- ✅ Works in Picking Type specific views
- ✅ Works in "All Operations" view

### Barcode Scanner Setup

For best results:

1. **Configure scanner** to send Enter key after barcode
2. **Set delay** to minimum (scanner should send data fast)
3. **Test** that scanner works in any text field first

### Manual Testing

If you don't have a barcode scanner:

1. Open picking list
2. **Type quickly**: Start typing a picking name or product code
3. Press **Enter**
4. System processes it as a barcode scan

## Troubleshooting

### Filter not working

**Check**:

1. Are you on a stock.picking view?
2. Is JavaScript console showing errors? (F12)
3. Try typing manually and pressing Enter
4. Check Odoo logs for Python errors

### Scanner input going to search box

**Solution**:

- Click outside any input field first
- Scanner should send Enter key at the end

### Filter shows nothing

**Reason**: Barcode not found

- Verify barcode exists in products or pickings
- Check product has barcode field filled
- Try scanning a known picking name

## Advanced: Extending the Filter

### Add More Filter Types

Edit `models/stock_picking.py`:

```python
def filter_by_barcode(self, barcode):
    # ... existing code ...

    # Add: Filter by lot/serial number
    lot = self.env['stock.lot'].search([('name', '=', barcode)], limit=1)
    if lot:
        domain = [('move_line_ids.lot_id', '=', lot.id)]
        return {'domain': domain, 'type': 'lot', ...}

    # Add: Filter by partner
    partner = self.env['res.partner'].search([('ref', '=', barcode)], limit=1)
    if partner:
        domain = [('partner_id', '=', partner.id)]
        return {'domain': domain, 'type': 'partner', ...}
```

### Customize Timeout

Edit `static/src/views/stock_picking_barcode_filter.esm.js`:

```javascript
// Change from 100ms to 200ms
this.barcodeTimeout = setTimeout(() => {
  // ...
}, 200); // Adjust this value
```

## Performance Notes

- ✅ Efficient: Uses indexed database searches
- ✅ Fast: Filter applied immediately
- ✅ No page reload needed
- ✅ Works with large datasets

## Security

- Respects Odoo access rights
- Users only see pickings they have permission to view
- Filter applies on top of existing security rules
