import pytest

from plugin.framework.tool_base import ToolBase
from plugin.framework.tool_context import ToolContext
from plugin.framework.tool_registry import ToolRegistry, _flatten_doc_type_params
from plugin.framework.service_registry import ServiceRegistry
from plugin.framework.event_bus import EventBus


class GetDocTool(ToolBase):
    name = "get_document_info"
    description = "Gets document info"
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        return {"status": "ok", "path": kwargs.get("path", "")}


class InsertTextTool(ToolBase):
    name = "insert_text"
    description = "Inserts text"
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        return {"status": "ok", "inserted": kwargs["text"]}


class CalcTool(ToolBase):
    name = "get_cell_value"
    description = "Gets cell value"
    parameters = {
        "type": "object",
        "properties": {"cell": {"type": "string"}},
    }
    doc_types = ["calc"]

    def execute(self, ctx, **kwargs):
        return {"status": "ok", "value": kwargs.get("cell", "")}


class UniversalTool(ToolBase):
    name = "get_metadata"
    description = "Gets metadata"
    parameters = {"type": "object", "properties": {}}
    doc_types = None

    def execute(self, ctx, **kwargs):
        return {"status": "ok", "meta": True}


class ApplyFormatTool(ToolBase):
    name = "apply_format"
    description = "Applies formatting"
    parameters = {"type": "object", "properties": {}}
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        return {"status": "ok", "formatted": True}


class DeleteTextTool(ToolBase):
    name = "delete_text"
    description = "Deletes text"
    parameters = {"type": "object", "properties": {}}
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        return {"status": "ok", "deleted": True}


class ExplicitNonMutationTool(ToolBase):
    name = "get_special"
    description = "A read tool with explicit is_mutation override"
    is_mutation = False
    parameters = {"type": "object", "properties": {}}
    doc_types = None

    def execute(self, ctx, **kwargs):
        return {"status": "ok"}


class ServiceRequiringTool(ToolBase):
    name = "use_gallery"
    description = "Uses gallery"
    parameters = {"type": "object", "properties": {}}
    doc_types = None
    requires_service = "images"

    def execute(self, ctx, **kwargs):
        return {"status": "ok"}


class FailingExecuteTool(ToolBase):
    name = "boom"
    description = "Always raises"
    parameters = {"type": "object", "properties": {}}
    doc_types = None

    def execute(self, ctx, **kwargs):
        raise RuntimeError("kaboom")


class _FakeUndoMgr:
    def __init__(self):
        self.contexts = []

    def enterUndoContext(self, title):
        self.contexts.append(("enter", title))

    def leaveUndoContext(self):
        self.contexts.append(("leave",))


class _FakeDoc:
    def __init__(self, undo_mgr=None):
        self._undo_mgr = undo_mgr
        self.track_changes_enabled = False

    def getUndoManager(self):
        if self._undo_mgr is None:
            raise RuntimeError("no undo manager")
        return self._undo_mgr

    def getPropertyValue(self, key):
        if key == "RecordChanges":
            return self.track_changes_enabled

    def setPropertyValue(self, key, value):
        if key == "RecordChanges":
            self.track_changes_enabled = value


class _FakeConfigProxy:
    def __init__(self, data=None):
        self._data = data or {}

    def get(self, key, default=None):
        return self._data.get(key, default)


class _FakeConfigService:
    name = "config"

    def __init__(self, force_track_changes=False):
        self._proxy = _FakeConfigProxy({"force_track_changes": force_track_changes})

    def proxy_for(self, module):
        return self._proxy


class _FakeDocumentService:
    name = "document"

    def __init__(self):
        self.invalidations = []

    def invalidate_cache(self, doc):
        self.invalidations.append(doc)


def _make_services(**overrides):
    services = ServiceRegistry()
    bus = EventBus()
    services.register_instance("events", bus)
    for name, svc in overrides.items():
        services.register_instance(name, svc)
    return services


