import json
from unittest.mock import patch, MagicMock

import pytest

from plugin.modules.mcp.protocol import (
    MCPProtocolHandler,
    _jsonrpc_ok,
    _jsonrpc_error,
    _tool_error,
    MCP_PROTOCOL_VERSION,
    _METHOD_NOT_FOUND,
    _INVALID_REQUEST,
)
from plugin.framework.tool_registry import ToolRegistry
from plugin.framework.service_registry import ServiceRegistry
from plugin.framework.event_bus import EventBus
from plugin.framework.tool_base import ToolBase
from plugin.framework.tool_context import ToolContext


class FakeReadTool(ToolBase):
    name = "get_info"
    description = "Gets info"
    parameters = {"type": "object", "properties": {}}
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        return {"status": "ok", "info": "hello"}


class FakeWriteTool(ToolBase):
    name = "set_data"
    description = "Sets data"
    parameters = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
    }
    doc_types = None
    requires_doc = False

    def execute(self, ctx, **kwargs):
        return {"status": "ok", "value": kwargs["value"]}


class FakeFailingTool(ToolBase):
    name = "bad_tool"
    description = "Always fails validation"
    parameters = {
        "type": "object",
        "properties": {"key": {"type": "string"}},
        "required": ["key"],
    }
    doc_types = None

    def execute(self, ctx, **kwargs):
        return {"status": "error", "code": "validation", "message": "bad input"}


class FakeDocOnlyTool(ToolBase):
    name = "writer_only"
    description = "Writer only"
    parameters = {"type": "object", "properties": {}}
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        return {"status": "ok"}


class FakeNoDocTool(ToolBase):
    name = "create_doc"
    description = "No doc needed"
    parameters = {"type": "object", "properties": {}}
    doc_types = None
    requires_doc = False

    def execute(self, ctx, **kwargs):
        return {"status": "ok", "created": True}


class StubDocService:
    name = "document"

    def get_active_document(self):
        return None

    def detect_doc_type(self, doc):
        return None

    def get_doc_id(self, doc):
        return None

    def get_default_save_dir(self):
        return "/tmp"

    def invalidate_cache(self, doc):
        pass

    def _get_desktop(self):
        return None


class StubConfigService:
    name = "config"

    def proxy_for(self, module_name):
        return MagicMock()


def _make_services():
    services = ServiceRegistry()
    services.register_instance("document", StubDocService())
    services.register_instance("config", StubConfigService())
    services.register_instance("events", EventBus())
    tool_reg = ToolRegistry(services)
    services.register_instance("tools", tool_reg)
    return services


def _make_handler(services=None, tool_filter=None, tools=None):
    if services is None:
        services = _make_services()
    if tools is None:
        tools = [
            FakeReadTool(),
            FakeWriteTool(),
            FakeFailingTool(),
            FakeDocOnlyTool(),
            FakeNoDocTool(),
        ]
    for t in tools:
        services.tools.register(t)
    return MCPProtocolHandler(services, tool_filter=tool_filter)


class TestJsonRpcHelpers:
    def test_jsonrpc_ok_structure(self):
        result = _jsonrpc_ok(1, {"data": "value"})
        assert result == {"jsonrpc": "2.0", "id": 1, "result": {"data": "value"}}

    def test_jsonrpc_ok_with_none_result(self):
        result = _jsonrpc_ok(42, None)
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 42
        assert result["result"] is None

    def test_jsonrpc_error_structure(self):
        result = _jsonrpc_error(2, -32600, "Invalid request")
        assert result == {
            "jsonrpc": "2.0",
            "id": 2,
            "error": {"code": -32600, "message": "Invalid request"},
        }

    def test_jsonrpc_error_with_data(self):
        result = _jsonrpc_error(3, -32603, "Internal error", data={"detail": "x"})
        assert result["error"]["data"] == {"detail": "x"}

    def test_tool_error_basic(self):
        result = _tool_error("not_found", "Tool not found")
        assert result["status"] == "error"
        assert result["code"] == "not_found"
        assert result["message"] == "Tool not found"
        assert result["retryable"] is False
        assert "hint" not in result

    def test_tool_error_with_hint(self):
        result = _tool_error("no_document", "No doc", hint="Open a document first")
        assert result["hint"] == "Open a document first"

    def test_tool_error_with_retryable(self):
        result = _tool_error("busy", "Server busy", retryable=True)
        assert result["retryable"] is True


