# Installation and Upgrade Guide

## Quick Installation Steps

### 1. Upgrade the Module

```bash
# Method 1: Using Odoo CLI
./odoo-bin -u stock_barcodes -d your_database --stop-after-init

# Method 2: Using invoke (if using Doodba/docker)
invoke -c your_project upgrade stock_barcodes

# Method 3: From Odoo UI
# Apps → Search "Stock Barcodes" → Upgrade
```

### 2. Verify Installation

After upgrade, check:

```python
# In Odoo shell or Python code
model = env['wiz.stock.barcodes.read.picking']

# Check new fields exist
print('is_filter_active' in model._fields)  # Should be True
print('picking_filter_domain' in model._fields)  # Should be True
print('filtered_picking_ids' in model._fields)  # Should be True
print('filter_message' in model._fields)  # Should be True

# Check new methods exist
print(hasattr(model, 'process_barcode_for_filter'))  # Should be True
print(hasattr(model, 'action_clear_filter'))  # Should be True
```

### 3. Test Basic Functionality

```python
# Create test wizard
wizard = env['wiz.stock.barcodes.read.picking'].with_context(
    barcode_filter_mode=True
).create({})

# Test filter method exists
result = wizard.process_barcode_for_filter('TEST')
print(f"Filter method works: {result is not None}")
```

## No Database Migration Required

This enhancement adds new fields and methods but doesn't modify existing data
structures, so:

- ✅ No data migration needed
- ✅ No database schema changes to existing tables
- ✅ No risk to existing data
- ✅ Safe to install on production after testing

## Rollback Plan (if needed)

If you need to revert the changes:

### Option 1: Remove Custom Files

```bash
cd odoo/custom/src/stock-logistics-barcode/stock_barcodes/wizard/
rm stock_barcodes_read_picking_filter.py
rm stock_barcodes_read_picking_filter_views.xml

# Edit __init__.py to remove the import
# Edit __manifest__.py to remove the view reference

# Restart Odoo
```

### Option 2: Git Revert

```bash
cd odoo/custom/src/stock-logistics-barcode/
git log --oneline  # Find the commit before filter feature
git revert <commit-hash>
```

### Option 3: Disable Filter Mode

Simply don't pass `barcode_filter_mode=True` in context. The feature won't activate.

## Post-Installation Configuration

### Recommended: Add Button to Picking Type

Create a new file: `models/stock_picking_type.py`

```python
from odoo import models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    def action_open_barcode_filter_mode(self):
        """Open barcode interface in filter mode"""
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

Add to your view file: `views/stock_picking_type_views.xml`

```xml
<?xml version="1.0" encoding="utf-8" ?>
<odoo>
  <record id="view_picking_type_form_barcode_filter" model="ir.ui.view">
    <field name="name">stock.picking.type.form.barcode.filter</field>
    <field name="model">stock.picking.type</field>
    <field name="inherit_id" ref="stock.view_picking_type_form" />
    <field name="arch" type="xml">
      <xpath expr="//button[@name='get_action_picking_tree_ready']" position="after">
        <button
          name="action_open_barcode_filter_mode"
          type="object"
          string="Filter by Barcode"
          class="btn-secondary"
          icon="fa-filter"
        />
      </xpath>
    </field>
  </record>
</odoo>
```

Update your module manifest to include these files.

## Testing Checklist

### Basic Tests

- [ ] Module installs/upgrades without errors
- [ ] No errors in Odoo log
- [ ] New fields appear in wizard
- [ ] Filter mode can be activated

### Functional Tests

- [ ] Can filter by picking name
- [ ] Can filter by product barcode
- [ ] Can filter by product internal reference
- [ ] Clear filter button works
- [ ] Filter banner displays correctly
- [ ] Error messages show for invalid barcodes
- [ ] Works with Picking IN
- [ ] Works with Picking OUT
- [ ] Works with Internal Transfers

### Integration Tests

- [ ] Doesn't break existing barcode scanning
- [ ] Works with guided mode
- [ ] Works with manual entry mode
- [ ] Compatible with existing options
- [ ] Respects security groups

## Common Issues and Solutions

### Issue 1: Module Won't Upgrade

**Symptoms**: Error during upgrade, module stuck in "To Upgrade" state

**Solution**:

```bash
# Check for syntax errors
python3 -m py_compile wizard/stock_barcodes_read_picking_filter.py