def _make_ctx(doc_type="writer", caller="test", doc=None, services=None):
    if services is None:
        services = _make_services()
    return ToolContext(
        doc=doc,
        ctx=None,
        doc_type=doc_type,
        services=services,
        caller=caller,
    )


class TestFlattenDocTypeParams:
    def test_writer_params_merged(self):
        result = _flatten_doc_type_params(
            {"writer": {"locator": "para 1"}, "text": "hello"},
            "writer",
        )
        assert result == {"locator": "para 1", "text": "hello"}

    def test_calc_params_merged(self):
        result = _flatten_doc_type_params(
            {"calc": {"sheet": "Sheet1"}, "cell": "A1"},
            "calc",
        )
        assert result == {"sheet": "Sheet1", "cell": "A1"}

    def test_other_doc_type_blocks_discarded(self):
        result = _flatten_doc_type_params(
            {
                "writer": {"locator": "para 1"},
                "calc": {"sheet": "Sheet1"},
                "text": "hello",
            },
            "writer",
        )
        assert result == {"locator": "para 1", "text": "hello"}
        assert "sheet" not in result

    def test_non_doc_type_params_pass_through(self):
        result = _flatten_doc_type_params(
            {"path": "/tmp/file.odt", "verbose": True},
            "writer",
        )
        assert result == {"path": "/tmp/file.odt", "verbose": True}

    def test_nested_non_doc_type_keys_pass_through(self):
        result = _flatten_doc_type_params(
            {"options": {"format": "pdf"}, "writer": {"style": "Heading 1"}},
            "writer",
        )
        assert result == {"options": {"format": "pdf"}, "style": "Heading 1"}

    def test_empty_kwargs(self):
        result = _flatten_doc_type_params({}, "writer")
        assert result == {}

    def test_doc_type_block_not_a_dict_is_discarded(self):
        result = _flatten_doc_type_params(
            {"writer": "not a dict"},
            "writer",
        )
        assert result == {}


class TestDispatchDocTypeFiltering:
    def test_reject_incompatible_doc_type(self):
        services = _make_services()
        reg = ToolRegistry(services)
        reg.register(GetDocTool())
        ctx = _make_ctx(doc_type="calc", services=services)
        result = reg.execute("get_document_info", ctx, path="/tmp/test.odt")
        assert result["status"] == "error"
        assert result["code"] == "incompatible_doc_type"

    def test_accept_compatible_doc_type(self):
        services = _make_services()
        reg = ToolRegistry(services)
        reg.register(GetDocTool())
        ctx = _make_ctx(doc_type="writer", services=services)
        result = reg.execute("get_document_info", ctx, path="/tmp/test.odt")
        assert result["status"] == "ok"

    def test_universal_tool_works_for_any_doc_type(self):
        services = _make_services()
        reg = ToolRegistry(services)
        reg.register(UniversalTool())
        for dt in ("writer", "calc", "impress", "draw"):
            ctx = _make_ctx(doc_type=dt, services=services)
            result = reg.execute("get_metadata", ctx)
            assert result["status"] == "ok", f"Failed for doc_type={dt}"

    def test_error_includes_hint_and_retryable(self):
        services = _make_services()
        reg = ToolRegistry(services)
        reg.register(GetDocTool())
        ctx = _make_ctx(doc_type="calc", services=services)
        result = reg.execute("get_document_info", ctx, path="/tmp/test.odt")
        assert "hint" in result
        assert "retryable" in result
        assert result["retryable"] is False


