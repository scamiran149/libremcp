# Nelson MCP Tools

## Getting Started

Open your document first using `list_open_documents` to see what's available.

**Important:** Always check open documents before creating new ones.

### Basic Workflow

1. Use `list_open_documents` to find your document
2. Use `get_document_info` for details
3. Use `read_paragraphs` to read content
4. Use `insert_at_paragraph` to add text

### Tips

- Use `_document` parameter to target a specific document
- Use `execute_batch` for multiple operations
- Use `undo` to revert changes

> Note: All tools preserve the document's aspect ratio when inserting images.

```
# Example: insert text after paragraph 10
insert_at_paragraph(paragraph_index=10, position="after", text="Hello")
```

---

## Image Tools

Use `insert_image` with a local file path:

- **width_mm** — target width in millimeters
- **max_height_mm** — prevents portrait images from filling a page
- **caption** — set to `false` to skip the caption frame
