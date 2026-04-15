# LibreMCP — Tool Reference

Complete reference for all 141 tools exposed via the MCP server.

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
- **Tier** — `core` tools are always exposed; `extended` tools are on demand.

---

## Module: `core` (2 tools)

System-level tools for background job management.

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `list_jobs` | List recent background jobs with their status | No | `limit?` |
| `get_job` | Get the status and result of a background job by ID | No | `job_id` |

---

## Module: `doc` (19 tools)

Document-agnostic tools that work on all document types.

### File Operations

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `open_document` | Open a document file in LibreOffice | No | `file_path` |
| `create_document` | Create a new empty document (writer/calc/impress/draw) | No | `doc_type`, `path?`, `content?` |
| `save_document` | Save current document (first save needs path) | Yes | `path?` |
| `save_document_as` | Save document to a new path | No | `target_path` |
| `export_pdf` | Export document to PDF | No | `path` |
| `close_document` | Close current document | Yes | — |
| `list_open_documents` | List all open documents | No | — |
| `get_recent_documents` | Get recently opened documents from LO history | No | `max_count?` |

### Document Info & Properties

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `get_document_info` | Document metadata (title, type, modified, author, etc.) | No | — |
| `set_document_properties` | Set document metadata (title, subject, author, description, keywords) | Yes | `title?`, `subject?`, `author?`, `description?`, `keywords?` |

### Undo/Redo

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `undo` | Undo last action(s) | Yes | `steps?` |
| `redo` | Redo last undone action(s) | Yes | `steps?` |

### Hyperlinks *(writer, calc)*

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `list_hyperlinks` | List all hyperlinks | No | `calc?` |
| `insert_hyperlink` | Insert a hyperlink | Yes | `url`, `text?`, `writer?`, `calc?` |
| `remove_hyperlink` | Remove hyperlink by index (preserves text) | Yes | `index`, `calc?` |
| `edit_hyperlink` | Edit existing hyperlink URL/text | Yes | `index`, `url?`, `text?`, `calc?` |

### Diagnostics *(writer)*

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `document_health_check` | Structural health checks (empty headings, level jumps, etc.) | No | — |
| `set_document_protection` | Set/remove section protection | Yes | `enabled`, `password?` |

### Images *(all doc types)*

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `list_images` | List all images/graphic objects | No | `draw?`, `calc?` |
| `get_image_info` | Get detailed image info (dimensions, anchor, etc.) | No | `image_name?`, `shape_index?`, `draw?`, `calc?` |
| `set_image_properties` | Resize/reposition/crop/alt-text a Writer image | Yes | `image_name`, `width_mm?`, `height_mm?`, `title?`, `description?`, `anchor_type?`, `hori_orient?`, `vert_orient?` |
| `download_image` | Download image from URL to local cache | No | `url`, `verify_ssl?`, `force?` |
| `insert_image` | Insert image from path/URL | Yes | `image_path`, `width_mm?`, `height_mm?`, `max_height_mm?`, `caption?`, `title?`, `description?`, `writer?`, `draw?`, `calc?` |
| `delete_image` | Delete image from document | Yes | `image_name?`, `shape_index?`, `draw?`, `calc?` |
| `replace_image` | Replace Writer image source keeping position | Yes | `image_name`, `new_image_path`, `width_mm?`, `height_mm?` |

### Print

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `print_document` | Print document to default/named printer | No | `printer?`, `pages?`, `copies?` |

---

## Module: `writer` (51 tools)

Writer document tools — content editing, styles, tables, comments, track changes, images, search.

### Content

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `get_document_content` | Get document (or selection/range) content | No | `scope?`, `max_chars?`, `start?`, `end?` |
| `apply_document_content` | Insert or replace content (target: beginning/end/selection/search/full/range) | Yes | `content`, `target`, `start?`, `end?`, `search?`, `all_matches?`, `case_sensitive?` |
| `find_text` | Find text, returns `{start, end, text}` per match | No | `search`, `start?`, `limit?`, `case_sensitive?` |
| `read_paragraphs` | Read a range of paragraphs by index or locator | No | `start_index?`, `locator?`, `count?` |
| `insert_at_paragraph` | Insert text at paragraph index or locator | Yes | `text`, `paragraph_index?`, `locator?`, `style?`, `position?` |
| `set_paragraph_text` | Replace entire paragraph text (preserves style) | Yes | `text`, `paragraph_index?`, `locator?` |
| `set_paragraph_style` | Change paragraph style (e.g. "Heading 1") | Yes | `style`, `paragraph_index?`, `locator?` |
| `delete_paragraph` | Delete a paragraph | Yes | `paragraph_index?`, `locator?` |
| `duplicate_paragraph` | Duplicate paragraph with its style | Yes | `paragraph_index?`, `locator?`, `count?` |
| `clone_heading_block` | Clone heading + all sub-content after original | Yes | `paragraph_index?`, `locator?` |
| `insert_paragraphs_batch` | Insert multiple paragraphs in one call | Yes | `paragraphs` (array of `{text, style?}`), `paragraph_index?`, `locator?`, `position?` |

