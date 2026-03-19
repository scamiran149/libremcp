# Roadmap

What's planned for Nelson MCP. Items are grouped by theme, roughly ordered by priority within each group.

## Agent Experience

- **System prompt injection** — send a tailored system prompt with the `initialize` response based on the active endpoint/preset. Include document context, available workflows, and tool usage hints so agents start productive immediately
- **Workflow tools** — higher-level tools that chain common patterns: "replace section by heading" (resolve heading → read → delete range → insert), "move paragraph" (read → delete → insert at new position)
- **Streaming tool progress** — SSE notifications for long-running operations (batch, AI indexation) so agents can show progress instead of waiting blind
- **Agent memory** — persist agent session context (last document, recent actions, preferences) across MCP reconnects

## Writer

- **Range coordinate fix** — align `get_document_content(scope="range")` and `apply_document_content(target="range")` with cursor-based paragraph offsets (known issue)
- **Section management** — insert/delete/reorder document sections (`com.sun.star.text.TextSection`)
- **Header/footer editing** — read and write page header/footer content
- **Footnote/endnote tools** — insert, list, edit footnotes and endnotes
- **Mail merge** — template fields + data source for batch document generation

## Calc

- **Pivot tables** — create and manipulate DataPilot tables
- **Data validation** — set validation rules on cell ranges
- **Sheet protection** — lock/unlock sheets and ranges
- **Named range management** — create/edit/delete named ranges (currently read-only)

## Impress / Draw

- **Reorder slides** — move slides by index
- **Duplicate slide** — clone a slide for templating
- **Structured slide export** — return title + bullets + images in one call per slide
- **Outline-to-deck** — generate a presentation from a Writer document outline
- **Presentation controls** — `start_presentation`, `goto_slide`, `stop_presentation`
- **AI slide audits** — text density, contrast, visual balance analysis

## AI & Indexation

- **idxV2 — unified document index** — sparse paragraph↔page cache (PageMap) with interpolation + XSelectionChangeListener for cursor tracking. Enables instant page-level navigation for large documents. Code exists (disabled), needs stabilization
- **Multi-provider LLM routing** — route prompts to different providers based on task (fast model for tagging, large model for summaries)
- **RAG over galleries** — vector embeddings for image/document galleries, enabling semantic search beyond keyword matching
- **AI image captioning in Writer** — auto-generate alt text and captions for inserted images using CLIP/LLM
- **AI Horde UX** — progress feedback during generation, smart image dimensions (read original size), translation visibility

## Infrastructure

- **CI/CD pipeline** — automated build + test on push, release artifact upload
- **Headless testing** — test tool execution without a display (Xvfb/cage compositor)
- **Test coverage** — expand beyond framework unit tests to integration tests with actual UNO calls
- **Linux .deb/.rpm packaging** — system package for distro repos alongside .oxt
- **Extension marketplace** — publish to LibreOffice Extensions site

## Protocol & Connectivity

- **MCP resources** — expose document metadata, gallery contents, and config as MCP resources (not just tools)
- **MCP prompts** — predefined prompt templates for common tasks (summarize document, review changes, format table)
- **WebSocket transport** — bidirectional MCP over WebSocket as alternative to HTTP+SSE
- **Multi-user sessions** — session isolation for concurrent agents working on different documents
- **OAuth / API keys** — authentication for exposed endpoints (currently open)
