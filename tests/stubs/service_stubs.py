from plugin.framework.service_registry import ServiceRegistry
from plugin.framework.event_bus import EventBus


class StubDocumentService:
    name = "document"

    def __init__(self, doc=None):
        self._doc = doc
        self._cache = {}
        self._para_ranges_cache = {}

    def detect_doc_type(self, model):
        for svc_name, doc_type in [
            ("com.sun.star.text.TextDocument", "writer"),
            ("com.sun.star.sheet.SpreadsheetDocument", "calc"),
            ("com.sun.star.presentation.PresentationDocument", "impress"),
            ("com.sun.star.drawing.DrawingDocument", "draw"),
        ]:
            if hasattr(model, "supportsService") and model.supportsService(svc_name):
                return doc_type
        return None

    def is_writer(self, model):
        return hasattr(model, "supportsService") and model.supportsService(
            "com.sun.star.text.TextDocument"
        )

    def is_calc(self, model):
        return hasattr(model, "supportsService") and model.supportsService(
            "com.sun.star.sheet.SpreadsheetDocument"
        )

    def is_draw(self, model):
        try:
            return model.supportsService("com.sun.star.drawing.DrawingDocument")
        except Exception:
            return False

    def is_impress(self, model):
        try:
            return model.supportsService(
                "com.sun.star.presentation.PresentationDocument"
            )
        except Exception:
            return False

    def get_paragraph_ranges(self, model):
        mid = id(model)
        if mid in self._para_ranges_cache:
            return self._para_ranges_cache[mid]
        if hasattr(model, "getText"):
            text = model.getText()
            if hasattr(text, "createEnumeration"):
                enum = text.createEnumeration()
                ranges = []
                while enum.hasMoreElements():
                    ranges.append(enum.nextElement())
                self._para_ranges_cache[mid] = ranges
                return ranges
        return []

    def find_paragraph_element(self, model, para_index):
        para_ranges = self.get_paragraph_ranges(model)
        if para_index < len(para_ranges):
            return para_ranges[para_index], len(para_ranges)
        return None, len(para_ranges)

    def build_heading_tree(self, model):
        paragraph_ranges = self.get_paragraph_ranges(model)
        headings = []
        for idx, para in enumerate(paragraph_ranges):
            if hasattr(para, "getPropertyValue"):
                try:
                    outline_level = para.getPropertyValue("OutlineLevel")
                    if outline_level and outline_level > 0:
                        text = para.getString() if hasattr(para, "getString") else ""
                        headings.append(
                            {
                                "level": outline_level,
                                "text": text.strip(),
                                "para_index": idx,
                                "children": [],
                            }
                        )
                except Exception:
                    continue
        return _nest_headings(headings)

    def resolve_locator(self, model, locator):
        loc_type, sep, loc_value = locator.partition(":")
        if not sep:
            raise ValueError("Invalid locator format: '%s'" % locator)
        result = {
            "locator_type": loc_type,
            "locator_value": loc_value,
            "confidence": "exact",
        }
        if loc_type == "paragraph":
            result["para_index"] = int(loc_value)
        elif loc_type == "first":
            result["para_index"] = 0
        elif loc_type == "last":
            para_ranges = self.get_paragraph_ranges(model)
            result["para_index"] = max(0, len(para_ranges) - 1)
        else:
            raise ValueError("Unknown locator type: '%s'" % loc_type)
        return result

    def get_document_length(self, model):
        if hasattr(model, "getText"):
            text = model.getText()
            if hasattr(text, "getString"):
                return len(text.getString())
        return 0

    def invalidate_cache(self, model):
        mid = id(model)
        self._para_ranges_cache.pop(mid, None)

    def get_page_count(self, model):
        if hasattr(model, "getPropertyValue"):
            try:
                return model.getPropertyValue("PageCount") or 1
            except Exception:
                pass
        return 1

    def get_doc_id(self, model):
        return "stub-doc-id-%d" % id(model)

    def doc_key(self, model):
        if hasattr(model, "getURL"):
            try:
                return model.getURL() or str(id(model))
            except Exception:
                pass
        return str(id(model))

    def yield_to_gui(self, every=50):
        pass

    def get_default_save_dir(self):
        import os

        return os.path.expanduser("~")

    def get_active_document(self):
        return self._doc

    def enumerate_open_documents(self, active_model=None):
        return []


