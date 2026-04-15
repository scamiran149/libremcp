# LibreMCP — Tool Reference

Complete reference for all 128 tools exposed via the MCP server.

## Connection

```json
{
  "mcpServers": {
    "libremcp": {
      "type": "http",
      "url": "http://localhost:8766/mcp"
    }
  }
}
```

## Conventions

- **Mutation tools** modify the document. They are automatically wrapped in undo contexts.
- **`_document`** — All tools accept an optional `_document` parameter to target a specific document: `id:<doc_id>`, `title:<title>`, or `path:<filepath>`.
- **Doc-type filtering** — Tools are filtered by the active document type. Only compatible tools appear in `tools/list`.
- **Tier** — `core` tools are always exposed on `/mcp/core`; `extended` tools are only on the full `/mcp` endpoint. Point your MCP client to `http://localhost:8766/mcp/core` for core-only (~64 tools) or `http://localhost:8766/mcp` for everything.

---

## Module: `doc` (19 tools)

Document-agnostic tools that work on all document types.

### File Operations

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `open_document` | Open a document file in LibreOffice | No | core | `file_path` |
| `create_document` | Create a new empty document (writer/calc/impress/draw) | No | core | `doc_type`, `path?`, `content?` |
| `save_document` | Save current document (first save needs path) | Yes | core | `path?` |
| `save_document_as` | Save document to a new path | No | core | `target_path` |
| `export_pdf` | Export document to PDF | No | core | `path` |
| `close_document` | Close current document | Yes | core | — |
| `list_open_documents` | List all open documents | No | core | — |
| `get_recent_documents` | Get recently opened documents from LO history | No | core | `max_count?` |

### Document Info & Properties

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `get_document_info` | Document metadata (title, type, modified, author, etc.) | No | core | — |
| `set_document_properties` | Set document metadata (title, subject, author, description, keywords) | Yes | extended | `title?`, `subject?`, `author?`, `description?`, `keywords?` |

### Undo/Redo

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `undo` | Undo last action(s) | Yes | core | `steps?` |
| `redo` | Redo last undone action(s) | Yes | core | `steps?` |

### Hyperlinks *(writer, calc)*

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `list_hyperlinks` | List all hyperlinks | No | core | `calc?` |
| `insert_hyperlink` | Insert a hyperlink | Yes | core | `url`, `text?`, `writer?`, `calc?` |
| `remove_hyperlink` | Remove hyperlink by index (preserves text) | Yes | extended | `index`, `calc?` |
| `edit_hyperlink` | Edit existing hyperlink URL/text | Yes | extended | `index`, `url?`, `text?`, `calc?` |

### Diagnostics *(writer)*

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `document_health_check` | Structural health checks (empty headings, level jumps, etc.) | No | extended | — |
| `set_document_protection` | Set/remove section protection | Yes | extended | `enabled`, `password?` |

### Images *(all doc types)*

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `list_images` | List all images/graphic objects | No | core | `draw?`, `calc?` |
| `get_image_info` | Get detailed image info (dimensions, anchor, etc.) | No | extended | `image_name?`, `shape_index?`, `draw?`, `calc?` |
| `set_image_properties` | Resize/reposition/crop/alt-text a Writer image | Yes | extended | `image_name`, `width_mm?`, `height_mm?`, `title?`, `description?`, `anchor_type?`, `hori_orient?`, `vert_orient?` |
| `download_image` | Download image from URL to local cache | No | extended | `url`, `verify_ssl?`, `force?` |
| `insert_image` | Insert image from path/URL | Yes | core | `image_path`, `width_mm?`, `height_mm?`, `max_height_mm?`, `caption?`, `title?`, `description?`, `writer?`, `draw?`, `calc?` |
| `delete_image` | Delete image from document | Yes | extended | `image_name?`, `shape_index?`, `draw?`, `calc?` |
| `replace_image` | Replace Writer image source keeping position | Yes | extended | `image_name`, `new_image_path`, `width_mm?`, `height_mm?` |

### Print

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `print_document` | Print document to default/named printer | No | extended | `printer?`, `pages?`, `copies?` |

---

## Module: `writer` (44 tools)

Writer document tools — content editing, styles, tables, comments, track changes, images, search.