class TestDispatchParameterValidation:
    def test_missing_required_params_returns_error(self):
        services = _make_services()
        reg = ToolRegistry(services)
        reg.register(InsertTextTool())
        ctx = _make_ctx(doc_type="writer", services=services)
        result = reg.execute("insert_text", ctx)
        assert result["status"] == "error"
        assert result["code"] == "invalid_params"
        assert "Missing required" in result["message"]

    def test_valid_params_execute_successfully(self):
        services = _make_services()
        reg = ToolRegistry(services)
        reg.register(InsertTextTool())
        ctx = _make_ctx(doc_type="writer", services=services)
        result = reg.execute("insert_text", ctx, text="hello")
        assert result["status"] == "ok"
        assert result["inserted"] == "hello"

    def test_unknown_param_rejected(self):
        services = _make_services()
        reg = ToolRegistry(services)
        reg.register(GetDocTool())
        ctx = _make_ctx(doc_type="writer", services=services)
        result = reg.execute("get_document_info", ctx, path="/a", bogus="x")
        assert result["status"] == "error"
        assert result["code"] == "invalid_params"


class TestDispatchEventEmission:
    def test_executing_emitted_before_execution(self):
        bus = EventBus()
        events = []
        bus.subscribe("tool:executing", lambda **kw: events.append(("executing", kw)))
        services = ServiceRegistry()
        services.register_instance("events", bus)
        reg = ToolRegistry(services)
        reg.register(GetDocTool())
        ctx = _make_ctx(doc_type="writer", services=services, caller="mcp")
        reg.execute("get_document_info", ctx, path="/tmp/x")
        assert len(events) == 1
        assert events[0][0] == "executing"
        kw = events[0][1]
        assert kw["name"] == "get_document_info"
        assert kw["caller"] == "mcp"
        assert "path" in kw["kwargs"]

    def test_completed_emitted_after_execution(self):
        bus = EventBus()
        events = []
        bus.subscribe("tool:completed", lambda **kw: events.append(("completed", kw)))
        services = ServiceRegistry()
        services.register_instance("events", bus)
        reg = ToolRegistry(services)
        reg.register(GetDocTool())
        ctx = _make_ctx(doc_type="writer", services=services)
        reg.execute("get_document_info", ctx, path="/tmp/x")
        assert len(events) == 1
        kw = events[0][1]
        assert kw["name"] == "get_document_info"
        assert kw["is_mutation"] is False
        assert kw["result"]["status"] == "ok"

    def test_failed_emitted_on_validation_failure(self):
        bus = EventBus()
        events = []
        bus.subscribe("tool:failed", lambda **kw: events.append(("failed", kw)))
        services = ServiceRegistry()
        services.register_instance("events", bus)
        reg = ToolRegistry(services)
        reg.register(InsertTextTool())
        ctx = _make_ctx(doc_type="writer", services=services)
        reg.execute("insert_text", ctx)
        assert len(events) == 1
        kw = events[0][1]
        assert kw["name"] == "insert_text"
        assert "Missing required" in kw["error"]

    def test_failed_emitted_on_incompatible_doc_type(self):
        bus = EventBus()
        events = []
        bus.subscribe("tool:failed", lambda **kw: events.append(("failed", kw)))
        services = ServiceRegistry()
        services.register_instance("events", bus)
        reg = ToolRegistry(services)
        reg.register(GetDocTool())
        ctx = _make_ctx(doc_type="calc", services=services)
        reg.execute("get_document_info", ctx)
        assert len(events) == 1
        kw = events[0][1]
        assert kw["name"] == "get_document_info"
        assert "calc" in kw["error"]

    def test_failed_emitted_on_execution_exception(self):
        bus = EventBus()
        events = []
        bus.subscribe("tool:failed", lambda **kw: events.append(("failed", kw)))
        services = ServiceRegistry()
        services.register_instance("events", bus)
        reg = ToolRegistry(services)
        reg.register(FailingExecuteTool())
        ctx = _make_ctx(doc_type="writer", services=services)
        reg.execute("boom", ctx)
        assert len(events) == 1
        kw = events[0][1]
        assert kw["name"] == "boom"
        assert "kaboom" in kw["error"]


