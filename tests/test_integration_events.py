import gc
import threading

import pytest

from plugin.framework.event_bus import EventBus
from plugin.framework.service_registry import ServiceRegistry
from plugin.framework.tool_registry import ToolRegistry
from plugin.framework.tool_context import ToolContext
from plugin.framework.tool_base import ToolBase
from plugin.modules.core.services.document import DocumentService, DocumentCache


class _ModelStub:
    def __init__(self):
        self._services = {
            "com.sun.star.text.TextDocument": False,
            "com.sun.star.sheet.SpreadsheetDocument": False,
            "com.sun.star.presentation.PresentationDocument": False,
            "com.sun.star.drawing.DrawingDocument": False,
        }

    def supportsService(self, name):
        return self._services.get(name, False)

    def getURL(self):
        return ""

    def getPropertyValue(self, name):
        if name == "PageCount":
            return 1
        raise AttributeError(name)


class _FakeTool(ToolBase):
    name = "fake_tool"
    description = "A fake tool for testing"
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
        },
        "required": ["text"],
    }
    doc_types = None

    def __init__(self, result=None, side_effect=None):
        self._result = result or {"status": "ok"}
        self._side_effect = side_effect

    def execute(self, ctx, **kwargs):
        if self._side_effect:
            raise self._side_effect
        return self._result


class _FakeMutatingTool(ToolBase):
    name = "fake_mutate"
    description = "A fake mutating tool"
    parameters = {"type": "object", "properties": {}}
    is_mutation = True

    def execute(self, ctx, **kwargs):
        return {"status": "ok"}


class _FakeSubscriber:
    def __init__(self, cache_attr, initial_value=None):
        setattr(self, cache_attr, initial_value)
        self._cache_attr = cache_attr
        self.cleared = False

    def on_cache_invalidated(self, **kwargs):
        setattr(self, self._cache_attr, None)
        self.cleared = True


class _ThrowingSubscriber:
    def __init__(self, cache_attr, initial_value=None):
        setattr(self, cache_attr, initial_value)
        self.cleared = False

    def on_cache_invalidated(self, **kwargs):
        raise RuntimeError("subscriber error")


class _ConfigChangeListener:
    def __init__(self):
        self.received = []

    def on_config_changed(self, **kwargs):
        self.received.append(kwargs)


class _WeakListener:
    def __init__(self):
        self.calls = []

    def on_event(self, **kwargs):
        self.calls.append(kwargs)


class TestCacheInvalidationChain:
    def test_invalidate_cache_fires_event(self):
        bus = EventBus()
        doc_svc = DocumentService()
        doc_svc.set_events(bus)
        model = _ModelStub()

        received = []
        bus.subscribe("document:cache_invalidated", lambda **kw: received.append(kw))
        doc_svc.invalidate_cache(model)

        assert len(received) == 1
        assert received[0]["doc"] is model

    def test_subscribers_clear_caches(self):
        bus = EventBus()
        doc_svc = DocumentService()
        doc_svc.set_events(bus)
        model = _ModelStub()

        bookmark_sub = _FakeSubscriber("_bookmark_cache", {"b1": "val"})
        tree_sub = _FakeSubscriber("_tree_cache", {"tree": "data"})
        proximity_sub = _FakeSubscriber("_flat_cache", [1, 2, 3])
        index_sub = _FakeSubscriber("_cache", {"idx": "entry"})

        bus.subscribe("document:cache_invalidated", bookmark_sub.on_cache_invalidated)
        bus.subscribe("document:cache_invalidated", tree_sub.on_cache_invalidated)
        bus.subscribe("document:cache_invalidated", proximity_sub.on_cache_invalidated)
        bus.subscribe("document:cache_invalidated", index_sub.on_cache_invalidated)

        doc_svc.invalidate_cache(model)

        assert bookmark_sub._bookmark_cache is None
        assert bookmark_sub.cleared is True
        assert tree_sub._tree_cache is None
        assert tree_sub.cleared is True
        assert proximity_sub._flat_cache is None
        assert proximity_sub.cleared is True
        assert index_sub._cache is None
        assert index_sub.cleared is True

    def test_no_event_without_set_events(self):
        doc_svc = DocumentService()
        model = _ModelStub()

        bus = EventBus()
        received = []
        bus.subscribe("document:cache_invalidated", lambda **kw: received.append(kw))

        doc_svc.invalidate_cache(model)
        assert len(received) == 0

    def test_document_cache_actually_invalidated(self):
        model = _ModelStub()
        cache = DocumentCache.get(model)
        cache.length = 42
        cache.dirty = False

        doc_svc = DocumentService()
        doc_svc.invalidate_cache(model)

        cache_after = DocumentCache.get(model)
        assert cache_after.length is None
        assert cache_after.dirty is True