class StubConfigService:
    name = "config"

    def __init__(self):
        self._values = {}

    def get(self, key, default=None, caller_module=None):
        return self._values.get(key, default)

    def set(self, key, value, caller_module=None):
        self._values[key] = value

    def set_manifest(self, manifest):
        pass

    def proxy_for(self, module_name):
        return _StubConfigProxy(self, module_name)


class _StubConfigProxy:
    def __init__(self, config_svc, module_name):
        self._svc = config_svc
        self._prefix = module_name

    def get(self, key, default=None):
        full = "%s.%s" % (self._prefix, key) if "." not in key else key
        return self._svc.get(full, default)

    def set(self, key, value):
        full = "%s.%s" % (self._prefix, key) if "." not in key else key
        self._svc.set(full, value)

    def remove(self, key):
        pass


class StubEventBus:
    def __init__(self):
        self._subscribers = {}
        self._calls = []

    def subscribe(self, event, callback, weak=False):
        self._subscribers.setdefault(event, []).append(callback)

    def emit(self, event, **kwargs):
        self._calls.append((event, kwargs))
        for cb in self._subscribers.get(event, []):
            try:
                cb(**kwargs)
            except Exception:
                pass

    @property
    def calls(self):
        return self._calls


class StubTreeService:
    name = "writer_tree"

    def __init__(self, doc_svc=None):
        self._doc_svc = doc_svc

    def build_heading_tree(self, doc):
        if self._doc_svc:
            return self._doc_svc.build_heading_tree(doc)
        return []

    def _find_node_by_para_index(self, tree, para_index):
        for node in tree:
            if node.get("para_index") == para_index:
                return node
            result = self._find_node_by_para_index(node.get("children", []), para_index)
            if result:
                return result
        return None

    def _count_all_children(self, node):
        count = len(node.get("children", []))
        for child in node.get("children", []):
            count += self._count_all_children(child)
        return count

    def find_heading_for_paragraph(self, doc, para_index):
        return None

    def enrich_search_results(self, doc, matches):
        pass


class StubBookmarkService:
    name = "writer_bookmarks"

    def __init__(self):
        self._bookmark_map = {}

    def get_mcp_bookmark_map(self, doc):
        return self._bookmark_map

    def set_bookmark_map(self, mapping):
        self._bookmark_map = mapping


class StubProximityService:
    name = "writer_proximity"

    def find_nearby_paragraphs(self, doc, para_index, count=3):
        return []


class StubFormatService:
    name = "format"

    def export_as_text(self, model, max_chars=None):
        if hasattr(model, "getText"):
            text = model.getText()
            if hasattr(text, "getString"):
                content = text.getString()
                if max_chars and len(content) > max_chars:
                    content = content[:max_chars]
                return content
        return ""


class StubToolRegistry:
    name = "tools"

    def __init__(self):
        self._tools = {}

    def register(self, tool):
        self._tools[tool.name] = tool

    def get(self, name):
        return self._tools.get(name)

    @property
    def tool_names(self):
        return list(self._tools.keys())


class StubServiceRegistry(ServiceRegistry):
    def __init__(self, doc=None):
        super().__init__()
        doc_svc = StubDocumentService(doc)
        events = StubEventBus()
        config_svc = StubConfigService()
        tree_svc = StubTreeService(doc_svc)
        bm_svc = StubBookmarkService()
        prox_svc = StubProximityService()
        fmt_svc = StubFormatService()
        tools_svc = StubToolRegistry()

        self.register_instance("document", doc_svc)
        self.register_instance("config", config_svc)
        self.register_instance("events", events)
        self.register_instance("writer_tree", tree_svc)
        self.register_instance("writer_bookmarks", bm_svc)
        self.register_instance("writer_proximity", prox_svc)
        self.register_instance("format", fmt_svc)
        self.register_instance("tools", tools_svc)


def _nest_headings(flat):
    if not flat:
        return []
    root = []
    stack = []
    for h in flat:
        node = dict(h)
        node["children"] = []
        while stack and stack[-1][0] >= h["level"]:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            root.append(node)
        stack.append((h["level"], node))
    return root
