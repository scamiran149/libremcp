#!/usr/bin/env python3
"""
mcp-dev — MCP stdio server for testing MCP servers in development.

Supports both HTTP and stdio MCP servers. Reads config.yaml for the
authorized server list. Exposes mcp_list_tools and mcp_call_tool so
Claude Code can test any authorized MCP server without curl.

Usage:
    python server.py [serve] [config.yaml]
"""

from __future__ import annotations

import asyncio
import json
import logging
import shlex
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

log = logging.getLogger("mcp-dev")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(config_path: str | None = None) -> dict:
    if config_path is None:
        config_path = str(Path(__file__).parent / "config.yaml")
    p = Path(config_path)
    if not p.is_absolute():
        p = Path(__file__).parent / p
    if not p.exists():
        log.warning("Config not found: %s", p)
        return {"servers": {}}
    return yaml.safe_load(p.read_text()) or {"servers": {}}


# ---------------------------------------------------------------------------
# HTTP transport
# ---------------------------------------------------------------------------

def _http_post(url: str, method: str, params: dict | None = None) -> dict:
    body = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        return {"error": {"code": -1, "message": str(e)}}
    except Exception as e:
        return {"error": {"code": -1, "message": str(e)}}


# ---------------------------------------------------------------------------
# Stdio transport — manages subprocess lifecycle per server
# ---------------------------------------------------------------------------

class StdioClient:
    """Manages a stdio MCP subprocess."""

    def __init__(self, command: str, args: list[str], cwd: str | None = None):
        self.cmd = [command] + args
        self.cwd = cwd
        self.proc: subprocess.Popen | None = None
        self._msg_id = 0
        self._lock = asyncio.Lock()

    async def ensure_started(self):
        if self.proc is not None and self.proc.poll() is None:
            return
        self.proc = await asyncio.to_thread(self._spawn)
        # Initialize handshake
        resp = await self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mcp-dev", "version": "0.1.0"},
        })
        await self._notify("notifications/initialized", {})
        log.info("stdio server started: %s", " ".join(self.cmd))

    def _spawn(self) -> subprocess.Popen:
        return subprocess.Popen(
            self.cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd,
        )

    async def request(self, method: str, params: dict | None = None) -> dict:
        async with self._lock:
            await self.ensure_started()
            return await self._request(method, params)

    async def _request(self, method: str, params: dict | None = None) -> dict:
        self._msg_id += 1
        msg = {"jsonrpc": "2.0", "id": self._msg_id, "method": method}
        if params is not None:
            msg["params"] = params
        return await asyncio.to_thread(self._send, msg)

    async def _notify(self, method: str, params: dict):
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        line = json.dumps(msg) + "\n"
        self.proc.stdin.write(line.encode())
        self.proc.stdin.flush()

    def _send(self, msg: dict) -> dict:
        line = json.dumps(msg) + "\n"
        self.proc.stdin.write(line.encode())
        self.proc.stdin.flush()
        while True:
            resp_line = self.proc.stdout.readline()
            if not resp_line:
                stderr = self.proc.stderr.read().decode(errors="replace")
                return {"error": {"code": -1,
                                  "message": "Server closed. stderr: %s" % stderr[-500:]}}
            try:
                resp = json.loads(resp_line)
            except json.JSONDecodeError:
                continue
            if "id" in resp:
                return resp

    def stop(self):
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()
            self.proc = None


# ---------------------------------------------------------------------------
# Unified dispatch
# ---------------------------------------------------------------------------

_stdio_clients: dict[str, StdioClient] = {}


async def _dispatch(srv_cfg: dict, srv_name: str,
                    method: str, params: dict | None = None) -> dict:
    srv_type = srv_cfg.get("type", "http")

    if srv_type == "http":
        url = srv_cfg["url"]
        return await asyncio.to_thread(_http_post, url, method, params)

    elif srv_type == "stdio":
        if srv_name not in _stdio_clients:
            command = srv_cfg["command"]
            args = srv_cfg.get("args", [])
            cwd = srv_cfg.get("cwd")
            _stdio_clients[srv_name] = StdioClient(command, args, cwd)
        client = _stdio_clients[srv_name]
        return await client.request(method, params)

    return {"error": {"code": -1, "message": "Unknown server type: %s" % srv_type}}


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

