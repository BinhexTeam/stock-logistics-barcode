# Example Usage of Barcode Filtering

## Scenario 1: Warehouse Operator Filtering by Picking

**Context**: A warehouse operator wants to quickly find a specific picking among many
pending ones.

```python
# In Python shell or automated script

# Create wizard with filter mode enabled
wizard = env['wiz.stock.barcodes.read.picking'].with_context(
    barcode_filter_mode=True
).create({
    'picking_ids': [(6, 0, pending_pickings.ids)],  # Multiple pickings
    'option_group_id': option_group.id,
})

# Simulate scanning a picking barcode
picking_barcode = "WH/IN/00123"
wizard.on_barcode_scanned(picking_barcode)

# Check result
print(f"Filter active: {wizard.is_filter_active}")
print(f"Filter message: {wizard.filter_message}")
print(f"Filtered pickings: {wizard.filtered_picking_ids.mapped('name')}")
# Expected output:
# Filter active: True
# Filter message: Showing picking: WH/IN/00123
# Filtered pickings: ['WH/IN/00123']
```

## Scenario 2: Filtering by Product

**Context**: An operator wants to see all pickings containing a specific product.

```python
# Create wizard in filter mode
wizard = env['wiz.stock.barcodes.read.picking'].with_context(
    barcode_filter_mode=True
).create({
    'picking_ids': [(6, 0, pending_pickings.ids)],
    'option_group_id': option_group.id,
})

# Scan product barcode
product_barcode = "8712345678901"
wizard.on_barcode_scanned(product_barcode)

# Check results
print(f"Filter message: {wizard.filter_message}")
print(f"Number of pickings found: {len(wizard.filtered_picking_ids)}")
for picking in wizard.filtered_picking_ids:
    print(f"  - {picking.name}: {picking.partner_id.name}")

# Expected output:
# Filter message: Showing pickings with product: [PROD001] Widget A (3 pickings found)
# Number of pickings found: 3
#   - WH/IN/00120: Customer A
#   - WH/IN/00125: Customer B
#   - WH/IN/00130: Customer C
```

## Scenario 3: Clearing Filter

```python
# After applying a filter, clear it to see all pickings again
wizard.action_clear_filter()

print(f"Filter active: {wizard.is_filter_active}")
print(f"Available pickings: {len(wizard.picking_ids)}")
# Expected output:
# Filter active: False
# Available pickings: 25  # All original pickings
```

## Scenario 4: Error Handling - Barcode Not Found

```python
wizard = env['wiz.stock.barcodes.read.picking'].with_context(
    barcode_filter_mode=True
).create({
    'picking_ids': [(6, 0, pending_pickings.ids)],
    'option_group_id': option_group.id,
})

# Scan invalid barcode
invalid_barcode = "XXXXX"
result = wizard.on_barcode_scanned(invalid_barcode)

print(f"Result: {result}")
print(f"Message type: {wizard.message_type}")
print(f"Message: {wizard.message}")
# Expected output:
# Result: False
# Message type: not_found
# Message: No picking or product found for barcode: XXXXX
```

## Scenario 5: Integration with UI

**XML Context for opening in filter mode:**

```xml
<button
  name="%(stock_barcodes.action_stock_barcodes_picking_filter)d"
  type="action"
  string="Filter Pickings"
  class="btn-primary"
/>
```

**Or via Python:**

```python
# Open wizard in filter mode from a picking type
action = env.ref('stock_barcodes.action_stock_barcodes_picking_filter').read()[0]
action['context'] = {
    'barcode_filter_mode': True,
    'default_picking_ids': [(6, 0, picking_type.get_pending_pickings().ids)],
    'default_picking_type_code': picking_type.code,
}
return action
```

## Scenario 6: Programmatic Filter Application

```python
# Directly apply a picking filter
wizard = env['wiz.stock.barcodes.read.picking'].create({...})

picking_to_filter = env['stock.picking'].browse(123)
wizard._apply_picking_filter(picking_to_filter, picking_to_filter.name)

# Directly apply a product filter
product_to_filter = env['product.product'].browse(456)
wizard._apply_product_filter(product_to_filter, product_to_filter.barcode)
```

## Testing in Odoo Shell

```bash
# Start Odoo shell
./odoo-bin shell -d your_database

# Then in Python:
>>> env = api.Environment(cr, SUPERUSER_ID, {})
>>>
>>> # Get pending pickings
>>> picking_type = env['stock.picking.type'].search([('code', '=', 'incoming')], limit=1)
>>> pending_pickings = env['stock.picking'].search([
...     ('picking_type_id', '=', picking_type.id),
...     ('state', 'in', ['confirmed', 'assigned'])
... ])
>>>
>>> # Create wizard
>>> wizard = env['wiz.stock.barcodes.read.picking'].with_context(
...     barcode_filter_mode=True
... ).create({
...     'picking_ids': [(6, 0, pending_pickings.ids)],
...     'picking_type_code': 'incoming',
... })
>>>
>>> # Test filtering
>>> wizard.process_barcode_for_filter(pending_pickings[0].name)
>>> print(f"Filtered to: {wizard.filtered_picking_ids.mapped('name')}")
```

## UI Workflow Example

1. **User opens Picking IN screen**

   - Multiple pending pickings are loaded
   - Filter mode is automatically activated

2. **User scans barcode with handheld scanner**

   - Barcode: "WH/IN/00150"
   - System detects it's a picking name
   - Only that picking is shown

3. **User reviews the filtered picking**

   - Blue banner shows: "Showing picking: WH/IN/00150"
   - "Clear Filter" button is visible

4. **User clears filter to see all pickings**

   - Clicks "Clear Filter"
   - All 25 pending pickings are visible again

5. **User scans product barcode**
   - Barcode: "5901234123457"
   - System finds product "Laptop Stand"
   - Shows 4 pickings containing that product
   - Banner shows: "Showing pickings with product: Laptop Stand (4 pickings found)"

## Common Patterns

### Pattern 1: Quick Picking Lookup

```python
def quick_find_picking(picking_name_or_barcode):
    wizard = env['wiz.stock.barcodes.read.picking'].with_context(
        barcode_filter_mode=True
    ).create({})
    wizard.process_barcode_for_filter(picking_name_or_barcode)
    return wizard.filtered_picking_ids
```

### Pattern 2: Find All Pickings with Product

```python
def find_pickings_with_product(product_barcode):
    wizard = env['wiz.stock.barcodes.read.picking'].with_context(
        barcode_filter_mode=True
    ).create({})
    wizard._try_product_filter(product_barcode)
    return wizard.filtered_picking_ids
```

### Pattern 3: Chain Filters (Future Enhancement)

```python
# This is a potential future enhancement
def apply_multiple_filters(wizard, barcode_list):
    for barcode in barcode_list:
        wizard.process_barcode_for_filter(barcode)
    return wizard.filtered_picking_ids
```
