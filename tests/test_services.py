import pytest

from plugin.framework.event_bus import EventBus
from plugin.modules.core.services.document import DocumentService, DocumentCache
from plugin.modules.core.services.config import ConfigService
from plugin.modules.writer_nav.services.bookmarks import BookmarkService
from plugin.modules.writer_nav.services.tree import TreeService
from plugin.modules.writer_nav.services.proximity import ProximityService
from plugin.modules.writer_index.services.index import IndexService
from plugin.framework.service_registry import ServiceRegistry

from stubs.writer_stubs import WriterDocStub


class _FakeModel:
    _counter = 0

    def __init__(self, doc_type="writer"):
        self._doc_type = doc_type
        self._services = set()
        if doc_type == "writer":
            self._services.add("com.sun.star.text.TextDocument")
        elif doc_type == "calc":
            self._services.add("com.sun.star.sheet.SpreadsheetDocument")
        elif doc_type == "impress":
            self._services.add("com.sun.star.presentation.PresentationDocument")
            self._services.add("com.sun.star.drawing.DrawingDocument")
        elif doc_type == "draw":
            self._services.add("com.sun.star.drawing.DrawingDocument")
        _FakeModel._counter += 1
        self._url = "test://%s/%d" % (doc_type, _FakeModel._counter)

    def supportsService(self, name):
        return name in self._services

    def getURL(self):
        return self._url

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other


class TestDocumentServiceEvents:
    def test_events_none_before_set_events(self):
        doc_svc = DocumentService()
        assert doc_svc._events is None

    def test_set_events_wires_event_bus(self):
        doc_svc = DocumentService()
        bus = EventBus()
        doc_svc.set_events(bus)
        assert doc_svc._events is bus

    def test_invalidate_cache_emits_event_when_events_wired(self):
        doc_svc = DocumentService()
        bus = EventBus()
        doc_svc.set_events(bus)

        received = []
        bus.subscribe("document:cache_invalidated", lambda **kw: received.append(kw))

        model = _FakeModel("writer")
        DocumentCache._instances.pop(id(model), None)
        doc_svc.invalidate_cache(model)

        assert len(received) == 1
        assert received[0]["doc"] is model

    def test_invalidate_cache_no_event_without_events(self):
        doc_svc = DocumentService()
        received = []
        bus = EventBus()
        bus.subscribe("document:cache_invalidated", lambda **kw: received.append(kw))

        model = _FakeModel("writer")
        DocumentCache._instances.pop(id(model), None)
        doc_svc.invalidate_cache(model)

        assert len(received) == 0

    def test_invalidate_cache_actually_clears_cache(self):
        doc_svc = DocumentService()
        model = _FakeModel("writer")
        DocumentCache._instances.pop(id(model), None)

        cache = DocumentCache.get(model)
        cache.length = 42
        cache.para_ranges = ["a", "b"]

        doc_svc.invalidate_cache(model)

        assert cache.length is None
        assert cache.para_ranges is None


class TestDocumentServiceMethods:
    @pytest.fixture
    def doc_svc(self):
        return DocumentService()

    def test_detect_writer(self, doc_svc):
        assert doc_svc.detect_doc_type(_FakeModel("writer")) == "writer"

    def test_detect_calc(self, doc_svc):
        assert doc_svc.detect_doc_type(_FakeModel("calc")) == "calc"

    def test_detect_impress(self, doc_svc):
        assert doc_svc.detect_doc_type(_FakeModel("impress")) == "impress"

    def test_detect_draw(self, doc_svc):
        assert doc_svc.detect_doc_type(_FakeModel("draw")) == "draw"

    def test_detect_none_for_unknown(self, doc_svc):
        m = _FakeModel("writer")
        m._services.clear()
        assert doc_svc.detect_doc_type(m) is None

    def test_detect_none_for_none_model(self, doc_svc):
        assert doc_svc.detect_doc_type(None) is None

    def test_is_writer(self, doc_svc):
        assert doc_svc.is_writer(_FakeModel("writer")) is True
        assert doc_svc.is_writer(_FakeModel("calc")) is False

    def test_is_calc(self, doc_svc):
        assert doc_svc.is_calc(_FakeModel("calc")) is True
        assert doc_svc.is_calc(_FakeModel("writer")) is False

    def test_is_impress(self, doc_svc):
        assert doc_svc.is_impress(_FakeModel("impress")) is True
        assert doc_svc.is_impress(_FakeModel("draw")) is False

    def test_is_draw(self, doc_svc):
        assert doc_svc.is_draw(_FakeModel("draw")) is True
        assert doc_svc.is_draw(_FakeModel("impress")) is True
        assert doc_svc.is_draw(_FakeModel("writer")) is False

    def test_get_document_length(self, doc_svc):
        doc = WriterDocStub()
        doc.add_paragraph("Hello world")
        doc.add_paragraph("Second paragraph")
        text_obj = doc.getText()
        expected = len(text_obj.getString())
        assert expected > 0

    def test_get_document_length_none_model(self, doc_svc):
        assert doc_svc.get_document_length(None) == 0

    def test_get_paragraph_ranges(self, doc_svc):
        doc = WriterDocStub()
        doc.add_paragraph("First")
        doc.add_paragraph("Second")
        model_id = id(doc)
        DocumentCache._instances.pop(model_id, None)
        ranges = doc_svc.get_paragraph_ranges(doc)
        assert len(ranges) == 2

    def test_doc_key(self, doc_svc):
        model = _FakeModel("writer")
        key = doc_svc.doc_key(model)
        assert key == model.getURL()

    def test_doc_key_with_url(self, doc_svc):
        class ModelWithUrl(_FakeModel):
            def getURL(self):
                return "file:///test.odt"

        key = doc_svc.doc_key(ModelWithUrl("writer"))
        assert key == "file:///test.odt"