class TestDispatchMutationTracking:
    def test_mutation_tool_gets_action_id(self):
        undo_mgr = _FakeUndoMgr()
        doc = _FakeDoc(undo_mgr=undo_mgr)
        services = _make_services()
        reg = ToolRegistry(services)
        reg.register(InsertTextTool())
        ctx = _make_ctx(doc_type="writer", doc=doc, services=services)
        result = reg.execute("insert_text", ctx, text="hello")
        assert "_action_id" in result
        assert isinstance(result["_action_id"], str)

    def test_non_mutation_tool_no_action_id(self):
        services = _make_services()
        reg = ToolRegistry(services)
        reg.register(GetDocTool())
        ctx = _make_ctx(doc_type="writer", services=services)
        result = reg.execute("get_document_info", ctx, path="/tmp")
        assert "_action_id" not in result

    def test_mutation_detected_from_name_prefix(self):
        assert InsertTextTool().detects_mutation() is True
        assert ApplyFormatTool().detects_mutation() is True
        assert DeleteTextTool().detects_mutation() is True
        assert GetDocTool().detects_mutation() is False

    def test_undo_context_entered_and_left(self):
        undo_mgr = _FakeUndoMgr()
        doc = _FakeDoc(undo_mgr=undo_mgr)
        services = _make_services()
        reg = ToolRegistry(services)
        reg.register(InsertTextTool())
        ctx = _make_ctx(doc_type="writer", doc=doc, services=services)
        reg.execute("insert_text", ctx, text="hello")
        enters = [e for e in undo_mgr.contexts if e[0] == "enter"]
        leaves = [e for e in undo_mgr.contexts if e[0] == "leave"]
        assert len(enters) == 1
        assert len(leaves) == 1
        assert "LibreMCP: insert_text" in enters[0][1]

    def test_track_changes_auto_enabled_for_mcp(self):
        undo_mgr = _FakeUndoMgr()
        doc = _FakeDoc(undo_mgr=undo_mgr)
        doc.track_changes_enabled = False
        config_svc = _FakeConfigService(force_track_changes=True)
        services = _make_services()
        services.register_instance("config", config_svc)
        reg = ToolRegistry(services)
        reg.register(InsertTextTool())
        ctx = _make_ctx(doc_type="writer", doc=doc, services=services, caller="mcp")
        reg.execute("insert_text", ctx, text="hello")
        assert doc.track_changes_enabled is True

    def test_track_changes_not_enabled_when_config_off(self):
        undo_mgr = _FakeUndoMgr()
        doc = _FakeDoc(undo_mgr=undo_mgr)
        doc.track_changes_enabled = False
        config_svc = _FakeConfigService(force_track_changes=False)
        services = _make_services()
        services.register_instance("config", config_svc)
        reg = ToolRegistry(services)
        reg.register(InsertTextTool())
        ctx = _make_ctx(doc_type="writer", doc=doc, services=services, caller="mcp")
        reg.execute("insert_text", ctx, text="hello")
        assert doc.track_changes_enabled is False

    def test_track_changes_not_enabled_for_non_mcp_caller(self):
        undo_mgr = _FakeUndoMgr()
        doc = _FakeDoc(undo_mgr=undo_mgr)
        doc.track_changes_enabled = False
        config_svc = _FakeConfigService(force_track_changes=True)
        services = _make_services()
        services.register_instance("config", config_svc)
        reg = ToolRegistry(services)
        reg.register(InsertTextTool())
        ctx = _make_ctx(doc_type="writer", doc=doc, services=services, caller="chatbot")
        reg.execute("insert_text", ctx, text="hello")
        assert doc.track_changes_enabled is False


