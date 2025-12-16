# Quick Start Guide: Barcode Filtering in Stock Pickings

## Installation

The barcode filtering feature is now part of your `stock_barcodes` module. After
upgrading the module, the feature will be available.

## Step-by-Step Activation

### Method 1: From Picking Type (Recommended)

Add a button to your Picking Type form/tree view to launch the barcode interface in
filter mode:

```xml
<!-- In your custom module or directly in stock_barcodes -->
<record id="view_picking_type_form_barcode_filter" model="ir.ui.view">
  <field name="name">stock.picking.type.form.barcode.filter</field>
  <field name="model">stock.picking.type</field>
  <field name="inherit_id" ref="stock.view_picking_type_form" />
  <field name="arch" type="xml">
    <xpath expr="//header" position="inside">
      <button
        name="action_open_barcode_filter_mode"
        type="object"
        string="🔍 Filter by Barcode"
        class="btn-primary"
      />
    </xpath>
  </field>
</record>
```

Then add the method to `stock.picking.type`:

```python
# In models/stock_picking_type.py (create if doesn't exist)
from odoo import models

class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    def action_open_barcode_filter_mode(self):
        """Open barcode interface in filter mode for this picking type"""
        pending_pickings = self.env['stock.picking'].search([
            ('picking_type_id', '=', self.id),
            ('state', 'in', ['confirmed', 'assigned', 'waiting']),
        ])

        action = self.env.ref('stock_barcodes.action_stock_barcodes_picking_filter').read()[0]
        action['context'] = {
            'barcode_filter_mode': True,
            'default_picking_ids': [(6, 0, pending_pickings.ids)],
            'default_picking_type_code': self.code,
        }
        return action
```

### Method 2: From Menu Item

Add a menu item to access filter mode directly:

```xml
<menuitem
  id="menu_stock_barcode_filter_pickings"
  name="Filter Pickings"
  parent="stock.menu_stock_warehouse_mgmt"
  action="action_stock_barcodes_picking_filter"
  sequence="25"
/>
```

### Method 3: Programmatic Activation

In your code, when you want to open the barcode wizard in filter mode:

```python
def open_barcode_filter(self):
    # Get the pickings you want to filter
    pickings = self.env['stock.picking'].search([
        ('state', 'in', ['assigned', 'confirmed']),
        ('picking_type_code', '=', 'incoming'),
    ])

    # Create wizard in filter mode
    wizard = self.env['wiz.stock.barcodes.read.picking'].with_context(
        barcode_filter_mode=True,
    ).create({
        'picking_ids': [(6, 0, pickings.ids)],
        'picking_type_code': 'incoming',
    })

    return wizard.get_formview_action()
```

## Usage Flow

### For Warehouse Operators:

1. **Click "Filter by Barcode" button** on Picking Type or from menu
2. **Scan a barcode** using your handheld scanner or keyboard:
   - **Picking barcode** → See only that picking
   - **Product barcode** → See all pickings with that product
3. **Review filtered results** in the list
4. **Click "Clear Filter"** to see all pickings again
5. **Scan another barcode** to apply a new filter

### Visual Guide:

```
┌─────────────────────────────────────────┐
│  📦 Picking Type: Receipts              │
│  [🔍 Filter by Barcode]                 │
└─────────────────────────────────────────┘
         ↓ (Click button)
┌─────────────────────────────────────────┐
│  Barcode Scanner Ready                  │
│  📋 25 pending pickings loaded          │
│  ┌─────────────────────────────────┐   │
│  │ Scan barcode to filter...       │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
         ↓ (Scan "WH/IN/00042")
┌─────────────────────────────────────────┐
│  ℹ️ Showing picking: WH/IN/00042        │
│     [Clear Filter]                      │
│                                         │
│  📋 Picking: WH/IN/00042                │
│     Partner: Acme Corp                  │
│     Products: 3 items                   │
└─────────────────────────────────────────┘
         ↓ (Scan product "8712345678901")
┌─────────────────────────────────────────┐
│  ℹ️ Showing pickings with product:      │
│     Widget A (3 pickings found)         │
│     [Clear Filter]                      │
│                                         │
│  📋 Picking: WH/IN/00020                │
│  📋 Picking: WH/IN/00035                │
│  📋 Picking: WH/IN/00048                │
└─────────────────────────────────────────┘
```

## Configuration Tips

### 1. Ensure Barcodes are Set

Make sure your pickings and products have barcodes:

```python
# For products
product.barcode = "8712345678901"
# or
product.default_code = "WIDGET-A-001"

# For pickings (usually automatic)
picking.name  # e.g., "WH/IN/00042"
```

### 2. Set Context Appropriately

The filter mode is activated when:

- `barcode_filter_mode=True` in context
- Multiple pickings are available
- No specific picking is selected yet

### 3. Customize Filter Logic

You can override `_is_filter_mode()` to customize when filtering should be active:

```python
def _is_filter_mode(self):
    # Custom logic
    return (
        self.env.context.get('barcode_filter_mode', False)
        and len(self.picking_ids) > 1
        # Add your custom conditions here
    )
```

## Troubleshooting

### Issue: Filter not activating

**Solution 1**: Check context

```python
# Ensure barcode_filter_mode is True
wizard = wizard.with_context(barcode_filter_mode=True)
```

**Solution 2**: Check picking_ids

```python
# Make sure multiple pickings are loaded
print(f"Pickings loaded: {len(wizard.picking_ids)}")
```

### Issue: Barcode not recognized

**Solution**: Test barcode matching manually

```python
# Test picking match
picking = env['stock.picking'].search([('name', '=', 'WH/IN/00042')])
print(f"Picking found: {picking.name if picking else 'None'}")

# Test product match
product = env['product.product'].search([('barcode', '=', '8712345678901')])
print(f"Product found: {product.name if product else 'None'}")
```

### Issue: Wrong pickings shown

**Solution**: Check filter domain

```python
print(f"Current filter domain: {wizard.picking_filter_domain}")
print(f"Filtered pickings: {wizard.filtered_picking_ids.mapped('name')}")
```

## Advanced Usage

### Custom Filter Button on Picking List

Add a button directly on the picking tree view:

```xml
<record id="view_picking_tree_filter_button" model="ir.ui.view">
  <field name="name">stock.picking.tree.filter.button</field>
  <field name="model">stock.picking</field>
  <field name="inherit_id" ref="stock.vpicktree" />
  <field name="arch" type="xml">
    <tree position="inside">
      <button
        name="action_barcode_filter_pickings"
        type="object"
        string="Filter by Barcode"
        icon="fa-filter"
      />
    </tree>
  </field>
</record>
```

### Integration with Other Modules

If you have custom picking workflows, integrate the filter:

```python
class CustomPickingWizard(models.TransientModel):
    _inherit = 'your.custom.wizard'

    def open_with_filter(self):
        return self.env['wiz.stock.barcodes.read.picking'].with_context(
            barcode_filter_mode=True,
            # Your custom context
        ).create({
            'picking_ids': [(6, 0, self.picking_ids.ids)],
        }).get_formview_action()
```

## Next Steps

1. **Upgrade the module**: `odoo-bin -u stock_barcodes`
2. **Test the feature**: Go to Picking Type → Click "Filter by Barcode"
3. **Train users**: Show them how to scan barcodes to filter
4. **Monitor usage**: Check if operators find it useful
5. **Customize**: Adjust the `_is_filter_mode()` logic if needed

## Support

For issues or questions:

1. Check the `BARCODE_FILTER_README.md` for detailed documentation
2. Review `EXAMPLES.md` for code examples
3. Look at the implementation in `stock_barcodes_read_picking_filter.py`
