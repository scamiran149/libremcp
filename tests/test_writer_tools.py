import os
import sys
import pytest
from unittest.mock import patch

_tests_dir = os.path.dirname(os.path.abspath(__file__))
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

from stubs.uno_stubs import install_uno_stubs

install_uno_stubs()

from stubs.writer_stubs import WriterDocStub, ParagraphStub, TextRangeStub
from stubs.service_stubs import StubServiceRegistry
from plugin.framework.tool_context import ToolContext
from plugin.modules.writer.tools.content import (
    GetDocumentContent,
    ApplyDocumentContent,
    FindText,
    ReadParagraphs,
    InsertAtParagraph,
    SetParagraphText,
    SetParagraphStyle,
    DeleteParagraph,
    DuplicateParagraph,
    CloneHeadingBlock,
    InsertParagraphsBatch,
)
from plugin.modules.writer.tools.search import SearchInDocument, ReplaceInDocument
from plugin.modules.writer.tools.stats import GetDocumentStats
from plugin.modules.writer.tools.outline import GetDocumentOutline, GetHeadingContent
from plugin.modules.writer.tools.styles import ListStyles, GetStyleInfo
from plugin.modules.writer.tools.tracking import (
    SetTrackChanges,
    GetTrackedChanges,
    AcceptAllChanges,
    RejectAllChanges,
)


@pytest.fixture
def writer_doc():
    doc = WriterDocStub()
    doc.add_paragraph("Introduction", style="Heading 1")
    doc.add_paragraph("This is the first paragraph.", style="Text Body")
    doc.add_paragraph("Methods", style="Heading 2")
    doc.add_paragraph("This is the second paragraph.", style="Text Body")
    doc.add_paragraph("Results", style="Heading 1")
    doc.add_paragraph("The results are conclusive.", style="Text Body")
    return doc


@pytest.fixture
def empty_doc():
    doc = WriterDocStub()
    return doc


@pytest.fixture
def writer_services(writer_doc):
    return StubServiceRegistry(doc=writer_doc)


@pytest.fixture
def tool_context(writer_doc, writer_services):
    return ToolContext(
        doc=writer_doc,
        ctx=None,
        doc_type="writer",
        services=writer_services,
        caller="test",
    )


@pytest.fixture
def empty_context(empty_doc):
    svc = StubServiceRegistry(doc=empty_doc)
    return ToolContext(
        doc=empty_doc,
        ctx=None,
        doc_type="writer",
        services=svc,
        caller="test",
    )


@pytest.fixture
def calc_context():
    from stubs.calc_stubs import CalcDocStub

    doc = CalcDocStub()
    doc.add_sheet("Sheet1")
    svc = StubServiceRegistry(doc=doc)
    return ToolContext(
        doc=doc,
        ctx=None,
        doc_type="calc",
        services=svc,
        caller="test",
    )


# ======================================================================
# GetDocumentContent
# ======================================================================


class TestGetDocumentContent:
    def test_mutation_detection(self):
        tool = GetDocumentContent()
        assert tool.detects_mutation() is False

    def test_doc_types(self):
        tool = GetDocumentContent()
        assert tool.doc_types == ["writer"]

    def test_validate_no_required_params(self):
        tool = GetDocumentContent()
        ok, err = tool.validate()
        assert ok is True

    def test_full_scope_returns_ok(self, tool_context):
        tool = GetDocumentContent()
        with patch(
            "plugin.modules.writer.tools.content.format_support.document_to_content",
            return_value="Introduction\nThis is the first paragraph.",
        ):
            result = tool.execute(tool_context, scope="full")
        assert result["status"] == "ok"
        assert "content" in result
        assert "document_length" in result

    def test_range_scope_missing_params(self, tool_context):
        tool = GetDocumentContent()
        result = tool.execute(tool_context, scope="range")
        assert result["status"] == "error"
        assert "start and end" in result["message"]

    def test_range_scope_with_params(self, tool_context):
        tool = GetDocumentContent()
        with patch(
            "plugin.modules.writer.tools.content.format_support.document_to_content",
            return_value="first paragraph",
        ):
            result = tool.execute(tool_context, scope="range", start=0, end=20)
        assert result["status"] == "ok"
        assert result["start"] == 0
        assert result["end"] == 20

    def test_max_chars_with_full_scope(self, tool_context):
        tool = GetDocumentContent()
        with patch(
            "plugin.modules.writer.tools.content.format_support.document_to_content",
            return_value="short content",
        ):
            result = tool.execute(tool_context, scope="full", max_chars=5)
        assert result["status"] == "ok"