### Content

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `get_document_content` | Get document (or selection/range) content | No | core | `scope?`, `max_chars?`, `start?`, `end?` |
| `apply_document_content` | Insert or replace content (target: beginning/end/selection/search/full/range) | Yes | core | `content`, `target`, `start?`, `end?`, `search?`, `all_matches?`, `case_sensitive?` |
| `read_paragraphs` | Read a range of paragraphs by index or locator | No | core | `start_index?`, `locator?`, `count?` |
| `set_paragraph_text` | Replace entire paragraph text (preserves style) | Yes | core | `text`, `paragraph_index?`, `locator?` |
| `set_paragraph_style` | Change paragraph style (e.g. "Heading 1") | Yes | core | `style`, `paragraph_index?`, `locator?` |
| `delete_paragraph` | Delete a paragraph | Yes | core | `paragraph_index?`, `locator?` |
| `duplicate_paragraph` | Duplicate paragraph with its style | Yes | extended | `paragraph_index?`, `locator?`, `count?` |
| `clone_heading_block` | Clone heading + all sub-content after original | Yes | extended | `paragraph_index?`, `locator?` |
| `insert_paragraphs_batch` | Insert multiple paragraphs in one call | Yes | core | `paragraphs` (array of `{text, style?}`), `paragraph_index?`, `locator?`, `position?` |

### Search & Replace

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `search_in_document` | Search with paragraph context and heading enrichment | No | core | `pattern`, `regex?`, `case_sensitive?`, `max_results?`, `context_paragraphs?` |
| `replace_in_document` | Find and replace (regex, case-sensitive, all/first) | Yes | core | `search`, `replace`, `regex?`, `case_sensitive?`, `replace_all?` |

### Styles *(all doc types)*

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `list_styles` | List available styles in a given family | No | core | `family?` |
| `get_style_info` | Get detailed style properties | No | core | `style_name`, `family?` |
| `set_style_properties` | Set or create style properties (font, size, margins, etc.) | Yes | core | `style_name`, `family?`, `create?`, `parent_style?`, `properties` |

### Tables

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `list_tables` | List all text tables with names and dimensions | No | core | — |
| `read_table` | Read all cell contents from a named table | No | core | `table_name` |
| `write_table_cell` | Write value to a table cell (e.g. "A1") | Yes | core | `table_name`, `cell`, `value` |
| `create_table` | Create table at paragraph position | Yes | core | `rows`, `cols`, `paragraph_index?`, `locator?`, `position?` |
| `delete_table` | Delete a named table | Yes | extended | `table_name` |
| `set_table_properties` | Set table width, alignment, column widths, repeat header, background | Yes | extended | `table_name`, `width_mm?`, `equal_columns?`, `column_widths?`, `alignment?`, `repeat_header?`, `header_rows?`, `bg_color?` |
| `add_table_rows` | Insert rows into a table | Yes | extended | `table_name`, `count?`, `at_index?` |
| `add_table_columns` | Insert columns into a table | Yes | extended | `table_name`, `count?`, `at_index?` |
| `delete_table_rows` | Delete rows from a table | Yes | extended | `table_name`, `at_index`, `count?` |
| `delete_table_columns` | Delete columns from a table | Yes | extended | `table_name`, `at_index`, `count?` |
| `write_table_row` | Write entire row of values efficiently | Yes | extended | `table_name`, `row`, `values` |

### Comments

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `list_comments` | List all comments/annotations | No | core | `author_filter?` |
| `add_comment` | Add comment anchored to paragraph | Yes | core | `content`, `search_text?`, `locator?`, `paragraph_index?`, `author?` |
| `delete_comment` | Delete comments by name or author | Yes | extended | `comment_name?`, `author?` |
| `resolve_comment` | Resolve comment with optional resolution text | Yes | extended | `comment_name`, `resolution?`, `author?` |

### Track Changes

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `set_track_changes` | Enable or disable change recording | Yes | extended | `enabled` |
| `get_tracked_changes` | List all tracked changes (redlines) | No | extended | — |
| `accept_all_changes` | Accept all tracked changes | Yes | extended | — |
| `reject_all_changes` | Reject all tracked changes | Yes | extended | — |

### Text Frames

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `list_text_frames` | List all text frames | No | extended | — |
| `get_text_frame_info` | Detailed text frame properties | No | extended | `frame_name` |
| `set_text_frame_properties` | Resize/reposition text frame | Yes | extended | `frame_name`, `width_mm?`, `height_mm?`, `anchor_type?`, `hori_orient?`, `vert_orient?` |

### Stats

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `get_document_stats` | Character/word/paragraph/page/heading counts | No | core | — |

