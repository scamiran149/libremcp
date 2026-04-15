"""Smoke test infrastructure — MCP client and fixtures for live LO testing.

Tests skip gracefully if LO+LibreMCP is not running (no server at localhost:9876).
"""

import json
import time
import uuid

import pytest
import urllib.request
import urllib.error

MCP_URL = "http://localhost:9876/mcp"
HEALTH_URL = "http://localhost:9876/health"
DEFAULT_TIMEOUT = 30

_server_available = None


def is_server_running():
    """Check if LibreMCP server is responding (cached)."""
    global _server_available
    if _server_available is None:
        try:
            req = urllib.request.Request(HEALTH_URL)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                _server_available = data.get("status") == "ok" and "tools" in data
        except Exception:
            _server_available = False
    return _server_available


def pytest_configure(config):
    config.addinivalue_line("markers", "smoke: live smoke test requiring LO+LibreMCP")


def pytest_collection_modifyitems(config, items):
    """Skip all smoke tests if LibreMCP server is not reachable."""
    if not is_server_running():
        for item in items:
            item.add_marker(
                pytest.mark.skip(
                    reason="LibreMCP server not running — start LO with LibreMCP"
                )
            )


def mcp_call(method, params=None, timeout=DEFAULT_TIMEOUT):
    """Send a JSON-RPC request to the LibreMCP server."""
    req_id = str(uuid.uuid4())
    body = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        MCP_URL,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        response = json.loads(resp.read())

    if "error" in response:
        err = response["error"]
        raise AssertionError(f"MCP error {err.get('code')}: {err.get('message')}")

    result = response.get("result")
    if result is None:
        raise AssertionError("MCP response missing 'result'")

    content = result.get("content", [])
    if content and content[0].get("type") == "text":
        text = content[0]["text"]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw_text": text, "isError": result.get("isError", False)}

    return result


def call_tool(tool_name, arguments=None, doc_id=None):
    """Call a LibreMCP tool via MCP tools/call with a small delay for LO."""
    time.sleep(0.15)
    args = dict(arguments or {})
    if doc_id is not None:
        args["_document"] = doc_id
    return mcp_call("tools/call", {"name": tool_name, "arguments": args})


# ── Session fixtures ────────────────────────────────────────────────


@pytest.fixture(scope="session")
def writer_doc_id():
    """Use the currently active Writer document. No creation needed."""
    result = call_tool("get_document_info", {})
    if result.get("doc_type") != "writer":
        pytest.skip("Active document is not a Writer document")
    return result.get("doc_id")