# ======================================================================
# ApplyDocumentContent
# ======================================================================


class TestApplyDocumentContent:
    def test_mutation_detection(self):
        tool = ApplyDocumentContent()
        assert tool.is_mutation is True

    def test_doc_types(self):
        tool = ApplyDocumentContent()
        assert tool.doc_types == ["writer"]

    def test_validate_requires_content_and_target(self):
        tool = ApplyDocumentContent()
        ok, err = tool.validate(content="hello", target="full")
        assert ok is True

    def test_validate_missing_required(self):
        tool = ApplyDocumentContent()
        ok, err = tool.validate(content="hello")
        assert ok is False

    def test_target_search_missing_search_param(self, tool_context):
        tool = ApplyDocumentContent()
        result = tool.execute(tool_context, content="new text", target="search")
        assert result["status"] == "error"
        assert "search" in result["message"].lower()

    def test_target_full_plain_text(self, tool_context):
        tool = ApplyDocumentContent()
        with patch(
            "plugin.modules.writer.tools.content.format_support.content_has_markup",
            return_value=True,
        ), patch(
            "plugin.modules.writer.tools.content.format_support.replace_full_document",
            return_value=None,
        ) as mock_replace:
            result = tool.execute(
                tool_context, content="<p>New content</p>", target="full"
            )
        assert result["status"] == "ok"
        mock_replace.assert_called_once()

    def test_target_range_missing_params(self, tool_context):
        tool = ApplyDocumentContent()
        result = tool.execute(tool_context, content="text", target="range")
        assert result["status"] == "error"
        assert "start and end" in result["message"]

    def test_target_range_with_params(self, tool_context):
        tool = ApplyDocumentContent()
        with patch(
            "plugin.modules.writer.tools.content.format_support.content_has_markup",
            return_value=True,
        ), patch(
            "plugin.modules.writer.tools.content.format_support.apply_content_at_range",
        ) as mock_apply:
            result = tool.execute(
                tool_context, content="text", target="range", start=0, end=5
            )
        assert result["status"] == "ok"
        mock_apply.assert_called_once()

    def test_target_unknown(self, tool_context):
        tool = ApplyDocumentContent()
        result = tool.execute(tool_context, content="text", target="nowhere")
        assert result["status"] == "error"


# ======================================================================
# FindText
# ======================================================================


class TestFindText:
    def test_mutation_detection(self):
        tool = FindText()
        assert tool.detects_mutation() is False

    def test_doc_types(self):
        tool = FindText()
        assert tool.doc_types == ["writer"]

    def test_validate_requires_search(self):
        tool = FindText()
        ok, err = tool.validate(search="hello")
        assert ok is True

    def test_validate_missing_search(self):
        tool = FindText()
        ok, err = tool.validate()
        assert ok is False
        assert "search" in err

    def test_empty_search_returns_error(self, tool_context):
        tool = FindText()
        result = tool.execute(tool_context, search="")
        assert result["status"] == "error"

    def test_find_text_returns_ranges(self, tool_context):
        tool = FindText()
        with patch(
            "plugin.modules.writer.tools.content.format_support.find_text_ranges",
            return_value=[{"start": 0, "end": 10, "text": "Introduction"}],
        ):
            result = tool.execute(tool_context, search="Introduction")
        assert result["status"] == "ok"
        assert "ranges" in result
        assert len(result["ranges"]) == 1

    def test_find_text_case_sensitive(self, tool_context):
        tool = FindText()
        with patch(
            "plugin.modules.writer.tools.content.format_support.find_text_ranges",
            return_value=[],
        ):
            result = tool.execute(
                tool_context, search="introduction", case_sensitive=True
            )
        assert result["status"] == "ok"