class TestBookmarkServiceCohesion:
    def test_cache_invalidated_on_event(self):
        bus = EventBus()
        doc_svc = DocumentService()

        bm_svc = BookmarkService(doc_svc, bus)

        bm_svc._bookmark_cache = {"key1": {"data": True}}

        bus.emit("document:cache_invalidated")

        assert bm_svc._bookmark_cache == {}

    def test_cache_cleared_for_specific_doc(self):
        bus = EventBus()
        doc_svc = DocumentService()

        bm_svc = BookmarkService(doc_svc, bus)

        model = WriterDocStub(url="test://doc1")
        model2 = WriterDocStub(url="test://doc2")
        key1 = doc_svc.doc_key(model)
        key2 = doc_svc.doc_key(model2)

        bm_svc._bookmark_cache = {key1: {"a": 1}, key2: {"b": 2}}

        bus.emit("document:cache_invalidated", doc=model)

        assert key1 not in bm_svc._bookmark_cache
        assert key2 in bm_svc._bookmark_cache


class TestTreeServiceCohesion:
    def test_cache_invalidated_on_event(self):
        bus = EventBus()
        doc_svc = DocumentService()

        class FakeBookmarkSvc:
            name = "writer_bookmarks"

            def get_mcp_bookmark_map(self, doc):
                return {}

        bm_svc = FakeBookmarkSvc()
        tree_svc = TreeService(doc_svc, bm_svc, bus)

        tree_svc._tree_cache = {"key1": {"data": True}}
        tree_svc._ai_summary_cache = {"key1": {"s": "sum"}}

        bus.emit("document:cache_invalidated")

        assert tree_svc._tree_cache == {}
        assert tree_svc._ai_summary_cache == {}

    def test_cache_cleared_for_specific_doc(self):
        bus = EventBus()
        doc_svc = DocumentService()

        class FakeBookmarkSvc:
            name = "writer_bookmarks"

            def get_mcp_bookmark_map(self, doc):
                return {}

        bm_svc = FakeBookmarkSvc()
        tree_svc = TreeService(doc_svc, bm_svc, bus)

        model = WriterDocStub(url="test://doc1")
        model2 = WriterDocStub(url="test://doc2")
        key1 = doc_svc.doc_key(model)
        key2 = doc_svc.doc_key(model2)

        tree_svc._tree_cache = {key1: "t1", key2: "t2"}
        tree_svc._ai_summary_cache = {key1: "s1", key2: "s2"}

        bus.emit("document:cache_invalidated", doc=model)

        assert key1 not in tree_svc._tree_cache
        assert key2 in tree_svc._tree_cache


