#!/usr/bin/env python3
"""
mcp-test.py — Dev harness for testing MCP servers via stdio.

Usage:
    # List tools
    python dev/mcp-test.py dev/cage-mcp/config.yaml --list

    # Call a tool
    python dev/mcp-test.py dev/cage-mcp/config.yaml --call launch

    # Call with args
    python dev/mcp-test.py dev/cage-mcp/config.yaml --call screenshot --args '{"name":"test"}'

    # Restart server and call again (reload code)
    python dev/mcp-test.py dev/cage-mcp/config.yaml --restart --call launch

Reads dev/mcp-servers.yaml for authorized server definitions.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml


def load_servers_config() -> dict:
    """Load the MCP servers registry."""
    cfg_path = Path(__file__).parent / "mcp-servers.yaml"
    if not cfg_path.exists():
        return {}
    return yaml.safe_load(cfg_path.read_text()) or {}


def find_server(config_arg: str, servers: dict) -> tuple[list[str], str]:
    """
    Resolve a server command from either:
    - A config file path (looks up in mcp-servers.yaml by config path)
    - A server name from mcp-servers.yaml
    Returns (command, working_dir).
    """
    # Try by name first
    if config_arg in servers:
        srv = servers[config_arg]
        return srv["command"], srv.get("cwd", ".")

    # Try to match by config file path
    for name, srv in servers.items():
        if config_arg in srv.get("command", []):
            return srv["command"], srv.get("cwd", ".")

    # Fallback: assume it's a config.yaml for cage-mcp
    cage_dir = Path(__file__).parent / "cage-mcp"
    return [
        str(cage_dir / ".venv" / "bin" / "python"),
        str(cage_dir / "server.py"),
        config_arg,
    ], str(cage_dir)


class MCPTestClient:
    """Simple MCP stdio client for testing."""

    def __init__(self, command: list[str], cwd: str = "."):
        self.command = command
        self.cwd = cwd
        self.proc: subprocess.Popen | None = None
        self._msg_id = 0

    def start(self):
        """Start the MCP server subprocess."""
        self.proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd,
        )
        # Initialize
        resp = self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mcp-test", "version": "0.1.0"},
        })
        # Send initialized notification
        self._notify("notifications/initialized", {})
        return resp

    def stop(self):
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()
            self.proc = None

    def restart(self):
        self.stop()
        return self.start()

    def list_tools(self) -> list[dict]:
        resp = self._request("tools/list", {})
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        resp = self._request("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })
        return resp.get("result", resp)

    def _request(self, method: str, params: dict) -> dict:
        self._msg_id += 1
        msg = {
            "jsonrpc": "2.0",
            "id": self._msg_id,
            "method": method,
            "params": params,
        }
        return self._send(msg)

    def _notify(self, method: str, params: dict):
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        line = json.dumps(msg) + "\n"
        self.proc.stdin.write(line.encode())
        self.proc.stdin.flush()

    def _send(self, msg: dict) -> dict:
        line = json.dumps(msg) + "\n"
        self.proc.stdin.write(line.encode())
        self.proc.stdin.flush()

        # Read response (may have notifications before the response)
        while True:
            resp_line = self.proc.stdout.readline()
            if not resp_line:
                stderr = self.proc.stderr.read().decode(errors="replace")
                return {"error": f"Server closed. stderr: {stderr[-500:]}"}
            try:
                resp = json.loads(resp_line)
            except json.JSONDecodeError:
                continue
            # Skip notifications (no "id" field)
            if "id" in resp:
                return resp


def main():
    import argparse

    parser = argparse.ArgumentParser(description="MCP server test harness")
    parser.add_argument("server", help="Server name or config file path")
    parser.add_argument("--list", action="store_true", help="List tools")
    parser.add_argument("--call", type=str, help="Call a tool by name")
    parser.add_argument("--args", type=str, default="{}", help="Tool arguments as JSON")
    parser.add_argument("--restart", action="store_true", help="Restart before calling")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    args = parser.parse_args()

    servers = load_servers_config()
    command, cwd = find_server(args.server, servers)

    print(f"Server: {' '.join(command)}", file=sys.stderr)
    print(f"CWD: {cwd}", file=sys.stderr)

    client = MCPTestClient(command, cwd)

    try:
        init = client.start()
        print(f"Initialized: {init.get('result', {}).get('serverInfo', {})}", file=sys.stderr)

        if args.list:
            tools = client.list_tools()
            for t in tools:
                schema = t.get("inputSchema", {})
                params = list(schema.get("properties", {}).keys())
                required = schema.get("required", [])
                param_str = ", ".join(
                    f"{'*' if p in required else ''}{p}" for p in params
                )
                print(f"  {t['name']}({param_str}) — {t.get('description', '')}")
            return

        if args.call:
            tool_args = json.loads(args.args)
            print(f"Calling: {args.call}({tool_args})", file=sys.stderr)
            result = client.call_tool(args.call, tool_args)

            # Pretty print content
            contents = result.get("content", [])
            for c in contents:
                if c.get("type") == "text":
                    print(c["text"])
                elif c.get("type") == "image":
                    print(f"[image: {len(c.get('data', ''))} bytes base64]")
                else:
                    print(json.dumps(c, indent=2))
            if not contents:
                print(json.dumps(result, indent=2))
            return

        if args.interactive:
            print("Interactive mode. Commands: list, call <tool> [json_args], quit")
            while True:
                try:
                    line = input("mcp> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not line or line == "quit":
                    break
                if line == "list":
                    tools = client.list_tools()
                    for t in tools:
                        print(f"  {t['name']} — {t.get('description', '')}")
                    continue
                if line == "restart":
                    client.restart()
                    print("Restarted.")
                    continue
                parts = line.split(None, 2)
                if parts[0] == "call" and len(parts) >= 2:
                    tool_name = parts[1]
                    tool_args = json.loads(parts[2]) if len(parts) > 2 else {}
                    result = client.call_tool(tool_name, tool_args)
                    contents = result.get("content", [])
                    for c in contents:
                        if c.get("type") == "text":
                            print(c["text"])
                        elif c.get("type") == "image":
                            print(f"[image: {len(c.get('data', ''))} bytes]")
                    if not contents:
                        print(json.dumps(result, indent=2))
                    continue
                print(f"Unknown: {line}")

    finally:
        client.stop()


if __name__ == "__main__":
    main()