class TestMultipleSubscribersInvalidation:
    def test_all_subscribers_receive_event(self):
        bus = EventBus()
        doc_svc = DocumentService()
        doc_svc.set_events(bus)
        model = _ModelStub()

        call_log = []
        for i in range(5):
            sub = _FakeSubscriber(f"_cache_{i}", f"data_{i}")
            bus.subscribe("document:cache_invalidated", sub.on_cache_invalidated)
            call_log.append(sub)

        doc_svc.invalidate_cache(model)

        for sub in call_log:
            assert sub.cleared is True

    def test_throwing_subscriber_does_not_affect_others(self):
        bus = EventBus()
        doc_svc = DocumentService()
        doc_svc.set_events(bus)
        model = _ModelStub()

        throwing_sub = _ThrowingSubscriber("_bad_cache", "data")
        good_sub = _FakeSubscriber("_good_cache", "good_data")

        bus.subscribe("document:cache_invalidated", throwing_sub.on_cache_invalidated)
        bus.subscribe("document:cache_invalidated", good_sub.on_cache_invalidated)

        doc_svc.invalidate_cache(model)

        assert good_sub.cleared is True
        assert good_sub._good_cache is None

    def test_independent_cache_clearing(self):
        bus = EventBus()
        doc_svc = DocumentService()
        doc_svc.set_events(bus)
        model = _ModelStub()

        sub_a = _FakeSubscriber("_cache_a", {"a": 1})
        sub_b = _FakeSubscriber("_cache_b", {"b": 2})

        bus.subscribe("document:cache_invalidated", sub_a.on_cache_invalidated)
        bus.subscribe("document:cache_invalidated", sub_b.on_cache_invalidated)

        doc_svc.invalidate_cache(model)

        assert sub_a._cache_a is None
        assert sub_b._cache_b is None
        assert sub_a.cleared is True
        assert sub_b.cleared is True


class TestConfigChangeEventChain:
    def test_config_changed_event_fires(self):
        bus = EventBus()
        listener = _ConfigChangeListener()
        bus.subscribe("config:changed", listener.on_config_changed)

        bus.emit("config:changed", key="mcp.port", value=9000, old_value=8766)

        assert len(listener.received) == 1
        assert listener.received[0]["key"] == "mcp.port"
        assert listener.received[0]["value"] == 9000
        assert listener.received[0]["old_value"] == 8766

    def test_multiple_config_changes(self):
        bus = EventBus()
        listener = _ConfigChangeListener()
        bus.subscribe("config:changed", listener.on_config_changed)

        bus.emit("config:changed", key="mcp.port", value=9000, old_value=8766)
        bus.emit("config:changed", key="mcp.enabled", value=False, old_value=True)

        assert len(listener.received) == 2
        assert listener.received[0]["key"] == "mcp.port"
        assert listener.received[1]["key"] == "mcp.enabled"

    def test_config_service_emits_on_set(self):
        bus = EventBus()
        received = []
        bus.subscribe("config:changed", lambda **kw: received.append(kw))

        bus.emit("config:changed", key="mcp.port", value=9000)
        assert len(received) == 1
        assert received[0]["key"] == "mcp.port"
        assert received[0]["value"] == 9000

        bus.emit("config:changed", key="mcp.enabled", value=True)
        assert len(received) == 2
        assert received[1]["key"] == "mcp.enabled"


