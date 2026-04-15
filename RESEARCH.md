# LibreMCP — Tool Redundancy & Validation Research

Generated: 2026-04-14

## Scope

104 tools across 8 modules, 8 services, ~1% module-level test coverage. This document captures findings from Phases 1A (redundancy), 1B (structural audit), and 2A (stub infrastructure), and defines the remaining phases.

---

## Phase 1A: Redundancy Analysis — Findings

### Group 1: Writer Search — KEEP ALL THREE

| Tool | Engine | Returns | Use Case |
|------|---------|---------|----------|
| `find_text` | UNO SearchDescriptor | Character offsets `{start, end, text}` | Find-then-edit workflow (offsets plug into `apply_document_content`) |
| `search_in_document` | Python `str.find`/`re` | Paragraph index + context + heading | Contextual browsing/reading with regex |
| `search_fulltext` | Snowball inverted index + BM25 | Paragraph index + score + stems | Semantic/boolean search (AND/OR/NOT/NEAR) |

These serve genuinely different use cases. `find_text` is the only one returning character offsets for editing. `search_in_document` adds regex and paragraph context. `search_fulltext` adds stemming and boolean queries.

**Action**: Suggest rename `find_text` → `find_text_ranges` to emphasize its editing purpose.

### Group 2: Writer Replace — KEEP BOTH, ADD CROSS-REFERENCES

| Aspect | `apply_document_content(target=search)` | `replace_in_document` |
|--------|----------------------------------------|----------------------|
| Format preservation | Yes (character-by-character) | No (setString) |
| Regex support | No | Yes |
| HTML/Markdown content | Yes | No |
| Bulk efficiency | Loops findFirst/findNext | Single `replaceAll()` |

They serve different workflows: surgical format-preserving edits vs fast bulk regex replace.

**Action**: Add cross-references in descriptions. Future: consider adding `format_preserve` param to `replace_in_document` to fully consolidate.

### Group 3: Heading Tree / Outline — DEPRECATE `get_document_outline`

| Aspect | `get_document_outline` | `get_document_tree` |
|--------|----------------------|---------------------|
| Service | `document.build_heading_tree()` (core) | `tree_svc.get_document_tree()` (writer_nav) |
| Bookmark creation | No | Yes |
| Content preview | No | Yes (4 strategies) |
| Para index | No | Yes |
| Page info | No | Yes |

`get_document_tree(content_strategy="heading_only", depth=0)` is a superset. The only advantage of `get_document_outline` is not needing `writer_nav`, but `writer_nav` ships with LibreMCP.

**Action**: Mark deprecated. Point users to `get_document_tree`. Remove after transition period.

### Group 4: Heading Content — DEPRECATE `get_heading_content`

| Aspect | `get_heading_content` | `get_heading_children` |
|--------|----------------------|----------------------|
| Addressing | Path "1.2" (numeric) | Bookmark, heading_text, para_index, locator |
| Body format | Plain strings | Structured objects with para_index |
| Content strategy | None (always full) | 4 strategies |

`get_heading_children(locator="heading:1.2", content_strategy="full")` is a superset.

**Action**: Mark deprecated. Remove after transition period.

### Group 5: Paragraph Reading — KEEP BOTH

| Aspect | `read_paragraphs` | `get_document_content(scope=range)` |
|--------|-------------------|--------------------------------------|
| Addressing | Paragraph index + locator | Character offset range |
| Format | Plain text per-paragraph | Rendered HTML/Markdown (single string) |
| Locator support | Yes | No |

Different use cases: structural indexing vs rendered content export.

### Group 6: Comments — KEEP SEPARATE

Writer and Calc comments use completely different UNO APIs (`text.textfield.Annotation` vs `sheet.getAnnotations()` + `CellAddress`). Writer comments have resolution, threading, and workflow features. Unification would add complexity without reducing code.

### Group 7: Style Tools — KEEP BOTH

`list_styles`/`get_style_info` inspect **named styles** (read-only). `set_cell_style` applies **direct formatting** (not style-based). They operate at different levels.

### Group 8: Table Operations — KEEP ALL

Writer's 11 table tools are all reasonably distinct. `write_table_cell` (single cell) vs `write_table_row` (full row) serve different granularities. Calc uses cell ranges, not text tables — no cross-module consolidation possible.

### Group 9: Document Stats vs Info — KEEP BOTH

Zero overlap. `get_document_stats` returns quantitative metrics (words, chars, pages). `get_document_info` returns qualitative metadata (title, author, dates). Not a single shared field.

### Summary of Redundancy Actions

