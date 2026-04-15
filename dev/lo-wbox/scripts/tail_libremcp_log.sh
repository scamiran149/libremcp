#!/usr/bin/env bash
# tail_libremcp_log.sh — Show the last N lines of the LibreMCP extension log
set -euo pipefail

LOG_FILE="${LIBREMCP_LOG_PATH:-$HOME/libremcp.log}"
LINES="${WBOX_ARG_LINES:-${1:-50}}"

if [[ -f "$LOG_FILE" ]]; then
    tail -n "$LINES" "$LOG_FILE"
else
    echo "No log file found at $LOG_FILE"
fi
