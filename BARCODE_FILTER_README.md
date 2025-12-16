# Stock Barcodes - Picking Filter by Barcode

## Overview

This enhancement adds the ability to filter stock pickings by scanning barcodes in the
barcode interface. When viewing pending picking records (Picking IN or Picking OUT), you
can now scan a barcode to:

1. **Filter by Picking Name**: If the barcode matches a picking name, only that specific
   picking will be displayed
2. **Filter by Product**: If the barcode matches a product, only pickings containing
   that product will be shown

## How It Works

### Barcode Detection Logic

When a barcode is scanned in filter mode:

1. **First**, the system checks if the barcode matches a picking name/reference

   - If found → Filters to show only that picking

2. **If no picking is found**, it searches for a product with that barcode

   - Searches by product barcode
   - Also searches by internal reference (default_code)
   - If found → Filters to show only pickings containing that product

3. **If neither is found**, an error message is displayed

### Usage

#### Accessing Filter Mode

The filter is automatically activated when:

- You have multiple pickings loaded
- You haven't selected a specific picking yet
- The context flag `barcode_filter_mode` is set to `True`

#### Scanning for Filtering

1. **Navigate to Picking IN or Picking OUT** view
2. **View the pending records**
3. **Scan a barcode**:
   - Scan a picking name/reference → Shows only that picking
   - Scan a product barcode → Shows only pickings with that product

#### Visual Feedback

When a filter is applied:

- **Blue info banner** appears at the top showing what filter is active
- **Filter message** explains what's being filtered (picking name or product name)
- **"Clear Filter" button** allows you to reset and see all pickings again
- **Filtered picking list** shows the matching results

#### Clearing Filters

- Click the **"Clear Filter"** button in the info banner
- Or manually call the `action_clear_filter()` method

## Technical Details

### New Fields

- `picking_filter_domain`: Stores the current filter domain (technical)
- `filtered_picking_ids`: Computed field showing filtered results
- `is_filter_active`: Boolean flag indicating if a filter is active
- `filter_message`: User-friendly message about the current filter

### Main Methods

#### `process_barcode_for_filter(barcode)`

Main entry point for barcode filtering. Determines if barcode is a picking or product.

#### `_apply_picking_filter(picking, barcode)`

Applies filter to show only the specified picking.

#### `_try_product_filter(barcode)`

Attempts to find a product and filter by it.

#### `_apply_product_filter(product, barcode)`

Applies filter to show pickings containing the specified product.

#### `action_clear_filter()`

Removes all active filters and returns to full list.

#### `_is_filter_mode()`

Determines if the wizard is in filter mode (vs normal picking processing mode).

### Override Points

The `on_barcode_scanned()` method is overridden to intercept barcodes in filter mode:

```python
def on_barcode_scanned(self, barcode):
    if self._is_filter_mode():
        return self.process_barcode_for_filter(barcode)
    else:
        return super().on_barcode_scanned(barcode)
```

## Configuration

### Enabling Filter Mode

To enable filter mode in a specific context, pass the context:

```python
{
    'barcode_filter_mode': True,
}
```

### Customization

You can customize the `_is_filter_mode()` method to define when filter mode should be
active:

```python
def _is_filter_mode(self):
    return (
        len(self.picking_ids) > 1
        and not self.picking_id
        and self.env.context.get('barcode_filter_mode', False)
    )
```

## Examples

### Example 1: Filter by Picking Name

```
User scans: "WH/IN/00042"
Result: Only picking WH/IN/00042 is shown
Message: "Showing picking: WH/IN/00042"
```

### Example 2: Filter by Product

```
User scans: "8712345678901" (product barcode)
Result: All pickings containing product "Widget A" are shown
Message: "Showing pickings with product: Widget A (3 pickings found)"
```

### Example 3: Clearing Filter

```
User clicks "Clear Filter" button
Result: All original pickings are shown again
Message: "Filter cleared"
```

## Error Handling

- **No match found**: Displays "No picking or product found for barcode: {barcode}"
- **No pickings with product**: Displays "No pickings found containing product:
  {product_name}"
- **Invalid domain**: Falls back to showing all pickings

## Integration with Existing Features

This enhancement works seamlessly with:

- Existing barcode scanning functionality
- Picking type filters (incoming/outgoing/internal)
- Pending moves display
- Detailed operations view

## Future Enhancements

Potential improvements:

1. Add filter by lot/serial number
2. Add filter by location
3. Support multiple filters simultaneously
4. Add keyboard shortcuts for clearing filters
5. Save filter preferences per user

## Troubleshooting

### Filter not activating

- Check that `barcode_filter_mode` is in context
- Verify multiple pickings are loaded
- Ensure no specific picking is selected

### Barcode not recognized

- Verify barcode format matches picking name or product barcode
- Check product has barcode or internal reference set
- Try scanning in manual entry mode first

### Filter shows wrong results

- Clear and reapply filter
- Check picking type matches (IN/OUT/INTERNAL)
- Verify product is actually in the pickings