class TestToolLifecycleEvents:
    def _make_registry_and_bus(self):
        bus = EventBus()
        services = ServiceRegistry()
        services.register_instance("events", bus)
        doc_svc = DocumentService()
        doc_svc.set_events(bus)
        services.register_instance("document", doc_svc)
        registry = ToolRegistry(services)
        return registry, bus, services

    def test_executing_then_completed(self):
        registry, bus, services = self._make_registry_and_bus()
        tool = _FakeTool(result={"status": "ok", "data": "hello"})
        registry.register(tool)

        events = []
        bus.subscribe("tool:executing", lambda **kw: events.append(("executing", kw)))
        bus.subscribe("tool:completed", lambda **kw: events.append(("completed", kw)))

        ctx = ToolContext(
            doc=None, ctx=None, doc_type=None, services=services, caller="test"
        )
        result = registry.execute("fake_tool", ctx, text="hello")

        assert result["status"] == "ok"
        assert len(events) == 2
        assert events[0][0] == "executing"
        assert events[0][1]["name"] == "fake_tool"
        assert events[0][1]["kwargs"] == {"text": "hello"}
        assert events[1][0] == "completed"
        assert events[1][1]["name"] == "fake_tool"
        assert events[1][1]["result"]["status"] == "ok"

    def test_failed_on_unknown_tool(self):
        registry, bus, services = self._make_registry_and_bus()

        events = []
        bus.subscribe("tool:failed", lambda **kw: events.append(kw))

        ctx = ToolContext(
            doc=None, ctx=None, doc_type=None, services=services, caller="test"
        )
        with pytest.raises(KeyError):
            registry.execute("nonexistent", ctx)

        assert len(events) == 0

    def test_failed_on_invalid_params(self):
        registry, bus, services = self._make_registry_and_bus()
        tool = _FakeTool()
        registry.register(tool)

        events = []
        bus.subscribe("tool:failed", lambda **kw: events.append(kw))

        ctx = ToolContext(
            doc=None, ctx=None, doc_type=None, services=services, caller="test"
        )
        result = registry.execute("fake_tool", ctx)

        assert result["status"] == "error"
        assert result["code"] == "invalid_params"
        assert len(events) == 1
        assert events[0]["name"] == "fake_tool"
        assert "Missing required parameter" in events[0]["error"]

    def test_failed_on_exception(self):
        registry, bus, services = self._make_registry_and_bus()
        tool = _FakeTool(side_effect=RuntimeError("tool crash"))
        registry.register(tool)

        events = []
        bus.subscribe("tool:failed", lambda **kw: events.append(kw))

        ctx = ToolContext(
            doc=None, ctx=None, doc_type=None, services=services, caller="mcp"
        )
        result = registry.execute("fake_tool", ctx, text="boom")

        assert result["status"] == "error"
        assert result["code"] == "execution_error"
        assert len(events) == 1
        assert events[0]["name"] == "fake_tool"
        assert "tool crash" in events[0]["error"]
        assert events[0]["caller"] == "mcp"

    def test_completed_payload_has_is_mutation(self):
        registry, bus, services = self._make_registry_and_bus()
        tool = _FakeMutatingTool()
        registry.register(tool)

        events = []
        bus.subscribe("tool:completed", lambda **kw: events.append(kw))

        ctx = ToolContext(
            doc=None, ctx=None, doc_type=None, services=services, caller="test"
        )
        registry.execute("fake_mutate", ctx)

        assert len(events) == 1
        assert events[0]["is_mutation"] is True