### Search & Replace

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `search_in_document` | Search with paragraph context and heading enrichment | No | `pattern`, `regex?`, `case_sensitive?`, `max_results?`, `context_paragraphs?` |
| `replace_in_document` | Find and replace (regex, case-sensitive, all/first) | Yes | `search`, `replace`, `regex?`, `case_sensitive?`, `replace_all?` |

### Styles *(all doc types)*

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `list_styles` | List available styles in a given family | No | `family?` |
| `get_style_info` | Get detailed style properties | No | `style_name`, `family?` |

### Tables

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `list_tables` | List all text tables with names and dimensions | No | — |
| `read_table` | Read all cell contents from a named table | No | `table_name` |
| `write_table_cell` | Write value to a table cell (e.g. "A1") | Yes | `table_name`, `cell`, `value` |
| `create_table` | Create table at paragraph position | Yes | `rows`, `cols`, `paragraph_index?`, `locator?`, `position?` |
| `delete_table` | Delete a named table | Yes | `table_name` |
| `set_table_properties` | Set table width, alignment, column widths, repeat header, background | Yes | `table_name`, `width_mm?`, `equal_columns?`, `column_widths?`, `alignment?`, `repeat_header?`, `header_rows?`, `bg_color?` |
| `add_table_rows` | Insert rows into a table | Yes | `table_name`, `count?`, `at_index?` |
| `add_table_columns` | Insert columns into a table | Yes | `table_name`, `count?`, `at_index?` |
| `delete_table_rows` | Delete rows from a table | Yes | `table_name`, `at_index`, `count?` |
| `delete_table_columns` | Delete columns from a table | Yes | `table_name`, `at_index`, `count?` |
| `write_table_row` | Write entire row of values efficiently | Yes | `table_name`, `row`, `values` |

### Comments & Workflow

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `list_comments` | List all comments/annotations | No | `author_filter?` |
| `add_comment` | Add comment anchored to paragraph | Yes | `content`, `search_text?`, `locator?`, `paragraph_index?`, `author?` |
| `delete_comment` | Delete comments by name or author | Yes | `comment_name?`, `author?` |
| `resolve_comment` | Resolve comment with optional resolution text | Yes | `comment_name`, `resolution?`, `author?` |
| `scan_tasks` | Scan comments for actionable task prefixes (TODO-AI, FIX, etc.) | No | `unresolved_only?`, `prefix_filter?` |
| `get_workflow_status` | Read MCP-WORKFLOW dashboard comment | No | — |
| `set_workflow_status` | Create/update MCP-WORKFLOW dashboard comment | Yes | `content` |
| `check_stop_conditions` | Check for STOP/CANCEL signals in comments | No | — |

### Track Changes

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `set_track_changes` | Enable or disable change recording | Yes | `enabled` |
| `get_tracked_changes` | List all tracked changes (redlines) | No | — |
| `accept_all_changes` | Accept all tracked changes | Yes | — |
| `reject_all_changes` | Reject all tracked changes | Yes | — |

### Text Frames

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `list_text_frames` | List all text frames | No | — |
| `get_text_frame_info` | Detailed text frame properties | No | `frame_name` |
| `set_text_frame_properties` | Resize/reposition text frame | Yes | `frame_name`, `width_mm?`, `height_mm?`, `anchor_type?`, `hori_orient?`, `vert_orient?` |

### Outline & Stats

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `get_document_outline` | Heading hierarchy (deprecated; use `get_document_tree`) | No | `max_depth?` |
| `get_heading_content` | Content under heading by path (deprecated; use `get_heading_children`) | No | `heading_path`, `max_paragraphs?` |
| `get_document_stats` | Character/word/paragraph/page/heading counts | No | — |

---

## Module: `writer_nav` (17 tools)

Writer navigation — heading tree, bookmarks, proximity, sections, and AI summaries.

### Tree & Navigation

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `get_document_tree` | Document heading tree with bookmarks and content previews | No | `content_strategy?`, `depth?` |
| `get_heading_children` | Drill into heading's body and sub-headings | No | `locator?`, `heading_para_index?`, `heading_bookmark?`, `content_strategy?`, `depth?` |
| `navigate_heading` | Navigate from locator to related heading (next/previous/parent/first_child/next_sibling/previous_sibling) | No | `locator`, `direction` |
| `get_surroundings` | Discover objects within a radius of paragraphs around a locator | No | `locator`, `radius?`, `include?` |