# Force reinstall
./odoo-bin -u stock_barcodes -d your_database --stop-after-init --log-level=debug
```

### Issue 2: Fields Not Appearing

**Symptoms**: New fields don't show in wizard

**Solution**:

```python
# Clear cache
env.registry.clear_cache()

# Reload module
env['ir.module.module'].search([('name', '=', 'stock_barcodes')]).button_immediate_upgrade()
```

### Issue 3: View Not Loading

**Symptoms**: XML view errors

**Solution**:

```bash
# Validate XML syntax
xmllint wizard/stock_barcodes_read_picking_filter_views.xml

# Check view is in manifest
grep "stock_barcodes_read_picking_filter_views.xml" __manifest__.py
```

### Issue 4: Import Error

**Symptoms**: `ImportError: cannot import name 'stock_barcodes_read_picking_filter'`

**Solution**:

```python
# Check __init__.py includes the import
cat wizard/__init__.py | grep stock_barcodes_read_picking_filter

# Verify file exists
ls -la wizard/stock_barcodes_read_picking_filter.py
```

## Performance Optimization

### For Large Databases

If you have thousands of pickings:

```python
# Add index for faster filtering
def init_hook(cr, registry):
    cr.execute("""
        CREATE INDEX IF NOT EXISTS stock_picking_name_idx
        ON stock_picking (name);
    """)
```

Add to `hooks.py` and reference in manifest:

```python
"post_init_hook": "init_hook",
```

## Monitoring

### Track Usage

```python
# Add logging to track filter usage
import logging
_logger = logging.getLogger(__name__)

def process_barcode_for_filter(self, barcode):
    _logger.info(f"Filter activated with barcode: {barcode}")
    # ... rest of method
```

### Analytics

```python
# Count filter usage
filter_usage = env['wiz.stock.barcodes.read.picking'].search_count([
    ('is_filter_active', '=', True),
    ('create_date', '>=', '2024-01-01'),
])
print(f"Filters used: {filter_usage}")
```

## Support

For issues or questions:

1. **Check logs**: Look in Odoo server logs for errors
2. **Verify installation**: Run the verification steps above
3. **Review documentation**: See BARCODE_FILTER_README.md
4. **Test in isolation**: Create a test database
5. **Check dependencies**: Ensure base modules are updated

## Next Steps After Installation

1. **Train users**: Show warehouse staff how to use the filter
2. **Gather feedback**: Ask users if it improves their workflow
3. **Monitor performance**: Check if filtering is fast enough
4. **Customize**: Adjust filter logic based on needs
5. **Extend**: Consider adding more filter types

## Maintenance

### Recommended Maintenance Schedule

- **Weekly**: Check error logs for filter-related issues
- **Monthly**: Review filter usage analytics
- **Quarterly**: Update documentation based on user feedback
- **Yearly**: Consider enhancements and new features

### Backup Strategy

Before making changes:

```bash
# Backup database
pg_dump your_database > backup_before_filter_$(date +%Y%m%d).sql

# Backup module files
cd odoo/custom/src/stock-logistics-barcode
git add .
git commit -m "Before filter enhancement"
```

## Documentation Updates

Keep these files updated:

- `BARCODE_FILTER_README.md` - Technical documentation
- `EXAMPLES.md` - Code examples
- `QUICK_START.md` - User guide
- `IMPLEMENTATION_SUMMARY.md` - Overview

## Version History

- **1.0.0** (2024): Initial implementation
  - Filter by picking name
  - Filter by product barcode
  - Clear filter functionality
  - Visual feedback

## License

This enhancement follows the same license as the stock_barcodes module: AGPL-3.0