---

## Module: `writer_nav` (13 tools)

Writer navigation — heading tree, bookmarks, proximity, sections, and fields.

### Tree & Navigation

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `get_document_tree` | Document heading tree with bookmarks and content previews | No | core | `content_strategy?`, `depth?` |
| `get_heading_children` | Drill into heading's body and sub-headings | No | core | `locator?`, `heading_para_index?`, `heading_bookmark?`, `content_strategy?`, `depth?` |
| `navigate_heading` | Navigate from locator to related heading (next/previous/parent/first_child/next_sibling/previous_sibling) | No | core | `locator`, `direction` |
| `get_surroundings` | Discover objects within a radius of paragraphs around a locator | No | extended | `locator`, `radius?`, `include?` |

### Sections & Fields

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `list_sections` | List named sections in the document | No | extended | — |
| `read_section` | Read text content of a named section | No | extended | `section_name` |
| `goto_page` | Navigate view cursor to a page | No | extended | `page` |
| `get_page_objects` | Get images/tables/frames on a page | No | extended | `page?`, `locator?`, `paragraph_index?` |
| `refresh_indexes` | Refresh TOC and other indexes | Yes | extended | — |
| `resolve_bookmark` | Resolve bookmark to paragraph index and heading | No | extended | `bookmark_name` |
| `resolve_locator` | Resolve any locator to paragraph position | No | core | `locator` |
| `update_fields` | Refresh all text fields (dates, page numbers, etc.) | Yes | extended | — |

### Bookmarks

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `list_bookmarks` | List all bookmarks with anchor text preview | No | extended | — |

---

## Module: `calc` (30 tools)

Calc spreadsheet tools — cells, sheets, charts, conditional formatting, comments.

### Sheets

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `list_sheets` | List all sheet names | No | core | — |
| `switch_sheet` | Switch to a sheet (make active) | Yes | core | `sheet_name` |
| `create_sheet` | Create a new sheet | Yes | core | `sheet_name`, `position?` |
| `get_sheet_summary` | Summary of active/specified sheet (size, headers, etc.) | No | core | `sheet_name?` |

### Cells

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `read_cell_range` | Read cell range values (supports non-contiguous ranges) | No | core | `range_name` |
| `write_formula_range` | Write formulas/values to cell range(s) | Yes | core | `range_name`, `formula_or_values` |
| `set_cell_style` | Apply formatting (bold, colors, alignment, borders, number format) | Yes | extended | `range_name`, `bold?`, `italic?`, `font_size?`, `bg_color?`, `font_color?`, `h_align?`, `v_align?`, `wrap_text?`, `border_color?`, `number_format?` |
| `merge_cells` | Merge cell range(s) | Yes | extended | `range_name`, `center?` |
| `clear_range` | Clear cell contents | Yes | extended | `range_name` |
| `sort_range` | Sort range by column | Yes | extended | `range_name`, `sort_column?`, `ascending?`, `has_header?` |
| `import_csv_from_string` | Import CSV data into sheet | Yes | extended | `csv_data`, `target_cell?` |
| `write_cell_range` | Write 2D array of values starting at a cell | Yes | extended | `start_cell`, `values`, `sheet_name?` |
| `delete_structure` | Delete rows or columns | Yes | extended | `structure_type`, `start`, `count?` |

### Search & Formulas

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `search_in_spreadsheet` | Search for text in spreadsheet | No | core | `pattern`, `regex?`, `case_sensitive?`, `max_results?`, `sheet_name?`, `all_sheets?` |
| `replace_in_spreadsheet` | Find and replace in spreadsheet | Yes | core | `search`, `replace`, `regex?`, `case_sensitive?`, `sheet_name?`, `all_sheets?` |
| `detect_and_explain_errors` | Detect and explain formula errors | No | extended | `range_name?` |

### Navigation

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `list_named_ranges` | List all named ranges | No | extended | — |
| `get_sheet_overview` | Overview of a sheet (used area, data regions, charts) | No | extended | `sheet_name?` |

### Charts

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `create_chart` | Create chart from data range | Yes | extended | `data_range`, `chart_type`, `title?`, `position?`, `has_header?` |
| `list_charts` | List all charts on a sheet | No | extended | `sheet_name?` |
| `get_chart_info` | Get chart details (type, title, data ranges) | No | extended | `chart_name`, `sheet_name?` |
| `edit_chart` | Edit chart properties (title, subtitle, legend) | Yes | extended | `chart_name`, `sheet_name?`, `title?`, `subtitle?`, `has_legend?` |
| `delete_chart` | Delete a named chart | Yes | extended | `chart_name`, `sheet_name?` |