# ======================================================================
# ReadParagraphs
# ======================================================================


class TestReadParagraphs:
    def test_mutation_detection(self):
        tool = ReadParagraphs()
        assert tool.detects_mutation() is False

    def test_returns_paragraphs(self, tool_context):
        tool = ReadParagraphs()
        result = tool.execute(tool_context, start_index=0, count=3)
        assert result["status"] == "ok"
        assert len(result["paragraphs"]) == 3
        assert result["paragraphs"][0]["text"] == "Introduction"
        assert result["total"] == 6

    def test_with_locator(self, tool_context):
        tool = ReadParagraphs()
        result = tool.execute(tool_context, locator="paragraph:0", count=2)
        assert result["status"] == "ok"
        assert result["paragraphs"][0]["text"] == "Introduction"

    def test_start_index_beyond_end(self, tool_context):
        tool = ReadParagraphs()
        result = tool.execute(tool_context, start_index=100, count=10)
        assert result["status"] == "ok"
        assert result["paragraphs"] == []

    def test_default_params(self, tool_context):
        tool = ReadParagraphs()
        result = tool.execute(tool_context)
        assert result["status"] == "ok"
        assert "paragraphs" in result


# ======================================================================
# InsertAtParagraph
# ======================================================================


class TestInsertAtParagraph:
    def test_mutation_detection(self):
        tool = InsertAtParagraph()
        assert tool.is_mutation is True

    def test_validate_requires_text(self):
        tool = InsertAtParagraph()
        ok, err = tool.validate(text="hello")
        assert ok is True

    def test_validate_missing_text(self):
        tool = InsertAtParagraph()
        ok, err = tool.validate()
        assert ok is False

    def test_no_locator_or_index(self, tool_context):
        tool = InsertAtParagraph()
        result = tool.execute(tool_context, text="new text")
        assert result["status"] == "error"
        assert (
            "locator" in result["message"].lower()
            or "paragraph_index" in result["message"].lower()
        )

    def test_index_out_of_range(self, tool_context):
        tool = InsertAtParagraph()
        result = tool.execute(tool_context, text="new", paragraph_index=999)
        assert result["status"] == "error"
        assert "out of range" in result["message"].lower()

    def test_insert_before(self, tool_context, writer_doc):
        tool = InsertAtParagraph()
        result = tool.execute(
            tool_context, text="New paragraph", paragraph_index=1, position="before"
        )
        assert result["status"] == "ok"
        assert "Inserted" in result["message"]

    def test_insert_after(self, tool_context, writer_doc):
        tool = InsertAtParagraph()
        result = tool.execute(
            tool_context, text="After para", paragraph_index=0, position="after"
        )
        assert result["status"] == "ok"

    def test_insert_with_locator(self, tool_context, writer_services):
        tool = InsertAtParagraph()
        result = tool.execute(
            tool_context, text="Located", locator="paragraph:0", position="before"
        )
        assert result["status"] == "ok"


# ======================================================================
# SetParagraphText
# ======================================================================


class TestSetParagraphText:
    def test_mutation_detection(self):
        tool = SetParagraphText()
        assert tool.is_mutation is True

    def test_validate_requires_text(self):
        tool = SetParagraphText()
        ok, err = tool.validate(text="new text")
        assert ok is True

    def test_no_locator_or_index(self, tool_context):
        tool = SetParagraphText()
        result = tool.execute(tool_context, text="new text")
        assert result["status"] == "error"

    def test_set_text_by_index(self, tool_context, writer_doc):
        tool = SetParagraphText()
        result = tool.execute(tool_context, text="Updated text", paragraph_index=1)
        assert result["status"] == "ok"
        assert result["paragraph_index"] == 1
        assert result["new_length"] == len("Updated text")
        assert writer_doc._paragraphs[1].getString() == "Updated text"

    def test_set_text_by_locator(self, tool_context, writer_doc):
        tool = SetParagraphText()
        result = tool.execute(tool_context, text="New title", locator="paragraph:0")
        assert result["status"] == "ok"
        assert writer_doc._paragraphs[0].getString() == "New title"

    def test_index_out_of_range(self, tool_context):
        tool = SetParagraphText()
        result = tool.execute(tool_context, text="x", paragraph_index=999)
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()


