# LibreMCP

A LibreOffice extension that turns your documents into an MCP server. External AI clients connect over HTTP and get full access to document tools — reading, editing, navigating, formatting, and more.

Works with any MCP-compatible client: Claude Code, OpenCode, Goose, ollmcp, etc.

## How it works

LibreMCP runs an HTTP server inside LibreOffice and speaks the [Model Context Protocol](https://modelcontextprotocol.io/). AI agents connect to it and use tools to interact with your open document — no copy-paste, no file export.

```
┌─────────────┐       HTTP/MCP        ┌──────────────┐
│  AI Client   │ ──────────────────── │  LibreOffice  │
│ (Claude Code,│   tools/call         │  + LibreMCP   │
│  OpenCode…)  │ ◄──────────────────  │               │
└─────────────┘    tool results       └──────────────┘
```

## Features

- **~115 document tools** — read content, edit text, manage styles, insert images, handle tables, charts, conditional formatting, hyperlinks, track changes, navigate headings, search, and more
- **Custom MCP endpoints** — expose only the tools your agent needs. Built-in presets (minimal, writer-edit, writer-read, calc) or create your own filtered endpoints
- **Writer, Calc, Draw, Impress** — tools adapt to the active document type
- **SSL** — optional HTTPS with auto-generated certificates
- **Modular** — each feature is a self-contained module with its own config, services, and tools

## Install

1. Download the latest `.oxt` from the [releases page](https://github.com/scamiran149/libremcp/releases)
2. In LibreOffice: **Tools > Extension Manager > Add**
3. Restart LibreOffice
4. The MCP server starts automatically (default: `http://localhost:8766/mcp`)

## Quick start

Once installed, point your MCP client at the server:

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

Open a document in LibreOffice, then ask your AI client to read or edit it.

**For AI agents:** see [`QUICKSTART.md`](QUICKSTART.md) — a step-by-step guide for LLM agents on how to discover documents, navigate structure, and use tools effectively.

## Modules

| Module | Description |
|--------|-------------|
| `core` | Document access, config, events, formatting |
| `writer` | Content editing, comments, styles, tables, change tracking |
| `writer.nav` | Heading tree, bookmarks, proximity navigation |
| `writer.index` | Full-text search with Snowball stemming |
| `calc` | Cells, sheets, formulas, charts, conditional formatting, comments |
| `draw` | Shapes, pages, slides, placeholders, master slides, transitions (Draw and Impress) |
| `batch` | Multi-tool execution with variable chaining |
| `http` | Shared HTTP server with optional SSL |
| `mcp` | MCP JSON-RPC protocol handler |

## Development

```bash
./install.sh              # Set up dev environment
make deploy               # Build + install + restart LO + show log
make test                 # Run tests
```

See [DEVEL.md](DEVEL.md) for the complete developer guide and [docs/modules.md](docs/modules.md) for the module framework reference.

## Documentation

- [`QUICKSTART.md`](QUICKSTART.md) — agent guide: discovery, workflows, tool patterns
- [`AGENTS.md`](AGENTS.md) — developer cheatsheet: project structure, build pipeline, critical rules
- [`docs/roadmap.md`](docs/roadmap.md) — what's planned next
- [`CHANGELOG.md`](CHANGELOG.md) — version history

## Acknowledgments

LibreMCP is a fork of [Nelson MCP](https://github.com/quazardous/nelson-mcp), stripped down to core MCP document tools. Nelson MCP itself was built on [LocalWriter](https://github.com/KeithCu/localwriter) by Keith Curtis and [mcp-libre](https://github.com/patrup/mcp-libre).

## License

MPL 2.0 — see `License.txt`.
