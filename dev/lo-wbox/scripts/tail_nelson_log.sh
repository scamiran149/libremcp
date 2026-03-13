#!/usr/bin/env bash
# tail_nelson_log.sh — Show the last N lines of the Nelson extension log
set -euo pipefail

LOG_FILE="${NELSON_LOG_PATH:-$HOME/nelson.log}"
LINES="${WBOX_ARG_LINES:-${1:-50}}"

if [[ -f "$LOG_FILE" ]]; then
    tail -n "$LINES" "$LOG_FILE"
else
    echo "No log file found at $LOG_FILE"
fi
