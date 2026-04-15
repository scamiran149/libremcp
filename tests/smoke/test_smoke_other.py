"""Smoke tests for Calc, Draw, and cross-doc tools via live MCP server.

These tests require creating new documents, so they must be run when LO is
stable. Each test creates a document, runs one check, and undoes/closes.
Requires LibreOffice + LibreMCP running at localhost:9876.
"""

import pytest

from .conftest import call_tool


class TestCalcTools:
    """Calc tools — requires creating a Calc document."""

    def test_create_calc_and_read(self):
        result = call_tool("create_document", {"doc_type": "calc"})
        assert result["status"] == "ok"
        doc_id = result.get("doc_id") or call_tool("get_document_info", {}).get(
            "doc_id"
        )
        try:
            sheets_result = call_tool("list_sheets", {}, doc_id=doc_id)
            assert sheets_result["status"] == "ok"
            assert "result" in sheets_result or "sheets" in sheets_result
        finally:
            call_tool("close_document", doc_id=doc_id)

    def test_calc_write_and_undo(self):
        result = call_tool("create_document", {"doc_type": "calc"})
        doc_id = result.get("doc_id") or call_tool("get_document_info", {}).get(
            "doc_id"
        )
        try:
            write_result = call_tool(
                "write_cell_range",
                {
                    "start_cell": "A1",
                    "values": [["Header", 42]],
                },
                doc_id=doc_id,
            )
            assert write_result["status"] == "ok"
            call_tool("undo", {"steps": 1}, doc_id=doc_id)
        finally:
            call_tool("close_document", doc_id=doc_id)


class TestDrawTools:
    """Draw tools — requires creating a Draw document."""

    def test_create_draw_and_list_pages(self):
        result = call_tool("create_document", {"doc_type": "draw"})
        doc_id = result.get("doc_id") or call_tool("get_document_info", {}).get(
            "doc_id"
        )
        try:
            pages_result = call_tool("list_pages", {}, doc_id=doc_id)
            assert pages_result["status"] == "ok"
            assert "pages" in pages_result
        finally:
            call_tool("close_document", doc_id=doc_id)

    def test_create_shape_and_undo(self):
        result = call_tool("create_document", {"doc_type": "draw"})
        doc_id = result.get("doc_id") or call_tool("get_document_info", {}).get(
            "doc_id"
        )
        try:
            shape_result = call_tool(
                "create_shape",
                {
                    "shape_type": "rectangle",
                    "x": 1000,
                    "y": 1000,
                    "width": 3000,
                    "height": 2000,
                    "text": "Smoke test",
                },
                doc_id=doc_id,
            )
            assert shape_result["status"] == "ok"
            call_tool("undo", {"steps": 1}, doc_id=doc_id)
        finally:
            call_tool("close_document", doc_id=doc_id)


class TestDocTools:
    """Document management tools."""

    def test_get_document_info(self):
        result = call_tool("get_document_info", {})
        assert result["status"] == "ok"
        assert "doc_type" in result

    def test_list_open_documents(self):
        result = call_tool("list_open_documents", {})
        assert result["status"] == "ok"
        assert "documents" in result