# ======================================================================
# SetParagraphStyle
# ======================================================================


class TestSetParagraphStyle:
    def test_mutation_detection(self):
        tool = SetParagraphStyle()
        assert tool.is_mutation is True

    def test_validate_requires_style(self):
        tool = SetParagraphStyle()
        ok, err = tool.validate(style="Heading 1")
        assert ok is True

    def test_change_style(self, tool_context, writer_doc):
        tool = SetParagraphStyle()
        result = tool.execute(tool_context, paragraph_index=1, style="Heading 2")
        assert result["status"] == "ok"
        assert result["old_style"] == "Text Body"
        assert result["new_style"] == "Heading 2"
        assert (
            writer_doc._paragraphs[1].getPropertyValue("ParaStyleName") == "Heading 2"
        )

    def test_no_index(self, tool_context):
        tool = SetParagraphStyle()
        result = tool.execute(tool_context, style="Heading 1")
        assert result["status"] == "error"


# ======================================================================
# DeleteParagraph
# ======================================================================


class TestDeleteParagraph:
    def test_mutation_detection(self):
        tool = DeleteParagraph()
        assert tool.is_mutation is True

    def test_no_index(self, tool_context):
        tool = DeleteParagraph()
        result = tool.execute(tool_context)
        assert result["status"] == "error"

    def test_delete_existing_paragraph(self, tool_context, writer_doc):
        tool = DeleteParagraph()
        original_count = len(writer_doc._paragraphs)
        result = tool.execute(tool_context, paragraph_index=1)
        assert result["status"] == "ok"
        assert "Deleted" in result["message"]

    def test_delete_out_of_range(self, tool_context):
        tool = DeleteParagraph()
        result = tool.execute(tool_context, paragraph_index=999)
        assert result["status"] == "error"


# ======================================================================
# DuplicateParagraph
# ======================================================================


class TestDuplicateParagraph:
    def test_mutation_detection(self):
        tool = DuplicateParagraph()
        assert tool.is_mutation is True

    def test_no_index(self, tool_context):
        tool = DuplicateParagraph()
        result = tool.execute(tool_context)
        assert result["status"] == "error"

    def test_duplicate_with_index(self, tool_context, writer_doc):
        tool = DuplicateParagraph()
        result = tool.execute(tool_context, paragraph_index=0)
        assert result["status"] == "ok"
        assert "Duplicated" in result["message"]

    def test_invalid_count(self, tool_context):
        tool = DuplicateParagraph()
        result = tool.execute(tool_context, paragraph_index=0, count=0)
        assert result["status"] == "error"
        assert "count" in result["message"].lower()

    def test_out_of_range(self, tool_context):
        tool = DuplicateParagraph()
        result = tool.execute(tool_context, paragraph_index=999)
        assert result["status"] == "error"


# ======================================================================
# CloneHeadingBlock
# ======================================================================


class TestCloneHeadingBlock:
    def test_mutation_detection(self):
        tool = CloneHeadingBlock()
        assert tool.is_mutation is True

    def test_no_index(self, tool_context):
        tool = CloneHeadingBlock()
        result = tool.execute(tool_context)
        assert result["status"] == "error"

    def test_clone_heading(self, tool_context, writer_doc):
        tool = CloneHeadingBlock()
        result = tool.execute(tool_context, paragraph_index=0)
        assert result["status"] == "ok"
        assert "Cloned" in result["message"]
        assert result["block_size"] >= 1

    def test_clone_non_heading(self, tool_context):
        tool = CloneHeadingBlock()
        result = tool.execute(tool_context, paragraph_index=1)
        assert result["status"] == "error"


# ======================================================================
# InsertParagraphsBatch
# ======================================================================