def create_server(config: dict) -> Server:
    servers = config.get("servers", {})
    server_names = list(servers.keys())

    app = Server("mcp-dev")

    @app.list_tools()
    async def list_tools_handler():
        desc_lines = []
        for name, cfg in servers.items():
            t = cfg.get("type", "http")
            d = cfg.get("description", "")
            if t == "http":
                desc_lines.append("%s (%s, %s)" % (name, t, cfg.get("url", "?")))
            else:
                desc_lines.append("%s (%s, %s)" % (name, t, cfg.get("command", "?")))
            if d:
                desc_lines[-1] += " — " + d

        return [
            Tool(
                name="mcp_list_tools",
                description=(
                    "List tools on an authorized MCP server. "
                    "Servers: %s" % "; ".join(desc_lines)
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "server": {
                            "type": "string",
                            "description": "Server name.",
                            "enum": server_names,
                        },
                    },
                    "required": ["server"],
                },
            ),
            Tool(
                name="mcp_call_tool",
                description=(
                    "Call a tool on an authorized MCP server. "
                    "Servers: %s" % ", ".join(server_names)
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "server": {
                            "type": "string",
                            "description": "Server name.",
                            "enum": server_names,
                        },
                        "tool": {
                            "type": "string",
                            "description": "Tool name to call.",
                        },
                        "arguments": {
                            "type": "object",
                            "description": "Tool arguments (optional).",
                        },
                    },
                    "required": ["server", "tool"],
                },
            ),
        ]

    @app.call_tool()
    async def call_tool_handler(name: str, arguments: dict):
        server_name = arguments.get("server", "")
        if server_name not in servers:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": "Unknown server '%s'. Authorized: %s"
                    % (server_name, ", ".join(server_names))
                }),
            )]

        srv_cfg = servers[server_name]

        if name == "mcp_list_tools":
            resp = await _dispatch(srv_cfg, server_name, "tools/list")
            if "error" in resp:
                return [TextContent(type="text", text=json.dumps(resp["error"]))]
            tools = resp.get("result", {}).get("tools", [])
            lines = []
            for t in tools:
                schema = t.get("inputSchema", {})
                params = list(schema.get("properties", {}).keys())
                required = schema.get("required", [])
                param_str = ", ".join(
                    ("*" + p if p in required else p) for p in params
                )
                lines.append(
                    "%s(%s) — %s" % (t["name"], param_str, t.get("description", ""))
                )
            return [TextContent(
                type="text",
                text=json.dumps({
                    "server": server_name,
                    "type": srv_cfg.get("type", "http"),
                    "tool_count": len(tools),
                    "tools": lines,
                }, ensure_ascii=False, indent=2),
            )]

        elif name == "mcp_call_tool":
            tool_name = arguments.get("tool", "")
            tool_args = arguments.get("arguments", {})
            resp = await _dispatch(
                srv_cfg, server_name, "tools/call",
                {"name": tool_name, "arguments": tool_args},
            )
            if "error" in resp:
                return [TextContent(type="text", text=json.dumps(resp["error"]))]
            result = resp.get("result", {})
            contents = result.get("content", [])
            parts = []
            for c in contents:
                if c.get("type") == "text":
                    try:
                        parsed = json.loads(c["text"])
                        parts.append(json.dumps(parsed, ensure_ascii=False, indent=2))
                    except (json.JSONDecodeError, TypeError):
                        parts.append(c["text"])
                elif c.get("type") == "image":
                    parts.append("[image: %d bytes base64]" % len(c.get("data", "")))
                else:
                    parts.append(json.dumps(c, ensure_ascii=False))
            return [TextContent(
                type="text",
                text="\n".join(parts) if parts
                else json.dumps(result, ensure_ascii=False, indent=2),
            )]

        return [TextContent(type="text", text='{"error": "unknown tool: %s"}' % name)]

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def amain(config_path: str | None = None):
    config = load_config(config_path)
    app = create_server(config)
    try:
        async with stdio_server() as (read, write):
            await app.run(read, write, app.create_initialization_options())
    finally:
        for client in _stdio_clients.values():
            client.stop()


def main():
    config_path = None
    args = sys.argv[1:]
    if args and args[0] == "serve":
        args = args[1:]
    if args:
        config_path = args[0]
    asyncio.run(amain(config_path))


if __name__ == "__main__":
    main()
