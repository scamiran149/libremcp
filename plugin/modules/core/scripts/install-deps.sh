#!/bin/bash
# LibreMCP - Install missing Python dependencies for LibreOffice
# On Linux/Mac, sqlite3 is normally available — this is a safety net.

set -e

LIB_DIR="$1"

echo "=== LibreMCP — Install Dependencies ==="
echo ""

if [ -z "$LIB_DIR" ]; then
    echo "ERROR: lib directory argument required."
    exit 1
fi

PYSQLITE3_DIR="$LIB_DIR/pysqlite3"

if [ -f "$PYSQLITE3_DIR/__init__.py" ]; then
    echo "[OK] pysqlite3 already installed at $PYSQLITE3_DIR"
    echo ""
    echo "Done. Press Enter to close."
    read -r
    exit 0
fi

# On Linux, sqlite3 is usually built into Python — check first
python3 -c "import sqlite3" 2>/dev/null && {
    echo "[OK] sqlite3 is available in system Python — no action needed."
    echo ""
    echo "Press Enter to close."
    read -r
    exit 0
}

echo "sqlite3 not found in Python — installing pysqlite3 from PyPI..."
echo ""

# Detect Python version
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')" 2>/dev/null || echo "312")
PLATFORM=$(python3 -c "import sys; print('manylinux' if sys.platform=='linux' else 'macosx')" 2>/dev/null || echo "manylinux")
ARCH=$(python3 -c "import struct; print('x86_64' if struct.calcsize('P')*8==64 else 'i686')" 2>/dev/null || echo "x86_64")

echo "Target: pysqlite3 for cp$PY_VER $PLATFORM $ARCH"

# Fetch wheel URL from PyPI
PYPI_JSON=$(curl -sS --max-time 30 "https://pypi.org/pypi/pysqlite3/json") || {
    echo "ERROR: Failed to reach PyPI. Check internet connection."
    read -r
    exit 1
}

WHEEL_URL=$(echo "$PYPI_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
tag = 'cp$PY_VER'
for urls in [data.get('urls', [])] + list(data.get('releases', {}).values()):
    for f in urls:
        fn = f['filename']
        if tag in fn and '$PLATFORM' in fn and '$ARCH' in fn and fn.endswith('.whl'):
            print(f['url'])
            sys.exit(0)
print('')
" 2>/dev/null)

if [ -z "$WHEEL_URL" ]; then
    echo "ERROR: No pysqlite3 wheel found for cp$PY_VER $PLATFORM $ARCH"
    echo "You may need to install it manually: pip install pysqlite3"
    read -r
    exit 1
fi

echo "Downloading: $WHEEL_URL"
TEMP_WHL=$(mktemp /tmp/pysqlite3.XXXXXX.whl)

curl -sS --max-time 60 -o "$TEMP_WHL" "$WHEEL_URL" || {
    echo "ERROR: Download failed."
    rm -f "$TEMP_WHL"
    read -r
    exit 1
}

SIZE=$(du -k "$TEMP_WHL" | cut -f1)
echo "Downloaded ${SIZE} KB"

# Extract pysqlite3/ from wheel
echo "Extracting to $LIB_DIR ..."
mkdir -p "$LIB_DIR"
rm -rf "$PYSQLITE3_DIR"

python3 -c "
import zipfile, os, sys
with zipfile.ZipFile('$TEMP_WHL') as zf:
    for name in zf.namelist():
        if name.startswith('pysqlite3/'):
            target = os.path.join('$LIB_DIR', name)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if not name.endswith('/'):
                with open(target, 'wb') as f:
                    f.write(zf.read(name))
" || {
    echo "ERROR: Extraction failed."
    rm -f "$TEMP_WHL"
    read -r
    exit 1
}

rm -f "$TEMP_WHL"

# Verify
if [ -f "$PYSQLITE3_DIR/__init__.py" ]; then
    echo ""
    echo "[OK] pysqlite3 installed successfully!"
    echo "Please restart LibreOffice for changes to take effect."
else
    echo ""
    echo "ERROR: Installation verification failed."
fi

echo ""
echo "Press Enter to close."
read -r