class TestProcessJsonrpc:
    def test_initialize(self):
        handler = _make_handler()
        msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        status, resp = handler._process_jsonrpc(msg)
        assert status == 200
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert "result" in resp

    def test_ping(self):
        handler = _make_handler()
        msg = {"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}}
        status, resp = handler._process_jsonrpc(msg)
        assert status == 200
        assert resp["result"] == {}

    def test_tools_list(self):
        handler = _make_handler()
        msg = {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
        status, resp = handler._process_jsonrpc(msg)
        assert status == 200
        assert "tools" in resp["result"]
        tool_names = [t["name"] for t in resp["result"]["tools"]]
        assert "get_info" not in tool_names
        assert "set_data" in tool_names
        assert "create_doc" in tool_names

    def test_invalid_jsonrpc_missing_version(self):
        handler = _make_handler()
        msg = {"id": 1, "method": "ping"}
        status, resp = handler._process_jsonrpc(msg)
        assert status == 400
        assert resp["error"]["code"] == _INVALID_REQUEST

    def test_unknown_method(self):
        handler = _make_handler()
        msg = {"jsonrpc": "2.0", "id": 5, "method": "nonexistent", "params": {}}
        status, resp = handler._process_jsonrpc(msg)
        assert status == 400
        assert resp["error"]["code"] == _METHOD_NOT_FOUND

    def test_notification_no_id(self):
        handler = _make_handler()
        msg = {"jsonrpc": "2.0", "method": "ping", "params": {}}
        result = handler._process_jsonrpc(msg)
        assert result is None

    def test_resources_list(self):
        handler = _make_handler()
        msg = {"jsonrpc": "2.0", "id": 6, "method": "resources/list", "params": {}}
        status, resp = handler._process_jsonrpc(msg)
        assert status == 200
        assert resp["result"] == {"resources": []}

    def test_prompts_list(self):
        handler = _make_handler()
        msg = {"jsonrpc": "2.0", "id": 7, "method": "prompts/list", "params": {}}
        status, resp = handler._process_jsonrpc(msg)
        assert status == 200
        assert resp["result"] == {"prompts": []}

    def test_non_dict_message(self):
        handler = _make_handler()
        status, resp = handler._process_jsonrpc("not a dict")
        assert status == 400
        assert resp["error"]["code"] == _INVALID_REQUEST


class TestMcpInitialize:
    def test_protocol_version(self):
        handler = _make_handler()
        resp = handler._mcp_initialize({})
        assert resp["protocolVersion"] == MCP_PROTOCOL_VERSION

    def test_capabilities(self):
        handler = _make_handler()
        resp = handler._mcp_initialize({})
        caps = resp["capabilities"]
        assert caps["tools"]["listChanged"] is False
        assert caps["resources"]["listChanged"] is False
        assert caps["prompts"]["listChanged"] is False

    def test_server_info(self):
        handler = _make_handler()
        resp = handler._mcp_initialize({})
        assert resp["serverInfo"]["name"] == "LibreMCP"

    def test_instructions_present(self):
        handler = _make_handler()
        resp = handler._mcp_initialize({})
        assert "instructions" in resp
        assert isinstance(resp["instructions"], str)
        assert len(resp["instructions"]) > 0


class TestMcpToolsList:
    def test_returns_schemas(self):
        handler = _make_handler()
        resp = handler._mcp_tools_list({})
        assert "tools" in resp
        assert isinstance(resp["tools"], list)
        for t in resp["tools"]:
            assert "name" in t
            assert "inputSchema" in t

    def test_with_tool_filter(self):
        handler = _make_handler(tool_filter={"set_data", "create_doc"})
        resp = handler._mcp_tools_list({})
        names = [t["name"] for t in resp["tools"]]
        assert set(names) == {"set_data", "create_doc"}

    def test_without_tool_filter(self):
        handler = _make_handler()
        resp = handler._mcp_tools_list({})
        names = [t["name"] for t in resp["tools"]]
        assert "set_data" in names
        assert "create_doc" in names

    def test_filtered_by_doc_type_when_doc_active(self):
        handler = _make_handler()
        doc_svc = handler.services.document
        doc_svc.get_active_document = lambda: "fake_doc"
        doc_svc.detect_doc_type = lambda doc: "writer"
        resp = handler._mcp_tools_list({})
        names = [t["name"] for t in resp["tools"]]
        assert "get_info" in names
        assert "writer_only" in names
        assert "set_data" in names

    def test_no_active_doc_returns_universal(self):
        handler = _make_handler()
        resp = handler._mcp_tools_list({})
        names = [t["name"] for t in resp["tools"]]
        assert "get_info" not in names
        assert "set_data" in names
        assert "create_doc" in names


class TestMcpToolsCall:
    def _patch_and_call(self, handler, params):
        with patch.object(
            handler,
            "_execute_with_backpressure",
            wraps=lambda name, args: handler._execute_tool_on_main(name, dict(args)),
        ):
            msg = {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": params}
            status, resp = handler._process_jsonrpc(msg)
        return status, resp

    def test_successful_call(self):
        handler = _make_handler()
        status, resp = self._patch_and_call(
            handler, {"name": "set_data", "arguments": {"value": "hi"}}
        )
        assert status == 200
        result = resp["result"]
        assert result["isError"] is False
        content = result["content"]
        assert len(content) == 1
        assert content[0]["type"] == "text"
        parsed = json.loads(content[0]["text"])
        assert parsed["status"] == "ok"
        assert parsed["value"] == "hi"

    def test_failed_tool_returns_error(self):
        handler = _make_handler()
        status, resp = self._patch_and_call(
            handler, {"name": "bad_tool", "arguments": {"key": "x"}}
        )
        assert status == 200
        result = resp["result"]
        assert result["isError"] is True
        parsed = json.loads(result["content"][0]["text"])
        assert parsed["status"] == "error"

    def test_unknown_tool(self):
        handler = _make_handler()
        msg = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "nonexistent_tool"},
        }
        with patch.object(
            handler,
            "_execute_with_backpressure",
            wraps=lambda name, args: handler._execute_tool_on_main(name, dict(args)),
        ):
            status, resp = handler._process_jsonrpc(msg)
        assert status == 200
        assert resp["result"]["isError"] is True

    def test_unknown_tool_with_filter(self):
        handler = _make_handler(tool_filter={"set_data"})
        with pytest.raises(ValueError, match="not available"):
            handler._mcp_tools_call({"name": "get_info"})

    def test_tool_filtered_out(self):
        handler = _make_handler(tool_filter={"set_data"})
        with pytest.raises(ValueError, match="not available"):
            handler._mcp_tools_call({"name": "get_info"})

    def test_missing_tool_name(self):
        handler = _make_handler()
        with pytest.raises(ValueError, match="Missing"):
            handler._mcp_tools_call({"arguments": {}})


class TestToolError:
    def test_basic_structure(self):
        err = _tool_error("code_x", "something went wrong")
        assert err["status"] == "error"
        assert err["code"] == "code_x"
        assert err["message"] == "something went wrong"
        assert err["retryable"] is False

    def test_with_hint(self):
        err = _tool_error("not_found", "missing", hint="Try again")
        assert err["hint"] == "Try again"

    def test_retryable_flag(self):
        err = _tool_error("busy", "occupied", retryable=True)
        assert err["retryable"] is True

    def test_no_hint_by_default(self):
        err = _tool_error("x", "y")
        assert "hint" not in err