| Tool | Action | Replacement |
|------|--------|-------------|
| `get_document_outline` | **DEPRECATE** | `get_document_tree(content_strategy="heading_only", depth=0)` |
| `get_heading_content` | **DEPRECATE** | `get_heading_children(locator="heading:N.N", content_strategy="full")` |
| `find_text` | **RENAME** | `find_text_ranges` (emphasize editing purpose) |
| Everything else | **KEEP** | Distinct use cases confirmed |

**Net result**: 2 tool removals, 1 rename, 0 merges. The 104-tool surface is well-differentiated after the refactor.

---

## Phase 1B: Structural Audit — Findings

### Bug: `DocumentService.set_events()` Never Called

**Status**: CONFIRMED BUG

**Root cause**: `main.py` wires `config_svc.set_events(events_svc)` but never calls `doc_svc.set_events(events_svc)`. `DocumentService._events` stays `None`.

**Impact**: `invalidate_cache()` gates `self._events.emit("document:cache_invalidated")` on `if self._events:` — event never fires. All downstream service caches (tree, proximity, index, bookmarks) become stale after any document mutation.

**User-visible**: After edits, `search_fulltext`, `get_document_tree`, `navigate_heading`, `get_surroundings`, and bookmark lookups may return outdated data until document reload.

**Fix** (one line in `plugin/main.py` after config service wiring):
```python
doc_svc = _services.get("document")
if doc_svc and events_svc:
    doc_svc.set_events(events_svc)
```

**Planned fix**: Phase 2C (service tests) will include and verify this fix.

### FormatService — VERIFIED UNUSED

No tool or service calls `FormatService`. The `writer/format_support.py` module implements all format logic directly. The `format` dependency in `writer/module.yaml` is vestigial.

**Action**: Remove `FormatService` class, its registration in `core/__init__.py`, and `format` from `core/module.yaml` `provides_services` and `writer/module.yaml` `requires`.

### DocumentService Dead Code (~300 lines)

| Method | Lines | Reason |
|--------|-------|--------|
| `get_document_context_for_chat` | 237+ | Never called from anywhere |
| `_writer/calc/draw_context_for_chat` | Sub-methods | Only called by dead parent |
| `_inject_markers` | ~30 | Only called by dead parent |
| `get_full_text` | ~15 | Never called; `format_support.document_to_content()` is used instead |
| `build_heading_tree` + `_nest_headings` | ~50 | Duplicates TreeService; only 2 callers (deprecated tools) |

**Additional issue**: `get_document_context_for_chat` imports from `plugin.modules.calc.*` and `plugin.modules.draw.*` — undeclared cross-module dependencies from core to downstream modules.

**Action**: Remove dead methods after Phase 2C tests verify the fix. Migrate `build_heading_tree` callers to use `writer_tree` service (already covered by deprecation of `get_document_outline`).

### Other Dead Code

| Location | Issue |
|----------|-------|
| `PageMap` class in `document.py` | `observe()`, `estimate_page()`, `estimate_para()` never called |
| `_find_heading_by_text()` in `tree.py` | Wrapper that just calls `_find_heading_by_text_enriched()`, never called externally |
| `core/__init__.py` lines 193-242 | Commented-out idle timer, statusbar, cursor tracker code |
| `core/__init__.py` line 76 | `_setup_bundled_sqlite3()` is a no-op stub |
| `writer/tools/_insert_frame_notes.py` | 24 lines of reference comments, not code |
| `batch/batch.py` line 247 | `check_conditions` parameter references non-existent `check_stop_conditions` tool — unreachable |

### Undeclared Cross-Module Dependencies

| Consumer | Dependency | Declared? | Mechanism |
|----------|-----------|-----------|-----------|
| `core/document.py` → `writer_nav` | `writer_tree.resolve_writer_locator()` | No | Lazy import via `get_services()` |
| `writer/tools/content.py` → `writer_nav` | `writer_bookmarks`, `writer_tree` | No | `ctx.services.get("writer_tree")` |
| `writer_index` → `writer_nav` | `writer_bookmarks` | No | Constructor parameter (declared `writer_tree` but not `writer_bookmarks`) |

**Action**: Add `writer_bookmarks` to `writer_index` requires. Document the `core` → `writer_nav` lazy dependency as intentional (graceful degradation for non-Writer docs).

### Thin Wrappers (7 tools)

These tools just call a single service method:
`GetDocumentTree`, `GetHeadingChildren`, `GetAiSummaries`, `CleanupBookmarks`, `NavigateHeading`, `GetSurroundings`, `GetIndexStats`, `Undo`, `Redo`, `ListJobs`, `GetJob`, `GetDocumentOutline`