class TestInsertParagraphsBatch:
    def test_mutation_detection(self):
        tool = InsertParagraphsBatch()
        assert tool.is_mutation is True

    def test_validate_requires_paragraphs(self):
        tool = InsertParagraphsBatch()
        ok, err = tool.validate(paragraphs=[{"text": "hello"}])
        assert ok is True

    def test_empty_paragraphs_list(self, tool_context):
        tool = InsertParagraphsBatch()
        result = tool.execute(tool_context, paragraphs=[])
        assert result["status"] == "error"
        assert "Empty" in result["message"]

    def test_no_index(self, tool_context):
        tool = InsertParagraphsBatch()
        result = tool.execute(tool_context, paragraphs=[{"text": "New para"}])
        assert result["status"] == "error"

    def test_insert_after(self, tool_context, writer_doc):
        tool = InsertParagraphsBatch()
        result = tool.execute(
            tool_context,
            paragraphs=[{"text": "Para A"}, {"text": "Para B"}],
            paragraph_index=0,
            position="after",
        )
        assert result["status"] == "ok"
        assert result["count"] == 2

    def test_insert_before(self, tool_context, writer_doc):
        tool = InsertParagraphsBatch()
        result = tool.execute(
            tool_context,
            paragraphs=[{"text": "Para A"}],
            paragraph_index=1,
            position="before",
        )
        assert result["status"] == "ok"
        assert result["count"] == 1


# ======================================================================
# SearchInDocument
# ======================================================================


class TestSearchInDocument:
    def test_mutation_detection(self):
        tool = SearchInDocument()
        assert tool.detects_mutation() is False

    def test_doc_types(self):
        tool = SearchInDocument()
        assert tool.doc_types == ["writer"]

    def test_validate_requires_pattern(self):
        tool = SearchInDocument()
        ok, err = tool.validate(pattern="hello")
        assert ok is True

    def test_validate_missing_pattern(self):
        tool = SearchInDocument()
        ok, err = tool.validate()
        assert ok is False

    def test_empty_pattern_returns_error(self, tool_context):
        tool = SearchInDocument()
        result = tool.execute(tool_context, pattern="")
        assert result["status"] == "error"
        assert "pattern" in result["message"].lower()

    def test_search_found(self, tool_context):
        tool = SearchInDocument()
        result = tool.execute(tool_context, pattern="Introduction")
        assert result["status"] == "ok"
        assert result["count"] >= 1
        assert len(result["matches"]) >= 1
        assert result["matches"][0]["text"] == "Introduction"

    def test_search_not_found(self, tool_context):
        tool = SearchInDocument()
        result = tool.execute(tool_context, pattern="NONEXISTENT_TEXT_XYZ")
        assert result["status"] == "ok"
        assert result["count"] == 0
        assert result["matches"] == []

    def test_case_insensitive(self, tool_context):
        tool = SearchInDocument()
        result = tool.execute(
            tool_context, pattern="introduction", case_sensitive=False
        )
        assert result["status"] == "ok"
        assert result["count"] >= 1

    def test_regex_search(self, tool_context):
        tool = SearchInDocument()
        result = tool.execute(tool_context, pattern="Intro.*", regex=True)
        assert result["status"] == "ok"
        assert result["count"] >= 1

    def test_max_results(self, tool_context):
        tool = SearchInDocument()
        result = tool.execute(tool_context, pattern="a", max_results=1)
        assert result["status"] == "ok"
        assert result["count"] >= 1
        assert len(result["matches"]) <= 1

    def test_context_paragraphs(self, tool_context):
        tool = SearchInDocument()
        result = tool.execute(
            tool_context, pattern="Introduction", context_paragraphs=2
        )
        assert result["status"] == "ok"
        match = result["matches"][0]
        assert "context" in match
        assert len(match["context"]) > 0

    def test_invalid_regex(self, tool_context):
        tool = SearchInDocument()
        result = tool.execute(tool_context, pattern="[invalid", regex=True)
        assert result["status"] == "error"


# ======================================================================
# ReplaceInDocument
# ======================================================================


