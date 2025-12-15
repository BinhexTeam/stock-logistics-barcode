#!/bin/bash
# Module Verification Script for stock_barcodes_delivery_proof
# Author: Antonio Ruban (Binhex)
# Date: 2024

set -e

MODULE_PATH="/home/adruban/Workspace/Doodba_ENV/O17/odoo/custom/src/stock-logistics-barcode/stock_barcodes_delivery_proof"

echo "============================================"
echo "Stock Barcodes Delivery Proof - Verification"
echo "============================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print success
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Function to print error
print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

cd "$MODULE_PATH"

echo "1. Checking module structure..."
echo "================================"

# Check critical files exist
CRITICAL_FILES=(
    "__init__.py"
    "__manifest__.py"
    "models/__init__.py"
    "wizard/__init__.py"
    "views/res_config_settings_views.xml"
    "views/stock_picking_views.xml"
    "views/stock_barcodes_read_picking_views.xml"
    "security/ir.model.access.csv"
)

for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_success "$file exists"
    else
        print_error "$file is missing!"
        exit 1
    fi
done
echo ""

echo "2. Checking Python syntax..."
echo "============================="
PYTHON_ERROR=0
for pyfile in $(find . -name "*.py"); do
    if python3 -m py_compile "$pyfile" 2>/dev/null; then
        print_success "$pyfile"
    else
        print_error "$pyfile has syntax errors!"
        python3 -m py_compile "$pyfile"
        PYTHON_ERROR=1
    fi
done

if [ $PYTHON_ERROR -eq 1 ]; then
    echo ""
    print_error "Python syntax errors found. Please fix before installation."
    exit 1
fi
echo ""

echo "3. Checking XML syntax..."
echo "========================="
for xmlfile in $(find ./views -name "*.xml"); do
    if xmllint --noout "$xmlfile" 2>/dev/null; then
        print_success "$xmlfile"
    else
        print_error "$xmlfile has XML errors!"
        xmllint --noout "$xmlfile"
        exit 1
    fi
done
echo ""

echo "4. Checking author information..."
echo "=================================="
if grep -q "Binhex" __manifest__.py && grep -q "Antonio Ruban" models/*.py; then
    print_success "Author information is correct (Binhex - Antonio Ruban)"
else
    print_warning "Author information may need verification"
fi
echo ""

echo "5. Checking dependencies..."
echo "==========================="
if grep -q "stock_barcodes" __manifest__.py; then
    print_success "Dependency on stock_barcodes found"
else
    print_error "Missing stock_barcodes dependency!"
    exit 1
fi
echo ""

echo "6. File count summary..."
echo "========================"
echo "Python files:      $(find . -name "*.py" | wc -l)"
echo "JavaScript files:  $(find . -name "*.js" | wc -l)"
echo "XML files:         $(find . -name "*.xml" | wc -l)"
echo "SCSS files:        $(find . -name "*.scss" | wc -l)"
echo "Total files:       $(find . -type f | wc -l)"
echo ""

echo "7. JavaScript/OWL components..."
echo "==============================="
if [ -d "static/src/components/camera_capture" ]; then
    print_success "CameraCapture component found"
else
    print_error "CameraCapture component missing!"
fi

if [ -d "static/src/components/image_carousel" ]; then
    print_success "ImageCarousel component found"
else
    print_error "ImageCarousel component missing!"
fi

if [ -f "static/src/widgets/delivery_proof_widget.js" ]; then
    print_success "DeliveryProofWidget found"
else
    print_error "DeliveryProofWidget missing!"
fi
echo ""

echo "8. Documentation check..."
echo "========================="
DOCS=(
    "README.rst"
    "INSTALL.md"
    "readme/DESCRIPTION.md"
    "readme/CONFIGURE.md"
    "readme/USAGE.md"
    "readme/CONTRIBUTORS.md"
)

for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        print_success "$doc"
    else
        print_warning "$doc not found (optional)"
    fi
done
echo ""

echo "9. Security check..."
echo "===================="
if grep -q "stock_delivery_proof_image" security/ir.model.access.csv; then
    print_success "Access rights configured for stock.delivery.proof.image"
else
    print_error "Missing access rights!"
    exit 1
fi
echo ""

echo "============================================"
echo -e "${GREEN}✓ All checks passed!${NC}"
echo "============================================"
echo ""
echo "Module is ready for installation!"
echo ""
echo "Next steps:"
echo "1. Update module list in Odoo"
echo "2. Install 'Stock Barcodes Delivery Proof' module"
echo "3. Configure in Inventory > Settings"
echo "4. Test with a delivery order"
echo ""
echo "For detailed instructions, see INSTALL.md"
echo ""
