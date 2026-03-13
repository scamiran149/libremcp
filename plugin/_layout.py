# Shared layout constants for Options dialog pages.
# Used by scripts/generate_manifest.py (build time) and
# plugin/options_handler.py (runtime via exec).
# NO IMPORTS — must stay dependency-free for UNO compatibility.

PAGE_WIDTH = 360          # dialog window width (fits in LO Options container)
PAGE_HEIGHT = 260
SCROLLBAR_WIDTH = 12
CONTENT_WIDTH = PAGE_WIDTH - SCROLLBAR_WIDTH  # 348 — usable area for controls
