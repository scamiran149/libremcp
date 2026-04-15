#!/bin/bash
set -e

echo "=== LibreMCP Docker Build ==="

# Use a temp working dir (writable by any UID)
WORK=$(mktemp -d)
trap "rm -rf $WORK" EXIT

# Copy source from read-only mount to working dir
echo "Copying source..."
cp -a /src/. "$WORK/"
cd "$WORK"

# Install vendored pip dependencies
echo "Installing vendor dependencies..."
pip install --target vendor -r requirements-vendor.txt

# Generate manifests
echo "Generating manifests..."
python3 scripts/generate_manifest.py

# Generate icons (SVG → PNG)
echo "Generating icons..."
mkdir -p build/generated/assets
magick -background none -density 256 extension/assets/icon.svg -resize 16x16 build/generated/assets/icon_16.png
magick -background none -density 256 extension/assets/icon.svg -resize 24x24 build/generated/assets/icon_24.png
magick -background none -density 256 extension/assets/icon.svg -resize 42x42 build/generated/assets/logo.png

# Build .oxt
echo "Building .oxt..."
python3 scripts/build_oxt.py --output /output/libremcp.oxt

# Report result
echo ""
echo "=== Build complete ==="
ls -lh /output/libremcp.oxt
