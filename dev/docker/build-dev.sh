#!/bin/bash
set -e

# Dev build with persistent /work volume for incremental builds.
# /src is read-only source mount, /work persists between runs,
# /output maps to build/ on host.

FORCE="${1:-}"  # pass "rebuild" to force

echo "=== Nelson MCP Dev Build ==="

# Sync source to work volume (incremental — only changed files)
echo "Syncing source..."
rsync -a --delete \
    --exclude='build/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.git/' \
    --exclude='node_modules/' \
    /src/ /work/

cd /work

# Force rebuild if requested
if [ "$FORCE" = "rebuild" ]; then
    echo "Forcing rebuild..."
    rm -rf build vendor/.installed
fi

# Vendor: skip if requirements unchanged
VENDOR_HASH=$(md5sum requirements-vendor.txt | cut -d' ' -f1)
if [ ! -f "vendor/.hash_$VENDOR_HASH" ]; then
    echo "Installing vendor dependencies..."
    pip install --target vendor -r requirements-vendor.txt 2>/dev/null
    rm -f vendor/.hash_*
    touch "vendor/.hash_$VENDOR_HASH"
else
    echo "Vendor: cached"
fi

# Manifest: skip if inputs unchanged
MANIFEST_INPUTS=$(find plugin/modules -name 'module.yaml' -newer build/generated/Addons.xcu 2>/dev/null | head -1)
if [ ! -f "build/generated/Addons.xcu" ] || [ -n "$MANIFEST_INPUTS" ] || \
   [ "plugin/plugin.yaml" -nt "build/generated/Addons.xcu" ] || \
   [ "plugin/version.py" -nt "build/generated/Addons.xcu" ]; then
    echo "Generating manifests..."
    python3 scripts/generate_manifest.py
else
    echo "Manifests: cached"
fi

# Icons: skip if SVG unchanged
if [ ! -f "build/generated/assets/icon_16.png" ] || \
   [ "extension/assets/icon.svg" -nt "build/generated/assets/icon_16.png" ]; then
    echo "Generating icons..."
    mkdir -p build/generated/assets
    magick -background none -density 256 extension/assets/icon.svg -resize 16x16 build/generated/assets/icon_16.png
    magick -background none -density 256 extension/assets/icon.svg -resize 24x24 build/generated/assets/icon_24.png
    magick -background none -density 256 extension/assets/icon.svg -resize 42x42 build/generated/assets/logo.png
else
    echo "Icons: cached"
fi

# Build .oxt
echo "Building .oxt..."
python3 scripts/build_oxt.py --output /output/nelson.oxt

echo ""
echo "=== Build complete ==="
ls -lh /output/nelson.oxt
