# Roadmap

## Where we are

Nelson MCP v0.7 exposes 148 tools via MCP to cloud AI agents (Claude, ChatGPT, Gemini). It works well with large models that can handle many tools, but smaller local models (7B–14B) get confused by the tool count and protocol complexity. Custom endpoints help (static filtered subsets), but don't solve the underlying problem: small models need guidance, not just fewer options.

## Where we're going

The next versions shift Nelson from a passive tool server ("here are 148 tools, figure it out") to an active collaborator that adapts to the agent's capabilities, learns from real usage, and guides agents through workflows.

---

## v0.8 — Make small models productive

The core problem: a 7B model can't reliably pick from 25 tools, compose locators, and chain multi-step workflows. Nelson should do that work for it.

### Simple REST API (`/api/do`)

A single high-level endpoint for models that struggle with tool selection:

```json
POST /api/do
{
  "action": "insert_text",
  "heading": "Introduction",
  "position": "after",
  "content": "New paragraph text..."
}
```

Nelson resolves "Introduction" internally (heading lookup → bookmark → paragraph index → `insert_at_paragraph`). The model never sees paragraph indices, bookmarks, or locators. ~15 structured actions instead of 148 low-level tools.

### Tool broker (progressive disclosure)

Bring back the two-tier tool delivery, adapted for MCP:

- **Core tools** always visible: `list_open_documents`, `get_document_info`, `get_document_outline`, `do`, `request_tools`
- **Extended tools** unlocked on demand by intent: `request_tools(intent="edit")` adds editing tools to the session
- Intent groups: `navigate`, `edit`, `search`, `tables`, `images`, `styles`, `review`, `calc`, `draw`
- `tools/list` reflects the current session — starts small, grows as the agent asks
- Compatible with MCP `listChanged` notification

### Context-aware tool filtering

`tools/list` adapts to what's happening:
- No document open → only lifecycle tools (open, create, list recent)
- Writer document → Writer tools only (no Calc/Draw noise)
- First edit done → surface `undo`, `save_document`

### Session trace collection

Nelson logs every tool call to a local SQLite database:

```sql
session_traces (session_id, seq, tool_name, doc_type, success, prev_tool, ts)
```

No telemetry, no cloud — just local data that fuels the learning cycle (see v0.9).

---

## v0.9 — Learn from usage

The key insight: every agent session is a training signal. Nelson collects traces at runtime (zero cost), then uses an LLM offline to extract patterns and generate rules that improve the next session.

### The learning cycle

```
Runtime                    Idle / on-demand              Next boot
─────────                  ────────────────              ─────────
Agent calls tools    →     LLM analyzes traces    →     rules.json loaded
Traces saved to SQLite     Extracts patterns             State machine applies rules
Zero overhead              Runs when GPU is free         Zero overhead
```

The LLM doesn't run during agent sessions — no GPU conflict with the client model. It processes traces offline (when the machine is idle, or on user request), like a coach reviewing game replays.

### What the LLM extracts

From accumulated session traces, the LLM generates `rules.json`:

```json
[
  {
    "after": ["list_open_documents", "get_document_outline"],
    "doc_type": "writer",
    "suggest": ["get_heading_content", "find_text"],
    "confidence": 0.85
  },
  {
    "after": ["insert_at_paragraph"],
    "followed_by_undo_rate": 0.30,
    "hint": "Verify paragraph_index with resolve_locator before inserting"
  },
  {
    "pattern": "get_heading_content → insert_at_paragraph → save_document",
    "name": "edit_section",
    "frequency": 0.60
  }
]
```

- **Workflow patterns** — common sequences that work, ranked by frequency
- **Anti-patterns** — sequences that lead to undo or failure, with corrective hints
- **Suggestion weights** — what to propose after each tool, specific to this user's habits and document types

### `_next` suggestions

Both MCP and `/api/do` return `_next` after every action, powered by the learned rules:

**MCP response:**
```json
{
  "result": { "paragraph_index": 12 },
  "_next": [
    {"tool": "get_heading_content", "args": {"heading": "Conclusion"}},
    {"tool": "save_document", "reason": "5 unsaved edits"}
  ]
}
```

**`/api/do` response:**
```json
{
  "result": { "ok": true },
  "_next": [
    {"action": "read", "heading": "Conclusion"},
    {"action": "save"}
  ]
}
```

Large cloud models can ignore `_next`. Small local models use it as a guide — effectively turning Nelson into a copilot for the copilot.

### System prompt enrichment

Nelson injects the most reliable workflow patterns into the MCP `instructions` field at initialize time, tailored to the active document type and endpoint. The agent starts with knowledge of what works, learned from real sessions.

---

## v1.0 — Production ready

### Stability & trust

- **CI/CD pipeline** — automated build + test on push, release artifacts
- **Integration tests** — tool execution against a real LibreOffice instance (headless)
- **Range coordinate fix** — resolve the known Writer coordinate mismatch
- **Session authentication** — API keys for exposed endpoints

### Packaging & distribution

- **LibreOffice Extensions site** — publish on the official marketplace
- **Linux packages** — .deb/.rpm for distro repos
- **One-click installer** — bundled LibreOffice + Nelson for non-technical users

### Protocol

- **MCP resources** — expose document structure and gallery contents as browsable resources
- **MCP prompts** — predefined prompt templates for common tasks
- **WebSocket transport** — alternative to HTTP+SSE for persistent connections

---

## Beyond v1.0

- **Unified document index (idxV2)** — paragraph↔page cache with cursor tracking for instant navigation in large documents
- **RAG over galleries** — vector embeddings for semantic search across image and document libraries
- **AI slide generation** — outline-to-deck conversion from Writer documents
- **Multi-user sessions** — concurrent agents on different documents with session isolation
- **Cross-document workflows** — copy content between documents, merge, compare
