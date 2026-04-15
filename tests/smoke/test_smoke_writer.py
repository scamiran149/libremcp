"""Smoke tests for Writer tools via live MCP server.

Uses the currently open Writer document. No document creation.
Requires LibreOffice + LibreMCP running at localhost:9876.
"""

import pytest

from .conftest import call_tool


class TestWriterReadTools:
    """Read-only tools — safe, no mutations."""

    def test_get_document_content(self, writer_doc_id):
        result = call_tool(
            "get_document_content", {"scope": "full"}, doc_id=writer_doc_id
        )
        assert result["status"] == "ok"
        assert "content" in result

    def test_get_document_info(self, writer_doc_id):
        result = call_tool("get_document_info", {}, doc_id=writer_doc_id)
        assert result["status"] == "ok"
        assert result["doc_type"] == "writer"

    def test_get_document_stats(self, writer_doc_id):
        result = call_tool("get_document_stats", {}, doc_id=writer_doc_id)
        assert result["status"] == "ok"
        assert "paragraph_count" in result

    def test_read_paragraphs(self, writer_doc_id):
        result = call_tool("read_paragraphs", {"count": 5}, doc_id=writer_doc_id)
        assert result["status"] == "ok"
        assert "paragraphs" in result

    def test_get_document_tree(self, writer_doc_id):
        result = call_tool(
            "get_document_tree",
            {"content_strategy": "heading_only", "depth": 0},
            doc_id=writer_doc_id,
        )
        assert result["status"] == "ok"

    def test_find_text(self, writer_doc_id):
        result = call_tool("find_text", {"search": "the"}, doc_id=writer_doc_id)
        assert result["status"] == "ok"

    def test_search_in_document(self, writer_doc_id):
        result = call_tool(
            "search_in_document",
            {"pattern": "the", "max_results": 5},
            doc_id=writer_doc_id,
        )
        assert result["status"] == "ok"

    def test_list_styles(self, writer_doc_id):
        result = call_tool(
            "list_styles", {"family": "ParagraphStyles"}, doc_id=writer_doc_id
        )
        assert result["status"] == "ok"
        assert "styles" in result

    def test_list_tables(self, writer_doc_id):
        result = call_tool("list_tables", {}, doc_id=writer_doc_id)
        assert result["status"] == "ok"

    def test_list_comments(self, writer_doc_id):
        result = call_tool("list_comments", {}, doc_id=writer_doc_id)
        assert result["status"] == "ok"

    def test_list_images(self, writer_doc_id):
        result = call_tool("list_images", {}, doc_id=writer_doc_id)
        assert result["status"] == "ok"

    def test_list_bookmarks(self, writer_doc_id):
        result = call_tool("list_bookmarks", {}, doc_id=writer_doc_id)
        assert result["status"] == "ok"


class TestWriterMutationTools:
    """Mutation tools — modify the document. Uses undo for cleanup."""

    def test_insert_and_undo(self, writer_doc_id):
        result = call_tool(
            "insert_at_paragraph",
            {
                "text": "Smoke test insertion.",
                "paragraph_index": 0,
                "position": "before",
            },
            doc_id=writer_doc_id,
        )
        assert result["status"] == "ok"
        call_tool("undo", {"steps": 1}, doc_id=writer_doc_id)

    def test_set_paragraph_and_undo(self, writer_doc_id):
        call_tool(
            "insert_at_paragraph",
            {
                "text": "Temporary paragraph.",
                "paragraph_index": 0,
            },
            doc_id=writer_doc_id,
        )
        result = call_tool(
            "set_paragraph_text",
            {
                "paragraph_index": 0,
                "text": "Modified text.",
            },
            doc_id=writer_doc_id,
        )
        assert result["status"] == "ok"
        call_tool("undo", {"steps": 2}, doc_id=writer_doc_id)

    def test_replace_in_document_and_undo(self, writer_doc_id):
        call_tool(
            "apply_document_content",
            {
                "target": "full",
                "content": "Hello world. Hello again.",
            },
            doc_id=writer_doc_id,
        )
        result = call_tool(
            "replace_in_document",
            {
                "search": "Hello",
                "replace": "Greetings",
            },
            doc_id=writer_doc_id,
        )
        assert result["status"] == "ok"
        call_tool("undo", {"steps": 2}, doc_id=writer_doc_id)

    def test_create_table_and_undo(self, writer_doc_id):
        result = call_tool(
            "create_table",
            {
                "rows": 2,
                "cols": 2,
                "paragraph_index": 0,
            },
            doc_id=writer_doc_id,
        )
        assert result["status"] == "ok"
        call_tool("undo", {"steps": 1}, doc_id=writer_doc_id)


class TestWriterNavigationTools:
    def test_resolve_locator(self, writer_doc_id):
        result = call_tool(
            "resolve_locator", {"locator": "paragraph:0"}, doc_id=writer_doc_id
        )
        assert result["status"] == "ok"

    def test_get_surroundings(self, writer_doc_id):
        result = call_tool(
            "get_surroundings",
            {"locator": "paragraph:0", "radius": 1},
            doc_id=writer_doc_id,
        )
        assert result["status"] == "ok"


class TestWriterIndexTools:
    def test_search_fulltext(self, writer_doc_id):
        result = call_tool(
            "search_fulltext", {"query": "document"}, doc_id=writer_doc_id
        )
        assert result["status"] == "ok"

    def test_get_index_stats(self, writer_doc_id):
        result = call_tool("get_index_stats", {}, doc_id=writer_doc_id)
        assert result["status"] == "ok"


class TestCommonTools:
    def test_list_open_documents(self):
        result = call_tool("list_open_documents", {})
        assert result["status"] == "ok"
        assert "documents" in result

    def test_undo_redo(self, writer_doc_id):
        call_tool(
            "insert_at_paragraph",
            {
                "text": "Undo test",
                "paragraph_index": 0,
            },
            doc_id=writer_doc_id,
        )
        undo_result = call_tool("undo", {"steps": 1}, doc_id=writer_doc_id)
        assert undo_result["status"] == "ok"


class TestMCPProtocol:
    def test_health_endpoint(self):
        import urllib.request

        req = urllib.request.Request("http://localhost:9876/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        assert data["status"] == "ok"
        assert data.get("tools", 0) > 0

    def test_tools_list(self):
        from .conftest import mcp_call

        result = mcp_call("tools/list", {})
        assert "tools" in result
        tool_names = [t["name"] for t in result["tools"]]
        assert len(tool_names) > 0

    def test_ping(self):
        from .conftest import mcp_call

        result = mcp_call("ping", {})
        assert result == {}

    def test_initialize(self):
        from .conftest import mcp_call

        result = mcp_call(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "smoke-test", "version": "1.0"},
            },
        )
        assert "protocolVersion" in result


import json
