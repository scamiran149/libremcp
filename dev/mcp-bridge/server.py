#!/usr/bin/env python3
"""
mcp-bridge — Stdio-to-HTTP MCP proxy.

Translates stdio MCP (JSON-RPC on stdin/stdout) to LibreMCP's HTTP MCP
endpoint. Handles session management and auto-reinitialize on 409.

Usage:
    python server.py [--url http://localhost:8766/mcp]

Configure in .mcp.json:
    {
      "mcpServers": {
        "libremcp": {
          "type": "stdio",
          "command": "python",
          "args": ["dev/mcp-bridge/server.py"]
        }
      }
    }
"""

import json
import logging
import sys
import urllib.request
import urllib.error

log = logging.getLogger("mcp-bridge")

DEFAULT_URL = "http://localhost:8766/mcp"


class MCPBridge:
    """Proxies stdio JSON-RPC to an HTTP MCP server."""

    def __init__(self, url):
        self.url = url
        self.session_id = None

    def forward(self, msg):
        """Forward a JSON-RPC message to the HTTP server.

        Returns the response dict, or None for notifications.
        Handles 409 (stale session) by re-initializing automatically.
        """
        resp = self._post(msg)
        if resp is None:
            return None

        # 409 = stale session → re-initialize and retry
        if resp.get("_status") == 409:
            log.info("Session expired, re-initializing...")
            init_msg = {
                "jsonrpc": "2.0",
                "id": "__bridge_reinit__",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "mcp-bridge", "version": "1.0"},
                },
            }
            init_resp = self._post(init_msg)
            if init_resp and init_resp.get("_status") != 409:
                # Send initialized notification
                self._post(
                    {
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                        "params": {},
                    }
                )
                # Retry the original message
                resp = self._post(msg)

        resp.pop("_status", None)
        return resp

    def _post(self, msg):
        """HTTP POST to the MCP endpoint."""
        data = json.dumps(msg).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        req = urllib.request.Request(
            self.url, data=data, headers=headers, method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                self._update_session(resp)
                body = json.loads(resp.read().decode("utf-8"))
                body["_status"] = resp.status
                return body
        except urllib.error.HTTPError as e:
            body_bytes = e.read()
            try:
                body = json.loads(body_bytes.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                body = {"error": {"code": -1, "message": str(e)}}
            body["_status"] = e.code
            self._update_session(e)
            return body
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "error": {"code": -1, "message": "Bridge error: %s" % e},
                "_status": 0,
            }

    def _update_session(self, resp):
        """Read Mcp-Session-Id from response headers."""
        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            self.session_id = sid


def main():
    # Force UTF-8 on all I/O (Windows defaults to cp1252)
    if sys.platform == "win32":
        import os

        os.environ["PYTHONUTF8"] = "1"
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    url = DEFAULT_URL
    for arg in sys.argv[1:]:
        if arg.startswith("--url="):
            url = arg.split("=", 1)[1]
        elif arg.startswith("http"):
            url = arg

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        stream=sys.stderr,
    )

    bridge = MCPBridge(url)
    log.info("MCP bridge started: %s", url)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Notifications (no id) — forward but don't expect response
        if "id" not in msg:
            bridge.forward(msg)
            continue

        resp = bridge.forward(msg)
        if resp:
            out = json.dumps(resp, ensure_ascii=False)
            sys.stdout.write(out + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