### Conditional Formatting

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `list_conditional_formats` | List conditional formatting rules | No | extended | `cell_range?`, `sheet_name?` |
| `add_conditional_format` | Add a conditional format rule | Yes | extended | `cell_range`, `operator`, `formula1`, `formula2?`, `style_name`, `sheet_name?` |
| `remove_conditional_format` | Remove conditional format by index | Yes | extended | `cell_range`, `rule_index`, `sheet_name?` |
| `clear_conditional_formats` | Clear all conditional formats from range | Yes | extended | `cell_range`, `sheet_name?` |

### Comments

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `list_cell_comments` | List cell comments/annotations | No | extended | `sheet_name?` |
| `add_cell_comment` | Add comment to a cell | Yes | extended | `cell`, `text`, `sheet_name?` |
| `delete_cell_comment` | Delete comment from a cell | Yes | extended | `cell`, `sheet_name?` |

---

## Module: `draw` (21 tools)

Draw and Impress tools — shapes, slides, masters, notes, placeholders, transitions.

### Pages/Slides

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `list_pages` | List all pages/slides | No | core | — |
| `add_slide` | Insert new slide at index | Yes | core | `index?` |
| `delete_slide` | Delete slide at index | Yes | core | `index` |
| `read_slide_text` | Read all text + speaker notes from slide | No | core | `page_index?` |
| `get_presentation_info` | Slide count, dimensions, master names, is_impress | No | core | — |

### Shapes *(all doc types with drawing layer)*

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `get_draw_summary` | Summary of shapes on a page | No | core | `draw?`, `calc?` |
| `create_shape` | Create rectangle/ellipse/text/line shape | Yes | core | `shape_type`, `x`, `y`, `width`, `height`, `text?`, `bg_color?`, `draw?`, `calc?` |
| `edit_shape` | Modify shape properties | Yes | extended | `shape_index`, `x?`, `y?`, `width?`, `height?`, `text?`, `bg_color?`, `draw?`, `calc?` |
| `delete_shape` | Delete shape by index | Yes | extended | `shape_index`, `draw?`, `calc?` |

### Masters

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `list_master_slides` | List all master slides | No | extended | — |
| `get_slide_master` | Get assigned master slide for a slide | No | extended | `page_index?` |
| `set_slide_master` | Assign master slide to a slide | Yes | extended | `master_name`, `page_index?` |

### Speaker Notes *(impress only)*

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `get_speaker_notes` | Read speaker notes from slide | No | extended | `page_index?` |
| `set_speaker_notes` | Set/append speaker notes | Yes | extended | `text`, `page_index?`, `append?` |

### Placeholders *(draw, impress)*

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `list_placeholders` | List text placeholders on a slide | No | extended | `page_index?` |
| `get_placeholder_text` | Get text from placeholder (by role or shape_index) | No | extended | `role?`, `shape_index?`, `page_index?` |
| `set_placeholder_text` | Set text on placeholder | Yes | extended | `text`, `role?`, `shape_index?`, `page_index?` |

### Transitions & Layouts *(impress only)*

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `get_slide_transition` | Get transition effect, speed, duration | No | extended | `page_index?` |
| `set_slide_transition` | Set transition effect, speed, advance mode | Yes | extended | `page_index?`, `effect?`, `speed?`, `duration?`, `transition_duration?`, `advance?` |
| `get_slide_layout` | Get the layout type of a slide | No | extended | `page_index?` |
| `set_slide_layout` | Set the layout of a slide | Yes | extended | `layout`, `page_index?` |

---

## Module: `batch` (1 tool)

Execute multiple tool calls in a single request.

| Tool | Description | Mutation | Tier | Params |
|------|-------------|----------|------|--------|
| `execute_batch` | Execute multiple tool calls sequentially with variable chaining (`$last`, `$step.N`) | Yes | core | `operations` (array of `{tool, args?}`), `stop_on_error?`, `follow?` |

---

## Tool Count by Module

| Module | Tools |
|--------|-------|
| `writer` | 44 |
| `calc` | 30 |
| `draw` | 21 |
| `doc` | 19 |
| `writer_nav` | 13 |
| `batch` | 1 |
| **Total** | **128** |