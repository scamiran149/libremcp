# Dev Tools for LibreMCP

Development tooling for visual debugging and automated testing of the LibreMCP
LibreOffice extension.

Uses [wbox-mcp](https://github.com/quazardous/wbox-mcp) to run LibreOffice
inside a nested Wayland compositor, controllable via MCP tools (screenshot,
click, key, deploy, etc.).

## Structure

```
dev/
  lo-wbox/             # wbox-mcp workspace for LibreOffice
    config.yaml        # Compositor + LO app config
    scripts/           # deploy.sh, seed_registry.py, etc.
    log/               # Runtime logs (gitignored)
    screenshots/       # Captured screenshots (gitignored)

  mcp-dev/             # MCP proxy server for dev testing
    server.py          # Exposes mcp_call_tool / mcp_list_tools
    config.yaml        # Authorized MCP servers (libremcp, libremcp-dev, lo-wbox)
    mcp-test.py        # CLI test harness
```

## Setup

```bash
# Install wbox-mcp
pipx install wbox-mcp
# or: uv tool install wbox-mcp

# Install mcp-dev dependencies
cd dev/mcp-dev
uv venv && uv pip install mcp pyyaml
```

## Usage

### wbox-mcp (compositor + LO)

Add to `.mcp.json`:

```json
{
  "lo-wbox": {
    "type": "stdio",
    "command": "wbox-mcp",
    "args": ["serve", "dev/lo-wbox/config.yaml"]
  }
}
```

Then use `mcp__lo-wbox__launch`, `mcp__lo-wbox__screenshot`, `mcp__lo-wbox__deploy`, etc.

### mcp-dev (MCP proxy)

Add to `.mcp.json`:

```json
{
  "mcp-dev": {
    "type": "stdio",
    "command": "uv",
    "args": ["run", "--directory", "dev/mcp-dev", "python", "server.py"]
  }
}
```

Allows calling any authorized MCP server (libremcp, libremcp-dev, lo-wbox) via
`mcp_call_tool` / `mcp_list_tools` without restarting Claude Code.

### CLI testing

```bash
cd dev/mcp-dev
python mcp-test.py lo-wbox --list
python mcp-test.py lo-wbox --call launch
python mcp-test.py lo-wbox --call screenshot
python mcp-test.py lo-wbox --call deploy
```

## LO isolation

LibreOffice runs with a separate profile (`/tmp/lo_dev_profile`) and LibreMCP
uses port 8767 (vs 8766 production), injected via `LIBREMCP_SET_CONFIG`.