These are candidates for a declarative/auto-generation approach in a future iteration. Not urgent.

---

## Phase 2A: UNO Stub Library — COMPLETE

### Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `tests/stubs/__init__.py` | 0 | Package marker |
| `tests/stubs/uno_stubs.py` | 270 | Core UNO infrastructure: PropertyHolder, ServiceInfoMixin, context, desktop, frame, controller, text range, search/replace descriptors, `install_uno_stubs()` |
| `tests/stubs/writer_stubs.py` | 499 | WriterDocStub, ParagraphStub, TextStub, TextCursorStub, TableStub, heading tree building |
| `tests/stubs/calc_stubs.py` | 406 | CalcDocStub, CellStub, CellRangeStub, SheetStub, address resolution |
| `tests/stubs/draw_stubs.py` | 261 | DrawDocStub, DrawPageStub, ShapeStub, page/shape management |
| `tests/stubs/service_stubs.py` | 352 | StubDocumentService, StubConfigService, StubEventBus, StubTreeService, StubBookmarkService, StubServiceRegistry |
| `tests/conftest.py` | 104 | Fixtures: writer_doc, calc_doc, draw_doc, any_doc, services, writer/calc/draw_services, tool_context, calc_context, draw_context |
| `tests/test_stubs.py` | 302 | 38 smoke tests for all stub infrastructure |

### Test Results

- 38 new stub tests: **all pass**
- 69 existing framework tests: **all pass** (pre-existing failures unchanged)
- 8 pre-existing failures in old tests: unrelated to stubs (test_config_service + test_tool_registry assert against outdated error shapes)

### Design Decisions

- **Minimal depth**: Stubs support the methods tools actually call. Unstubbed methods raise clear `AttributeError`.
- **Stateful**: Writing to a stub cell/paragraph updates internal state; subsequent reads reflect changes.
- **Property-bag pattern**: `PropertyHolder` stores arbitrary `getPropertyValue()`/`setPropertyValue()` pairs.
- **No `uno` dependency**: All stubs import without `uno` installed; `install_uno_stubs()` patches `sys.modules` when needed.

---

## Remaining Phases

### Phase 2B: Tool Unit Tests (next)

For each module, write synthetic unit tests using stubs:
- Parameter validation, doc_type filtering, mutation detection
- Core execution logic (happy path + key error paths)
- **Priority**: writer/content.py (7 tools), calc/cells.py (7 tools), doc/file_ops.py (5 tools)
- Target: every tool has at least 1 synthetic test

### Phase 2C: Service Unit Tests (includes bug fix)

- Fix `DocumentService.set_events()` bug
- Test: cache invalidation, event wiring, service interdependencies
- Test: BookmarkService, TreeService, IndexService, ProximityService
- Verify the fix: after wiring, `document:cache_invalidated` events propagate to all subscriber services

### Phase 2D: Integration Tests

- Full dispatch pipeline: HTTP → MCP → ToolRegistry → tool → result
- Batch execution with variable chaining
- Cross-module tool invocation

### Phase 3: Live Smoke Testing — COMPLETE

**Status**: 82 smoke tests written, skip gracefully when LO+LibreMCP is not running

**How to run**:
```bash
# Start LibreOffice with LibreMCP installed, then:
make test-smoke
```

**Test structure**:
```
tests/smoke/
├── conftest.py              # MCP client, fixture creation, skip-if-down logic
├── test_smoke_writer.py     # 30 tests: 17 read + 9 mutation + 4 navigation/index
├── test_smoke_calc.py       # 17 tests: 10 read + 6 mutation + 1 batch
├── test_smoke_draw.py       # 16 tests: 6 read + 5 mutation + 3 impress + 2 batch
├── test_smoke_doc.py        # 19 tests: doc/core tools + cross-doc-type + MCP protocol
```

**Test categories**:
- Read-only tests (safe, no mutations): list_*, get_*, search_*, find_*, read_*
- Mutation tests (on fresh documents): insert_*, set_*, create_*, write_*, add_*, undo/redo
- MCP protocol tests: health endpoint, initialize, ping, tools/list

**Skip mechanism**: `conftest.py` checks `http://localhost:8766/health` for `{"status": "ok", "tools": N}`. If unavailable, all 82 tests skip with a clear message.

**Makefile targets**:
- `make test` — synthetic tests only (excludes smoke and legacy)
- `make test-smoke` — live smoke tests
- `make test-all` — synthetic + legacy (excludes smoke)
- Per-module smoke suites (Writer, Calc, Draw/Impress, Doc/Core)
- Each test: create doc → call tool → assert result → cleanup
- Requires running LibreOffice instance