class TestProximityServiceCohesion:
    def test_cache_invalidated_on_event(self):
        bus = EventBus()
        doc_svc = DocumentService()

        class FakeTreeSvc:
            pass

        class FakeBookmarkSvc:
            pass

        prox_svc = ProximityService(doc_svc, FakeTreeSvc(), FakeBookmarkSvc(), bus)

        prox_svc._flat_cache = {"key1": [{"node": True}]}

        bus.emit("document:cache_invalidated")

        assert prox_svc._flat_cache == {}

    def test_cache_cleared_for_specific_doc(self):
        bus = EventBus()
        doc_svc = DocumentService()

        class FakeTreeSvc:
            pass

        class FakeBookmarkSvc:
            pass

        prox_svc = ProximityService(doc_svc, FakeTreeSvc(), FakeBookmarkSvc(), bus)

        model = WriterDocStub(url="test://doc1")
        model2 = WriterDocStub(url="test://doc2")
        key1 = doc_svc.doc_key(model)
        key2 = doc_svc.doc_key(model2)

        prox_svc._flat_cache = {key1: "a", key2: "b"}

        bus.emit("document:cache_invalidated", doc=model)

        assert key1 not in prox_svc._flat_cache
        assert key2 in prox_svc._flat_cache


class TestIndexServiceCohesion:
    def test_cache_invalidated_on_event(self):
        bus = EventBus()
        doc_svc = DocumentService()

        class FakeTreeSvc:
            def enrich_search_results(self, doc, matches):
                pass

        class FakeBookmarkSvc:
            def get_mcp_bookmark_map(self, doc):
                return {}

        idx_svc = IndexService(doc_svc, FakeTreeSvc(), FakeBookmarkSvc(), bus)

        idx_svc._cache = {"key1": "data"}

        bus.emit("document:cache_invalidated")

        assert idx_svc._cache == {}

    def test_cache_cleared_for_specific_doc(self):
        bus = EventBus()
        doc_svc = DocumentService()

        class FakeTreeSvc:
            def enrich_search_results(self, doc, matches):
                pass

        class FakeBookmarkSvc:
            def get_mcp_bookmark_map(self, doc):
                return {}

        idx_svc = IndexService(doc_svc, FakeTreeSvc(), FakeBookmarkSvc(), bus)

        model = WriterDocStub(url="test://doc1")
        model2 = WriterDocStub(url="test://doc2")
        key1 = doc_svc.doc_key(model)
        key2 = doc_svc.doc_key(model2)

        idx_svc._cache = {key1: "a", key2: "b"}

        bus.emit("document:cache_invalidated", doc=model)

        assert key1 not in idx_svc._cache
        assert key2 in idx_svc._cache


class TestServiceRegistryWiring:
    def test_full_wiring_sequence(self):
        events_svc = EventBus()
        doc_svc = DocumentService()
        config_svc = ConfigService()

        assert doc_svc._events is None
        assert config_svc._events is None

        config_svc.set_events(events_svc)
        doc_svc.set_events(events_svc)

        assert doc_svc._events is events_svc
        assert config_svc._events is events_svc

        received = []
        events_svc.subscribe(
            "document:cache_invalidated", lambda **kw: received.append(kw)
        )

        model = _FakeModel("writer")
        DocumentCache._instances.pop(id(model), None)
        doc_svc.invalidate_cache(model)

        assert len(received) == 1
        assert received[0]["doc"] is model

    def test_config_changed_emits_via_events(self):
        events_svc = EventBus()
        config_svc = ConfigService()
        config_svc.set_events(events_svc)

        config_svc._defaults = {"core.test_key": "default_val"}
        config_svc._manifest = {"core.test_key": {"type": "string"}}

        received = []
        events_svc.subscribe("config:changed", lambda **kw: received.append(kw))

        config_svc._registry_write = lambda key, value: None
        config_svc._registry_read = lambda key: None

        config_svc.set("core.test_key", "new_val")

        assert len(received) == 1
        assert received[0]["key"] == "core.test_key"
        assert received[0]["value"] == "new_val"

    def test_all_services_wired_via_registry(self):
        registry = ServiceRegistry()
        events_svc = EventBus()
        doc_svc = DocumentService()
        config_svc = ConfigService()

        registry.register_instance("events", events_svc)
        registry.register_instance("document", doc_svc)
        registry.register_instance("config", config_svc)

        from plugin.main import bootstrap

        events_svc_from_reg = registry.get("events")
        config_svc.set_events(events_svc_from_reg)
        doc_svc.set_events(events_svc_from_reg)

        assert doc_svc._events is not None
        assert config_svc._events is not None

        doc_received = []
        events_svc.subscribe(
            "document:cache_invalidated", lambda **kw: doc_received.append(kw)
        )

        model = _FakeModel("writer")
        DocumentCache._instances.pop(id(model), None)
        doc_svc.invalidate_cache(model)

        assert len(doc_received) == 1

        bm_svc = BookmarkService(doc_svc, events_svc)
        bm_svc._bookmark_cache = {"key1": "data"}
        events_svc.emit("document:cache_invalidated")
        assert bm_svc._bookmark_cache == {}
