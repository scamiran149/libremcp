#!/usr/bin/env bash
# tail_log.sh — Show the last N lines of the Nelson MCP log
set -euo pipefail

PROFILE_DIR="${LO_PROFILE_DIR:-/tmp/lo_dev_profile}"
LOG_FILE="$PROFILE_DIR/user/nelson.log"
LINES="${1:-50}"

if [[ -f "$LOG_FILE" ]]; then
    tail -n "$LINES" "$LOG_FILE"
else
    echo "No log file found at $LOG_FILE"
fi