class TestDispatchCacheInvalidation:
    def test_mutation_invalidates_cache(self):
        doc_svc = _FakeDocumentService()
        services = _make_services()
        services.register_instance("document", doc_svc)
        reg = ToolRegistry(services)
        reg.register(InsertTextTool())
        ctx = _make_ctx(doc_type="writer", services=services)
        reg.execute("insert_text", ctx, text="hello")
        assert len(doc_svc.invalidations) == 1

    def test_batch_mode_suppresses_cache_invalidation(self):
        doc_svc = _FakeDocumentService()
        services = _make_services()
        services.register_instance("document", doc_svc)
        reg = ToolRegistry(services)
        reg.batch_mode = True
        reg.register(InsertTextTool())
        ctx = _make_ctx(doc_type="writer", services=services)
        reg.execute("insert_text", ctx, text="hello")
        assert len(doc_svc.invalidations) == 0

    def test_non_mutation_no_cache_invalidation(self):
        doc_svc = _FakeDocumentService()
        services = _make_services()
        services.register_instance("document", doc_svc)
        reg = ToolRegistry(services)
        reg.register(GetDocTool())
        ctx = _make_ctx(doc_type="writer", services=services)
        reg.execute("get_document_info", ctx, path="/tmp")
        assert len(doc_svc.invalidations) == 0

    def test_cache_invalidation_emits_event(self):
        doc_svc = _FakeDocumentService()
        bus = EventBus()
        cache_events = []
        bus.subscribe(
            "document:cache_invalidated", lambda **kw: cache_events.append(kw)
        )
        services = ServiceRegistry()
        services.register_instance("events", bus)
        services.register_instance("document", doc_svc)

        class CacheEventDocService(_FakeDocumentService):
            def __init__(self, bus):
                super().__init__()
                self._bus = bus

            def invalidate_cache(self, doc):
                super().invalidate_cache(doc)
                self._bus.emit("document:cache_invalidated", doc=doc)

        event_doc_svc = CacheEventDocService(bus)
        services = ServiceRegistry()
        services.register_instance("events", bus)
        services.register_instance("document", event_doc_svc)
        reg = ToolRegistry(services)
        reg.register(InsertTextTool())
        ctx = _make_ctx(doc_type="writer", services=services)
        reg.execute("insert_text", ctx, text="hello")
        assert len(cache_events) == 1


class TestToolsForDocType:
    def test_filter_returns_compatible_only(self):
        services = _make_services()
        reg = ToolRegistry(services)
        reg.register(GetDocTool())
        reg.register(CalcTool())
        reg.register(UniversalTool())
        names = [t.name for t in reg.tools_for_doc_type("writer")]
        assert "get_document_info" in names
        assert "get_cell_value" not in names
        assert "get_metadata" in names

    def test_filter_for_calc(self):
        services = _make_services()
        reg = ToolRegistry(services)
        reg.register(GetDocTool())
        reg.register(CalcTool())
        reg.register(UniversalTool())
        names = [t.name for t in reg.tools_for_doc_type("calc")]
        assert "get_document_info" not in names
        assert "get_cell_value" in names
        assert "get_metadata" in names

    def test_universal_tools_always_included(self):
        services = _make_services()
        reg = ToolRegistry(services)
        reg.register(UniversalTool())
        for dt in ("writer", "calc", "draw", "impress", None):
            names = [t.name for t in reg.tools_for_doc_type(dt)]
            assert "get_metadata" in names

    def test_mcp_schemas_are_valid(self):
        services = _make_services()
        reg = ToolRegistry(services)
        reg.register(GetDocTool())
        reg.register(UniversalTool())
        schemas = reg.get_mcp_schemas("writer")
        assert len(schemas) == 2
        for s in schemas:
            assert "name" in s
            assert "description" in s
            assert "inputSchema" in s
            assert s["inputSchema"]["type"] == "object"

    def test_requires_service_filtering(self):
        services = _make_services()
        reg = ToolRegistry(services)
        reg.register(ServiceRequiringTool())
        names = [t.name for t in reg.tools_for_doc_type("writer")]
        assert "use_gallery" not in names

    def test_requires_service_included_when_available(self):
        services = _make_services()

        class FakeImagesService:
            name = "images"

            def list_instances(self):
                return ["default"]

        services.register_instance("images", FakeImagesService())
        reg = ToolRegistry(services)
        reg.register(ServiceRequiringTool())
        names = [t.name for t in reg.tools_for_doc_type("writer")]
        assert "use_gallery" in names
