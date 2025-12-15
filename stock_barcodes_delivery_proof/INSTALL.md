# Installation and Setup Guide

## Module: stock_barcodes_delivery_proof

**Author:** Antonio Ruban (Binhex) **Client:** Angelina Bakery **Version:** 17.0.1.0.0

---

## Prerequisites

1. **Odoo Version:** 17.0
2. **Required Dependencies:**

   - `stock_barcodes` (OCA module)
   - `stock_move_line_qty_picked` (dependency of stock_barcodes)
   - `web_widget_numeric_step` (dependency of stock_barcodes)

3. **Browser Requirements:**
   - Modern browser with camera API support (Chrome, Firefox, Safari, Edge)
   - HTTPS connection (required for camera access on production)
   - Camera permissions granted

---

## Installation Steps

### 1. Install Dependencies

First, ensure the required OCA modules are installed:

```bash
# From Odoo Apps menu, install:
# - stock_barcodes
# Or via command line:
./odoo-bin -d your_database -i stock_barcodes --stop-after-init
```

### 2. Update Module List

```bash
# Via Odoo UI:
# Apps > Update Apps List

# Or via command line:
./odoo-bin -d your_database -u all --stop-after-init
```

### 3. Install Module

```bash
# Via Odoo UI:
# Apps > Search "Stock Barcodes Delivery Proof" > Install

# Or via command line:
./odoo-bin -d your_database -i stock_barcodes_delivery_proof --stop-after-init
```

---

## Configuration

### Step 1: Enable Delivery Proof

1. Navigate to **Inventory > Configuration > Settings**
2. Scroll to the **"Delivery Proof of Delivery"** section
3. Check **"Enable Delivery Proof Capture"**
4. Save

### Step 2: Choose Capture Level

Select one of the following:

- **Per Picking** (Recommended for Angelina Bakery)

  - Captures photos for the entire delivery
  - Simpler workflow
  - Best for deliveries with multiple products

- **Per Line**
  - Captures photos for each product line individually
  - More detailed tracking
  - Better for specific product verification

### Step 3: Grant Camera Permissions

When users first access the camera feature, the browser will request permission:

- Click **"Allow"** when prompted
- This only needs to be done once per device/browser

---

## Usage Workflow

### For Delivery Personnel (Mobile Device)

1. **Open Barcode Scanner**

   - Go to Inventory > Operations > Deliveries
   - Select a delivery order
   - Click **"Barcode Scanner"** button

2. **Process Delivery**

   - Scan products as usual
   - Verify quantities

3. **Capture Delivery Photos**

   - Click the **"Photo (0)"** button (hotkey: 9)
   - Camera interface opens
   - For "Per Line" mode: optionally select a specific product
   - Click the large camera button to take photo
   - Review the photo
   - Click **"Use Photo"** to save or **"Retake"** to try again

4. **Validate Delivery**
   - Click **"Validate"** button as normal
   - Photos are permanently attached to the delivery

### Viewing Photos Later

**Option 1: From Delivery Order**

1. Open the delivery order
2. Click the **"Photos"** smart button (top right)
3. View all captured photos

**Option 2: Delivery Proof Tab**

1. Open the delivery order
2. Go to **"Delivery Proof"** tab
3. View photos in list/kanban view
4. Add notes to photos if needed

---

## Troubleshooting

### Camera Not Working

**Problem:** Camera doesn't start or shows error

**Solutions:**

1. Check browser permissions (Settings > Privacy > Camera)
2. Ensure HTTPS connection (HTTP blocks camera on many browsers)
3. Try switching camera (use "Switch" button)
4. Close other apps using the camera
5. Try a different browser

### Photos Not Saving

**Problem:** Photo captured but doesn't appear in gallery

**Solutions:**

1. Check user permissions (must have stock_user or stock_manager)
2. Check browser console for JavaScript errors
3. Verify module is properly installed
4. Check server logs for errors

### Performance Issues

**Problem:** Camera interface is slow

**Solutions:**

1. Use lower resolution camera if available
2. Clear browser cache
3. Use native mobile browser (not in-app browsers)
4. Ensure good lighting for faster capture

---

## Technical Details

### Database Models

- **stock.delivery.proof.image**: Stores delivery photos
  - Uses ir.attachment for actual image storage (hybrid approach)
  - Linked to stock.picking (delivery)
  - Optionally linked to stock.move.line (product line)

### File Structure

```
stock_barcodes_delivery_proof/
├── models/                    # Python models
│   ├── stock_delivery_proof_image.py
│   ├── stock_picking.py
│   ├── stock_move_line.py
│   ├── res_company.py
│   └── res_config_settings.py
├── wizard/                    # Wizard extensions
│   └── stock_barcodes_read_picking.py
├── views/                     # XML views
│   ├── res_config_settings_views.xml
│   ├── stock_picking_views.xml
│   └── stock_barcodes_read_picking_views.xml
├── static/src/               # JavaScript/OWL components
│   ├── components/
│   │   ├── camera_capture/   # Camera widget
│   │   └── image_carousel/   # Photo carousel
│   ├── widgets/              # Integration widget
│   └── scss/                 # Styles
├── tests/                    # Unit tests
└── security/                 # Access rights
```

### Image Storage

Photos are stored as:

- **Format:** JPEG (85% quality)
- **Resolution:** Original camera resolution (up to 1920x1080)
- **Storage:** PostgreSQL via ir.attachment
- **Size:** Typically 100-500 KB per photo

---

## API Reference

### Python Methods

#### wizard.stock.barcodes.read.picking

```python
# Save delivery proof
def action_save_delivery_proof(self, image_data, move_line_id=False):
    """
    Save a captured image as delivery proof

    Args:
        image_data (str): Base64 encoded JPEG image
        move_line_id (int): Optional stock.move.line ID

    Returns:
        stock.delivery.proof.image: Created record
    """

# Delete delivery proof
def action_delete_delivery_proof(self, proof_id):
    """
    Delete a delivery proof image

    Args:
        proof_id (int): ID of stock.delivery.proof.image

    Returns:
        bool: True if successful
    """

# Get delivery proof data for JS
def get_delivery_proof_data(self):
    """
    Get delivery proof images data for the JS widget

    Returns:
        list: List of dictionaries with proof image data
    """
```

---

## Support

For issues or questions:

- **Developer:** Antonio Ruban <aruban@binhex.cloud>
- **Company:** Binhex
- **Client:** Angelina Bakery

---

## License

AGPL-3.0 - See LICENSE file for details