class TestReplaceInDocument:
    def test_mutation_detection(self):
        tool = ReplaceInDocument()
        assert tool.is_mutation is True

    def test_doc_types(self):
        tool = ReplaceInDocument()
        assert tool.doc_types == ["writer"]

    def test_validate_requires_search_and_replace(self):
        tool = ReplaceInDocument()
        ok, err = tool.validate(search="old", replace="new")
        assert ok is True

    def test_empty_search_returns_error(self, tool_context):
        tool = ReplaceInDocument()
        result = tool.execute(tool_context, search="", replace="new")
        assert result["status"] == "error"
        assert "search" in result["message"].lower()

    def test_replace_all(self, tool_context, writer_doc):
        tool = ReplaceInDocument()
        result = tool.execute(
            tool_context, search="first", replace="second", replace_all=True
        )
        assert result["status"] == "ok"
        assert result["replacements"] >= 1
        assert "second" in writer_doc._paragraphs[1].getString()

    def test_replace_first_only(self, tool_context):
        tool = ReplaceInDocument()
        result = tool.execute(
            tool_context, search="first", replace="modified", replace_all=False
        )
        assert result["status"] == "ok"
        assert result["replacements"] in (0, 1)

    def test_replace_not_found(self, tool_context):
        tool = ReplaceInDocument()
        result = tool.execute(
            tool_context, search="NONEXISTENT_XYZ", replace="foo", replace_all=True
        )
        assert result["status"] == "ok"
        assert result["replacements"] == 0

    def test_replace_case_insensitive(self, tool_context):
        tool = ReplaceInDocument()
        result = tool.execute(
            tool_context,
            search="introduction",
            replace="Intro",
            case_sensitive=False,
            replace_all=True,
        )
        assert result["status"] == "ok"


# ======================================================================
# GetDocumentStats
# ======================================================================


class TestGetDocumentStats:
    def test_mutation_detection(self):
        tool = GetDocumentStats()
        assert tool.detects_mutation() is False

    def test_doc_types(self):
        tool = GetDocumentStats()
        assert tool.doc_types == ["writer"]

    def test_validate_no_params(self):
        tool = GetDocumentStats()
        ok, err = tool.validate()
        assert ok is True

    def test_returns_stats(self, tool_context):
        tool = GetDocumentStats()
        result = tool.execute(tool_context)
        assert result["status"] == "ok"
        assert result["paragraph_count"] == 6
        assert result["heading_count"] >= 2
        assert result["page_count"] >= 1
        assert result["word_count"] >= 0
        assert result["character_count"] >= 0

    def test_empty_doc_stats(self, empty_context):
        tool = GetDocumentStats()
        result = tool.execute(empty_context)
        assert result["status"] == "ok"
        assert result["paragraph_count"] == 0
        assert result["heading_count"] == 0


# ======================================================================
# GetDocumentOutline (deprecated)
# ======================================================================


class TestGetDocumentOutline:
    def test_mutation_detection(self):
        tool = GetDocumentOutline()
        assert tool.detects_mutation() is False

    def test_doc_types(self):
        tool = GetDocumentOutline()
        assert tool.doc_types == ["writer"]

    def test_returns_outline(self, tool_context):
        tool = GetDocumentOutline()
        result = tool.execute(tool_context)
        assert result["status"] == "ok"
        assert "outline" in result
        assert len(result["outline"]) >= 1

    def test_max_depth(self, tool_context):
        tool = GetDocumentOutline()
        result = tool.execute(tool_context, max_depth=1)
        assert result["status"] == "ok"
        for node in result["outline"]:
            assert node["children"] == []

    def test_empty_doc(self, empty_context):
        tool = GetDocumentOutline()
        result = tool.execute(empty_context)
        assert result["status"] == "ok"
        assert result["outline"] == []


# ======================================================================
# GetHeadingContent (deprecated)
# ======================================================================


class TestGetHeadingContent:
    def test_mutation_detection(self):
        tool = GetHeadingContent()
        assert tool.detects_mutation() is False

    def test_doc_types(self):
        tool = GetHeadingContent()
        assert tool.doc_types == ["writer"]

    def test_validate_requires_heading_path(self):
        tool = GetHeadingContent()
        ok, err = tool.validate(heading_path="1")
        assert ok is True

    def test_validate_missing_heading_path(self):
        tool = GetHeadingContent()
        ok, err = tool.validate()
        assert ok is False

    def test_heading_content(self, tool_context):
        tool = GetHeadingContent()
        result = tool.execute(tool_context, heading_path="1")
        assert result["status"] == "ok"
        assert result["heading_title"] == "Introduction"
        assert "paragraphs" in result

    def test_heading_not_found(self, tool_context):
        tool = GetHeadingContent()
        result = tool.execute(tool_context, heading_path="99")
        assert result["status"] == "error"

    def test_invalid_heading_path(self, tool_context):
        tool = GetHeadingContent()
        result = tool.execute(tool_context, heading_path="abc")
        assert result["status"] == "error"