class TestEventBusWeakReferences:
    def test_weak_subscriber_auto_cleanup(self):
        bus = EventBus()
        listener = _WeakListener()
        bus.subscribe("test:event", listener.on_event, weak=True)

        bus.emit("test:event", data="first")
        assert len(listener.calls) == 1

        del listener
        gc.collect()

        bus.emit("test:event", data="second")

    def test_strong_subscriber_survives(self):
        bus = EventBus()
        listener = _WeakListener()
        bus.subscribe("test:event", listener.on_event, weak=False)

        bus.emit("test:event", data="first")
        assert len(listener.calls) == 1

        ref = listener
        del listener
        gc.collect()

        bus.emit("test:event", data="second")
        assert len(ref.calls) == 2

    def test_no_errors_from_dead_weakrefs(self):
        bus = EventBus()

        class TempListener:
            def on_event(self, **kw):
                pass

        obj = TempListener()
        bus.subscribe("evt", obj.on_event, weak=True)
        del obj
        gc.collect()

        bus.emit("evt", data="safe")


class TestConcurrentEventEmission:
    def test_concurrent_emits_all_processed(self):
        bus = EventBus()
        results = []
        lock = threading.Lock()

        def handler(**kw):
            with lock:
                results.append(kw["idx"])

        bus.subscribe("concurrent", handler)

        threads = []
        for i in range(50):
            t = threading.Thread(
                target=bus.emit, args=("concurrent",), kwargs={"idx": i}
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 50
        assert set(results) == set(range(50))

    def test_concurrent_no_exceptions(self):
        bus = EventBus()
        received = []

        def handler(**kw):
            received.append(1)

        bus.subscribe("multi", handler)

        errors = []

        def worker(i):
            try:
                bus.emit("multi", idx=i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(received) == 100


class TestBootstrapWiringSequence:
    def test_set_events_wiring(self):
        services = ServiceRegistry()
        bus = EventBus()
        doc_svc = DocumentService()
        config_svc = __import__(
            "plugin.modules.core.services.config", fromlist=["ConfigService"]
        ).ConfigService()
        config_svc.set_events(bus)

        services.register_instance("events", bus)
        services.register_instance("document", doc_svc)
        services.register_instance("config", config_svc)

        doc_svc.set_events(bus)

        assert doc_svc._events is bus
        assert config_svc._events is bus

    def test_invalidate_after_wiring_fires_event(self):
        services = ServiceRegistry()
        bus = EventBus()
        doc_svc = DocumentService()
        doc_svc.set_events(bus)
        services.register_instance("events", bus)
        services.register_instance("document", doc_svc)

        received = []
        bus.subscribe("document:cache_invalidated", lambda **kw: received.append(kw))

        model = _ModelStub()
        doc_svc.invalidate_cache(model)

        assert len(received) == 1
        assert received[0]["doc"] is model

    def test_subscribers_receive_after_bootstrap_wiring(self):
        services = ServiceRegistry()
        bus = EventBus()
        doc_svc = DocumentService()
        doc_svc.set_events(bus)
        services.register_instance("events", bus)
        services.register_instance("document", doc_svc)

        bookmark_sub = _FakeSubscriber("_bookmark_cache", {"b1": "val"})
        tree_sub = _FakeSubscriber("_tree_cache", {"tree": True})
        index_sub = _FakeSubscriber("_cache", {"entries": []})

        bus.subscribe("document:cache_invalidated", bookmark_sub.on_cache_invalidated)
        bus.subscribe("document:cache_invalidated", tree_sub.on_cache_invalidated)
        bus.subscribe("document:cache_invalidated", index_sub.on_cache_invalidated)

        model = _ModelStub()
        doc_svc.invalidate_cache(model)

        assert bookmark_sub._bookmark_cache is None
        assert tree_sub._tree_cache is None
        assert index_sub._cache is None

    def test_phase_1a_bug_fix_set_events_called(self):
        doc_svc = DocumentService()
        assert doc_svc._events is None

        bus = EventBus()
        doc_svc.set_events(bus)
        assert doc_svc._events is bus

        model = _ModelStub()
        received = []
        bus.subscribe("document:cache_invalidated", lambda **kw: received.append(kw))

        doc_svc.invalidate_cache(model)
        assert len(received) == 1
