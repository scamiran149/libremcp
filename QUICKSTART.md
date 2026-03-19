# Nelson MCP — Agent Quickstart

This guide helps LLM agents (ChatGPT, Claude, Gemini, etc.) use Nelson MCP effectively. It covers connection, tool discovery, and common workflows.

## Connect

Nelson MCP runs as an HTTP server inside LibreOffice on port 8766.

```json
{
  "mcpServers": {
    "nelson": {
      "type": "http",
      "url": "http://localhost:8766/mcp"
    }
  }
}
```

For remote access via Tailscale tunnel: `https://your-machine.tail1234.ts.net/mcp`

## First Steps

After connecting, always start with these two calls:

1. **`list_open_documents`** — see what's open (returns doc_id, title, type, path)
2. **`get_document_info`** — get details about the active document (page count, word count, sections)

If no document is open, use `open_document` or `create_document`.

## Target a Specific Document

All tools accept an optional `_document` parameter to target a document other than the active one:

- `_document: "id:abc123..."` — by Nelson doc ID (best, survives save-as)
- `_document: "title:My Report"` — by window title (partial match)
- `_document: "path:C:/Users/me/doc.odt"` — by file path

When working with multiple documents, always specify `_document` to avoid ambiguity.

## Writer Workflows

### Read a Document

```
get_document_outline        → heading tree with bookmarks
get_heading_content         → read text under a specific heading
read_paragraphs             → read paragraphs by index range
find_text / search_in_document → search for text
```

**Tip:** Use `get_document_outline` first to understand the document structure. Headings have stable bookmarks — use `heading_text:` or `bookmark:` locators to target sections.

### Edit a Document

```
insert_at_paragraph         → insert text/HTML at a position
set_paragraph_text          → replace a paragraph's content
set_paragraph_style         → apply a style (Heading 1, Body Text, etc.)
delete_paragraph            → remove a paragraph
insert_paragraphs_batch     → insert multiple paragraphs at once
```

**Tip:** Use `resolve_locator` to convert a heading name or bookmark to a paragraph index before editing. Example: `resolve_locator(locator="heading_text:Chapter 3")` returns the paragraph index.

### Tables

```
list_tables                 → find tables in the document
read_table                  → read a table's content
create_table                → create a new table
write_table_cell            → write to a specific cell
write_table_row             → write an entire row
```

### Images

```
list_images                 → find images in the document
insert_image                → insert an image (with caption)
gallery_search              → search image galleries by keyword
```

### Review Workflow

```
set_track_changes(enabled=true)
  → make edits (insert, delete, modify)
get_tracked_changes         → see all changes
accept_all_changes          → accept
set_track_changes(enabled=false)
```

### Styles

Always discover available styles first — names are localized:

```
list_styles(family="ParagraphStyles")  → list available styles
set_paragraph_style(index=5, style="Heading 1")
```

## Calc Workflows

```
list_tables                 → list sheets
read_table                  → read cell range (e.g. "A1:D10")
write_table_cell            → write to a cell
write_table_row             → write a full row
```

## Batch Operations

Use `execute_batch` to run multiple tools in one call. Supports variable chaining:

```json
{
  "steps": [
    {"tool": "get_document_outline", "output_var": "outline"},
    {"tool": "get_heading_content", "args": {"heading": "Introduction"}}
  ]
}
```

## Undo

All mutations support `undo`. If something goes wrong:

```
undo    → revert last MCP operation (one Ctrl+Z)
redo    → re-apply if needed
```

## Tool Presets

Custom endpoints may expose a subset of tools. Common presets:

| Preset | Tools | Best for |
|--------|-------|----------|
| minimal | 8 | Basic document read/write |
| writer-edit | 25 | Full Writer editing |
| writer-read | 14 | Read-only Writer access |
| calc | 13 | Spreadsheet operations |
| gallery | 10 | Image gallery browsing |

If you're on a custom endpoint, use `tools/list` to see which tools are available.

## Common Patterns

### "Add text under heading X"

```
1. get_document_outline          → find heading bookmark
2. resolve_locator("heading_text:X")  → get paragraph index
3. insert_at_paragraph(index=N+1, text="...", position="after")
```

### "Replace a paragraph"

```
1. find_text("old text")         → find paragraph index
2. set_paragraph_text(index=N, text="new text")
```

### "Insert an image from gallery"

```
1. gallery_search("sunset beach") → find image path
2. insert_image(path="/path/to/image.jpg", paragraph_index=10)
```

### "Create a report from scratch"

```
1. create_document(type="writer", path="C:/Users/me/report.odt")
2. insert_paragraphs_batch(paragraphs=[
     {"text": "Monthly Report", "style": "Heading 1"},
     {"text": "Summary of findings...", "style": "Body Text"}
   ])
3. save_document
```

## Tips

- **Bookmarks over indices** — paragraph indices shift when content is added/deleted. Use heading bookmarks or `resolve_locator` for stable references.
- **Check doc_type** — tools are filtered by document type. A Writer tool won't appear on a Calc document.
- **Batch when possible** — `execute_batch` reduces round-trips and runs faster.
- **Read before writing** — always read the current state before making edits to avoid overwriting content.