### Sections & Fields

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `list_sections` | List named sections in the document | No | — |
| `read_section` | Read text content of a named section | No | `section_name` |
| `goto_page` | Navigate view cursor to a page | No | `page` |
| `get_page_objects` | Get images/tables/frames on a page | No | `page?`, `locator?`, `paragraph_index?` |
| `refresh_indexes` | Refresh TOC and other indexes | Yes | — |
| `resolve_bookmark` | Resolve bookmark to paragraph index and heading | No | `bookmark_name` |
| `resolve_locator` | Resolve any locator to paragraph position | No | `locator` |
| `update_fields` | Refresh all text fields (dates, page numbers, etc.) | Yes | — |

### Bookmarks

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `list_bookmarks` | List all bookmarks with anchor text preview | No | — |
| `cleanup_bookmarks` | Remove stale `_mcp_*` bookmarks | Yes | — |

### AI Annotations

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `add_ai_summary` | Add MCP-AI summary comment at heading/paragraph | Yes | `summary`, `locator?`, `para_index?` |
| `get_ai_summaries` | List all MCP-AI summary annotations | No | — |
| `remove_ai_summary` | Remove MCP-AI summary at paragraph | Yes | `locator?`, `para_index?` |

---

## Module: `writer_index` (2 tools)

Full-text search with Snowball stemming.

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `search_fulltext` | Full-text search with boolean queries (AND, OR, NOT, NEAR/N) | No | `query`, `max_results?`, `context_paragraphs?`, `around_page?`, `page_radius?`, `include_pages?` |
| `get_index_stats` | Search index stats (paragraph count, stems, language) | No | — |

---

## Module: `calc` (30 tools)

Calc spreadsheet tools — cells, sheets, charts, conditional formatting, comments.

### Sheets

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `list_sheets` | List all sheet names | No | — |
| `switch_sheet` | Switch to a sheet (make active) | Yes | `sheet_name` |
| `create_sheet` | Create a new sheet | Yes | `sheet_name`, `position?` |
| `get_sheet_summary` | Summary of active/specified sheet (size, headers, etc.) | No | `sheet_name?` |

### Cells

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `read_cell_range` | Read cell range values (supports non-contiguous ranges) | No | `range_name` |
| `write_formula_range` | Write formulas/values to cell range(s) | Yes | `range_name`, `formula_or_values` |
| `set_cell_style` | Apply formatting (bold, colors, alignment, borders, number format) | Yes | `range_name`, `bold?`, `italic?`, `font_size?`, `bg_color?`, `font_color?`, `h_align?`, `v_align?`, `wrap_text?`, `border_color?`, `number_format?` |
| `merge_cells` | Merge cell range(s) | Yes | `range_name`, `center?` |
| `clear_range` | Clear cell contents | Yes | `range_name` |
| `sort_range` | Sort range by column | Yes | `range_name`, `sort_column?`, `ascending?`, `has_header?` |
| `import_csv_from_string` | Import CSV data into sheet | Yes | `csv_data`, `target_cell?` |
| `write_cell_range` | Write 2D array of values starting at a cell | Yes | `start_cell`, `values`, `sheet_name?` |
| `delete_structure` | Delete rows or columns | Yes | `structure_type`, `start`, `count?` |

### Search & Formulas

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `search_in_spreadsheet` | Search for text in spreadsheet | No | `pattern`, `regex?`, `case_sensitive?`, `max_results?`, `sheet_name?`, `all_sheets?` |
| `replace_in_spreadsheet` | Find and replace in spreadsheet | Yes | `search`, `replace`, `regex?`, `case_sensitive?`, `sheet_name?`, `all_sheets?` |
| `detect_and_explain_errors` | Detect and explain formula errors | No | `range_name?` |

### Navigation

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `list_named_ranges` | List all named ranges | No | — |
| `get_sheet_overview` | Overview of a sheet (used area, data regions, charts) | No | `sheet_name?` |

### Charts

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `create_chart` | Create chart from data range | Yes | `data_range`, `chart_type`, `title?`, `position?`, `has_header?` |
| `list_charts` | List all charts on a sheet | No | `sheet_name?` |
| `get_chart_info` | Get chart details (type, title, data ranges) | No | `chart_name`, `sheet_name?` |
| `edit_chart` | Edit chart properties (title, subtitle, legend) | Yes | `chart_name`, `sheet_name?`, `title?`, `subtitle?`, `has_legend?` |
| `delete_chart` | Delete a named chart | Yes | `chart_name`, `sheet_name?` |