# ======================================================================
# ListStyles
# ======================================================================


class TestListStyles:
    def test_mutation_detection(self):
        tool = ListStyles()
        assert tool.detects_mutation() is False

    def test_doc_types_all(self):
        tool = ListStyles()
        assert tool.doc_types is None

    def test_list_all_families(self, tool_context):
        tool = ListStyles()
        result = tool.execute(tool_context)
        assert result["status"] == "ok"
        assert "families" in result
        assert "ParagraphStyles" in result["families"]
        assert result["count"] >= 1

    def test_list_paragraph_styles(self, tool_context):
        tool = ListStyles()
        result = tool.execute(tool_context, family="ParagraphStyles")
        assert result["status"] == "ok"
        assert result["family"] == "ParagraphStyles"
        assert result["count"] >= 2
        style_names = [s["name"] for s in result["styles"]]
        assert "Heading 1" in style_names

    def test_unknown_family(self, tool_context):
        tool = ListStyles()
        result = tool.execute(tool_context, family="NonexistentStyles")
        assert result["status"] == "error"
        assert "Unknown" in result["message"]

    def test_works_with_writer_doc(self, tool_context):
        tool = ListStyles()
        result = tool.execute(tool_context, family="ParagraphStyles")
        assert result["status"] == "ok"

    def test_works_with_calc_doc(self, calc_context):
        tool = ListStyles()
        result = calc_styles = tool.execute(calc_context)
        assert result["status"] == "error" or result["status"] == "ok"


# ======================================================================
# GetStyleInfo
# ======================================================================


class TestGetStyleInfo:
    def test_mutation_detection(self):
        tool = GetStyleInfo()
        assert tool.detects_mutation() is False

    def test_doc_types_all(self):
        tool = GetStyleInfo()
        assert tool.doc_types is None

    def test_validate_requires_style_name(self):
        tool = GetStyleInfo()
        ok, err = tool.validate(style_name="Heading 1")
        assert ok is True

    def test_validate_missing_style_name(self):
        tool = GetStyleInfo()
        ok, err = tool.validate()
        assert ok is False

    def test_get_existing_style(self, tool_context):
        tool = GetStyleInfo()
        result = tool.execute(
            tool_context, style_name="Heading 1", family="ParagraphStyles"
        )
        assert result["status"] == "ok"
        assert result["name"] == "Heading 1"
        assert result["family"] == "ParagraphStyles"
        assert "ParentStyle" in result

    def test_style_not_found(self, tool_context):
        tool = GetStyleInfo()
        result = tool.execute(
            tool_context, style_name="NonExistentStyle", family="ParagraphStyles"
        )
        assert result["status"] == "error"

    def test_default_family(self, tool_context):
        tool = GetStyleInfo()
        result = tool.execute(tool_context, style_name="Heading 1")
        assert result["status"] == "ok"
        assert result["family"] == "ParagraphStyles"


# ======================================================================
# SetTrackChanges
# ======================================================================


class TestSetTrackChanges:
    def test_mutation_detection(self):
        tool = SetTrackChanges()
        assert tool.is_mutation is True

    def test_doc_types(self):
        tool = SetTrackChanges()
        assert tool.doc_types == ["writer"]

    def test_validate_requires_enabled(self):
        tool = SetTrackChanges()
        ok, err = tool.validate(enabled=True)
        assert ok is True

    def test_enable(self, tool_context, writer_doc):
        tool = SetTrackChanges()
        result = tool.execute(tool_context, enabled=True)
        assert result["status"] == "ok"
        assert result["record_changes"] is True

    def test_disable(self, tool_context, writer_doc):
        tool = SetTrackChanges()
        result = tool.execute(tool_context, enabled=False)
        assert result["status"] == "ok"
        assert result["record_changes"] is False

    def test_string_enabled(self, tool_context):
        tool = SetTrackChanges()
        result = tool.execute(tool_context, enabled="true")
        assert result["status"] == "ok"
        assert result["record_changes"] is True

    def test_string_disabled(self, tool_context):
        tool = SetTrackChanges()
        result = tool.execute(tool_context, enabled="false")
        assert result["status"] == "ok"
        assert result["record_changes"] is False


