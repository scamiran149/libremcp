#!/usr/bin/env bash
# open_options.sh — Open LibreOffice Options dialog (Alt+F12)
set -euo pipefail

XD="${WBOX_X_DISPLAY:-${COMPOSITOR_X_DISPLAY:-:2}}"

DISPLAY="$XD" xdotool key --delay 100 alt+F12
echo "Sent Alt+F12 (Options dialog)"