### Conditional Formatting

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `list_conditional_formats` | List conditional formatting rules | No | `cell_range?`, `sheet_name?` |
| `add_conditional_format` | Add a conditional format rule | Yes | `cell_range`, `operator`, `formula1`, `formula2?`, `style_name`, `sheet_name?` |
| `remove_conditional_format` | Remove conditional format by index | Yes | `cell_range`, `rule_index`, `sheet_name?` |
| `clear_conditional_formats` | Clear all conditional formats from range | Yes | `cell_range`, `sheet_name?` |

### Comments

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `list_cell_comments` | List cell comments/annotations | No | `sheet_name?` |
| `add_cell_comment` | Add comment to a cell | Yes | `cell`, `text`, `sheet_name?` |
| `delete_cell_comment` | Delete comment from a cell | Yes | `cell`, `sheet_name?` |

---

## Module: `draw` (21 tools)

Draw and Impress tools — shapes, slides, masters, notes, placeholders, transitions.

### Pages/Slides

| Tool | Description | Mutation | Doc Types | Params |
|------|-------------|----------|-----------|--------|
| `list_pages` | List all pages/slides | No | draw, impress | — |
| `add_slide` | Insert new slide at index | Yes | draw, impress | `index?` |
| `delete_slide` | Delete slide at index | Yes | draw, impress | `index` |
| `read_slide_text` | Read all text + speaker notes from slide | No | draw, impress | `page_index?` |
| `get_presentation_info` | Slide count, dimensions, master names, is_impress | No | draw, impress | — |

### Shapes *(all doc types with drawing layer)*

| Tool | Description | Mutation | Doc Types | Params |
|------|-------------|----------|-----------|--------|
| `get_draw_summary` | Summary of shapes on a page | No | all | `draw?`, `calc?` |
| `create_shape` | Create rectangle/ellipse/text/line shape | Yes | all | `shape_type`, `x`, `y`, `width`, `height`, `text?`, `bg_color?`, `draw?`, `calc?` |
| `edit_shape` | Modify shape properties | Yes | all | `shape_index`, `x?`, `y?`, `width?`, `height?`, `text?`, `bg_color?`, `draw?`, `calc?` |
| `delete_shape` | Delete shape by index | Yes | all | `shape_index`, `draw?`, `calc?` |

### Masters

| Tool | Description | Mutation | Doc Types | Params |
|------|-------------|----------|-----------|--------|
| `list_master_slides` | List all master slides | No | draw, impress | — |
| `get_slide_master` | Get assigned master slide for a slide | No | draw, impress | `page_index?` |
| `set_slide_master` | Assign master slide to a slide | Yes | draw, impress | `master_name`, `page_index?` |

### Speaker Notes *(impress only)*

| Tool | Description | Mutation | Doc Types | Params |
|------|-------------|----------|-----------|--------|
| `get_speaker_notes` | Read speaker notes from slide | No | impress | `page_index?` |
| `set_speaker_notes` | Set/append speaker notes | Yes | impress | `text`, `page_index?`, `append?` |

### Placeholders *(draw, impress)*

| Tool | Description | Mutation | Doc Types | Params |
|------|-------------|----------|-----------|--------|
| `list_placeholders` | List text placeholders on a slide | No | draw, impress | `page_index?` |
| `get_placeholder_text` | Get text from placeholder (by role or shape_index) | No | draw, impress | `role?`, `shape_index?`, `page_index?` |
| `set_placeholder_text` | Set text on placeholder | Yes | draw, impress | `text`, `role?`, `shape_index?`, `page_index?` |

### Transitions & Layouts *(impress only)*

| Tool | Description | Mutation | Doc Types | Params |
|------|-------------|----------|-----------|--------|
| `get_slide_transition` | Get transition effect, speed, duration | No | impress | `page_index?` |
| `set_slide_transition` | Set transition effect, speed, advance mode | Yes | impress | `page_index?`, `effect?`, `speed?`, `duration?`, `transition_duration?`, `advance?` |
| `get_slide_layout` | Get the layout type of a slide | No | impress | `page_index?` |
| `set_slide_layout` | Set the layout of a slide | Yes | impress | `layout`, `page_index?` |

---

## Module: `batch` (1 tool)

Execute multiple tool calls in a single request.

| Tool | Description | Mutation | Params |
|------|-------------|----------|--------|
| `execute_batch` | Execute multiple tool calls sequentially with variable chaining (`$last`, `$step.N`) | Yes | `operations` (array of `{tool, args?}`), `stop_on_error?`, `follow?`, `check_conditions?`, `revision_comment?` |

---

## Tool Count by Module

| Module | Tools |
|--------|-------|
| `writer` | 51 |
| `calc` | 30 |
| `draw` | 21 |
| `doc` | 19 |
| `writer_nav` | 17 |
| `writer_index` | 2 |
| `core` | 2 |
| `batch` | 1 |
| **Total** | **143** |