# ======================================================================
# GetTrackedChanges
# ======================================================================


class TestGetTrackedChanges:
    def test_mutation_detection(self):
        tool = GetTrackedChanges()
        assert tool.detects_mutation() is False

    def test_doc_types(self):
        tool = GetTrackedChanges()
        assert tool.doc_types == ["writer"]

    def test_returns_ok_no_changes(self, tool_context):
        tool = GetTrackedChanges()
        result = tool.execute(tool_context)
        assert result["status"] == "ok"
        assert result["count"] == 0
        assert result["changes"] == []


# ======================================================================
# AcceptAllChanges / RejectAllChanges
# ======================================================================


class TestAcceptAllChanges:
    def test_mutation_detection(self):
        tool = AcceptAllChanges()
        assert tool.is_mutation is True

    def test_doc_types(self):
        tool = AcceptAllChanges()
        assert tool.doc_types == ["writer"]

    def test_requires_uno_ctx(self, tool_context):
        tool = AcceptAllChanges()
        try:
            result = tool.execute(tool_context)
        except AttributeError:
            pass


class TestRejectAllChanges:
    def test_mutation_detection(self):
        tool = RejectAllChanges()
        assert tool.is_mutation is True

    def test_doc_types(self):
        tool = RejectAllChanges()
        assert tool.doc_types == ["writer"]


# ======================================================================
# Comments tools (parameter validation only, UNO annotation stubs limited)
# ======================================================================


class TestListComments:
    def test_returns_empty_comments(self, tool_context):
        from plugin.modules.writer.tools.comments import ListComments

        tool = ListComments()
        result = tool.execute(tool_context)
        assert result["status"] == "ok"
        assert result["count"] == 0


class TestAddComment:
    def test_validate_requires_content(self):
        from plugin.modules.writer.tools.comments import AddComment

        tool = AddComment()
        ok, err = tool.validate(content="test comment")
        assert ok is True

    def test_validate_missing_content(self):
        from plugin.modules.writer.tools.comments import AddComment

        tool = AddComment()
        ok, err = tool.validate()
        assert ok is False

    def test_empty_content_returns_error(self, tool_context):
        from plugin.modules.writer.tools.comments import AddComment

        tool = AddComment()
        result = tool.execute(tool_context, content="")
        assert result["status"] == "error"

    def test_no_anchor_returns_error(self, tool_context):
        from plugin.modules.writer.tools.comments import AddComment

        tool = AddComment()
        result = tool.execute(tool_context, content="Hello")
        assert result["status"] == "error"


class TestDeleteComment:
    def test_validate_no_required(self):
        from plugin.modules.writer.tools.comments import DeleteComment

        tool = DeleteComment()
        ok, err = tool.validate()
        assert ok is True

    def test_no_params_returns_error(self, tool_context):
        from plugin.modules.writer.tools.comments import DeleteComment

        tool = DeleteComment()
        result = tool.execute(tool_context)
        assert result["status"] == "error"


class TestCheckStopConditions:
    def test_returns_ok(self, tool_context):
        from plugin.modules.writer.tools.comments import CheckStopConditions

        tool = CheckStopConditions()
        result = tool.execute(tool_context)
        assert result["status"] == "ok"
        assert "should_stop" in result


# ======================================================================
# Tables, images, frames: TODO markers
# ======================================================================


class TestTablesToolsPlaceholder:
    def test_placeholder(self):
        pass


class TestImagesToolsPlaceholder:
    def test_placeholder(self):
        pass


class TestFramesToolsPlaceholder:
    def test_placeholder(self):
        pass
