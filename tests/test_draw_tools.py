import os
import sys
import pytest

_tests_dir = os.path.dirname(os.path.abspath(__file__))
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

from stubs.uno_stubs import install_uno_stubs

install_uno_stubs()

from stubs.draw_stubs import DrawDocStub
from stubs.service_stubs import StubServiceRegistry
from plugin.framework.tool_context import ToolContext
from plugin.modules.draw.tools.shapes import (
    ListPages,
    GetDrawSummary,
    CreateShape,
    EditShape,
    DeleteShape,
)
from plugin.modules.draw.tools.pages import (
    AddSlide,
    DeleteSlide,
    ReadSlideText,
    GetPresentationInfo,
)
from plugin.modules.draw.tools.masters import (
    ListMasterSlides,
    GetSlideMaster,
    SetSlideMaster,
)
from plugin.modules.draw.tools.notes import GetSpeakerNotes, SetSpeakerNotes
from plugin.modules.draw.tools.transitions import (
    GetSlideTransition,
    SetSlideTransition,
    GetSlideLayout,
    SetSlideLayout,
)
from plugin.modules.draw.tools.placeholders import (
    ListPlaceholders,
    GetPlaceholderText,
    SetPlaceholderText,
)


@pytest.fixture
def draw_doc():
    doc = DrawDocStub(doc_type="draw")
    page = doc.add_page()
    page.add_shape(
        "RectangleShape", x=1000, y=1000, width=5000, height=3000, text="Hello"
    )
    return doc


@pytest.fixture
def impress_doc():
    doc = DrawDocStub(doc_type="impress")
    page = doc.add_page()
    page.add_shape(
        "TextShape", x=1000, y=1000, width=20000, height=3000, text="Title Slide"
    )
    page._speaker_notes = "Welcome everyone"
    return doc


@pytest.fixture
def empty_draw_doc():
    doc = DrawDocStub(doc_type="draw")
    return doc


def _ctx(doc, doc_type, services=None):
    if services is None:
        services = StubServiceRegistry(doc)
    return ToolContext(
        doc=doc, ctx=None, doc_type=doc_type, services=services, caller="test"
    )


@pytest.fixture
def draw_ctx(draw_doc):
    return _ctx(draw_doc, "draw")


@pytest.fixture
def impress_ctx(impress_doc):
    return _ctx(impress_doc, "impress")


@pytest.fixture
def empty_draw_ctx(empty_draw_doc):
    return _ctx(empty_draw_doc, "draw")


def _should_skip(tool, doc_type):
    if tool.doc_types is None:
        return False
    return doc_type not in tool.doc_types


# ── shapes.py ──────────────────────────────────────────────────────


class TestListPages:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = ListPages()

    def test_validate_no_required(self):
        ok, _ = self.tool.validate()
        assert ok is True

    def test_doc_types_draw_impress(self):
        assert self.tool.doc_types == ["draw", "impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is False

    def test_happy_path(self, draw_ctx):
        result = self.tool.execute(draw_ctx)
        assert result["status"] == "ok"
        assert result["count"] == 1
        assert len(result["pages"]) == 1

    def test_multiple_pages(self, draw_ctx):
        draw_ctx.doc.add_page()
        draw_ctx.doc.add_page()
        result = self.tool.execute(draw_ctx)
        assert result["count"] == 3

    def test_empty_doc(self, empty_draw_ctx):
        result = self.tool.execute(empty_draw_ctx)
        assert result["status"] == "ok"
        assert result["count"] == 0


class TestGetDrawSummary:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = GetDrawSummary()

    def test_validate_no_required(self):
        ok, _ = self.tool.validate()
        assert ok is True

    def test_doc_types_all(self):
        assert self.tool.doc_types is None

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is False

    def test_happy_path(self, draw_ctx):
        result = self.tool.execute(draw_ctx)
        assert result["status"] == "ok"
        assert len(result["shapes"]) == 1
        assert result["shapes"][0]["type"] == "com.sun.star.drawing.RectangleShape"
        assert result["shapes"][0]["text"] == "Hello"

    def test_with_page_index(self, draw_ctx):
        draw_ctx.doc.add_page()
        result = self.tool.execute(draw_ctx, page_index=1)
        assert result["status"] == "ok"
        assert len(result["shapes"]) == 0

    def test_out_of_range_page_index(self, draw_ctx):
        with pytest.raises(RuntimeError, match="Page index"):
            self.tool.execute(draw_ctx, page_index=99)

    def test_empty_page(self, empty_draw_ctx):
        empty_draw_ctx.doc.add_page()
        result = self.tool.execute(empty_draw_ctx)
        assert result["status"] == "ok"
        assert len(result["shapes"]) == 0


class TestCreateShape:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = CreateShape()

    def test_validate_required(self):
        ok, err = self.tool.validate()
        assert ok is False
        assert "shape_type" in err

    def test_validate_with_all_required(self):
        ok, _ = self.tool.validate(
            shape_type="rectangle", x=0, y=0, width=100, height=100
        )
        assert ok is True

    def test_doc_types_all(self):
        assert self.tool.doc_types is None

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is True

    def test_happy_path(self, draw_ctx):
        result = self.tool.execute(
            draw_ctx, shape_type="rectangle", x=500, y=500, width=2000, height=1000
        )
        assert result["status"] == "ok"
        assert result["shape_index"] == 1

    def test_with_text(self, draw_ctx):
        result = self.tool.execute(
            draw_ctx,
            shape_type="text",
            x=100,
            y=100,
            width=5000,
            height=1000,
            text="New shape",
        )
        assert result["status"] == "ok"
        pages = draw_ctx.doc.getDrawPages()
        page = pages.getByIndex(0)
        shape = page.getByIndex(result["shape_index"])
        assert shape.getString() == "New shape"

    def test_with_bg_color(self, draw_ctx):
        result = self.tool.execute(
            draw_ctx,
            shape_type="rectangle",
            x=0,
            y=0,
            width=100,
            height=100,
            bg_color="red",
        )
        assert result["status"] == "ok"

    def test_ellipse_shape(self, draw_ctx):
        result = self.tool.execute(
            draw_ctx, shape_type="ellipse", x=0, y=0, width=100, height=100
        )
        assert result["status"] == "ok"

    def test_line_shape(self, draw_ctx):
        result = self.tool.execute(
            draw_ctx, shape_type="line", x=0, y=0, width=100, height=100
        )
        assert result["status"] == "ok"

    def test_invalid_enum(self):
        ok, err = self.tool.validate(
            shape_type="hexagon", x=0, y=0, width=100, height=100
        )
        assert ok is False


class TestEditShape:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = EditShape()

    def test_validate_required(self):
        ok, err = self.tool.validate()
        assert ok is False
        assert "shape_index" in err

    def test_validate_with_required(self):
        ok, _ = self.tool.validate(shape_index=0)
        assert ok is True

    def test_doc_types_all(self):
        assert self.tool.doc_types is None

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is True

    def test_happy_path_move(self, draw_ctx):
        result = self.tool.execute(draw_ctx, shape_index=0, x=9999, y=8888)
        assert result["status"] == "ok"
        shape = draw_ctx.doc.getDrawPages().getByIndex(0).getByIndex(0)
        assert shape.getPosition().X == 9999
        assert shape.getPosition().Y == 8888

    def test_happy_path_resize(self, draw_ctx):
        result = self.tool.execute(draw_ctx, shape_index=0, width=7777, height=6666)
        assert result["status"] == "ok"
        shape = draw_ctx.doc.getDrawPages().getByIndex(0).getByIndex(0)
        assert shape.getSize().Width == 7777

    def test_edit_text(self, draw_ctx):
        result = self.tool.execute(draw_ctx, shape_index=0, text="Updated")
        assert result["status"] == "ok"
        shape = draw_ctx.doc.getDrawPages().getByIndex(0).getByIndex(0)
        assert shape.getString() == "Updated"

    def test_out_of_range_shape(self, draw_ctx):
        with pytest.raises(IndexError):
            self.tool.execute(draw_ctx, shape_index=99)


class TestDeleteShape:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = DeleteShape()

    def test_validate_required(self):
        ok, err = self.tool.validate()
        assert ok is False
        assert "shape_index" in err

    def test_validate_with_required(self):
        ok, _ = self.tool.validate(shape_index=0)
        assert ok is True

    def test_doc_types_all(self):
        assert self.tool.doc_types is None

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is True

    def test_happy_path(self, draw_ctx):
        assert draw_ctx.doc.getDrawPages().getByIndex(0).getCount() == 1
        result = self.tool.execute(draw_ctx, shape_index=0)
        assert result["status"] == "ok"
        assert draw_ctx.doc.getDrawPages().getByIndex(0).getCount() == 0

    def test_out_of_range(self, draw_ctx):
        with pytest.raises(IndexError):
            self.tool.execute(draw_ctx, shape_index=5)


# ── pages.py ──────────────────────────────────────────────────────


class TestAddSlide:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = AddSlide()

    def test_validate_no_required(self):
        ok, _ = self.tool.validate()
        assert ok is True

    def test_doc_types_draw_impress(self):
        assert self.tool.doc_types == ["draw", "impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is True

    def test_happy_path(self, draw_ctx):
        result = self.tool.execute(draw_ctx)
        assert result["status"] == "ok"
        assert draw_ctx.doc.getDrawPages().getCount() == 2

    def test_happy_path_impress(self, impress_ctx):
        result = self.tool.execute(impress_ctx)
        assert result["status"] == "ok"
        assert impress_ctx.doc.getDrawPages().getCount() == 2

    def test_with_index(self, draw_ctx):
        result = self.tool.execute(draw_ctx, index=0)
        assert result["status"] == "ok"
        assert draw_ctx.doc.getDrawPages().getCount() == 2


class TestDeleteSlide:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = DeleteSlide()

    def test_validate_required(self):
        ok, err = self.tool.validate()
        assert ok is False
        assert "index" in err

    def test_validate_with_required(self):
        ok, _ = self.tool.validate(index=0)
        assert ok is True

    def test_doc_types_draw_impress(self):
        assert self.tool.doc_types == ["draw", "impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is True

    def test_happy_path(self, draw_ctx):
        draw_ctx.doc.add_page()
        assert draw_ctx.doc.getDrawPages().getCount() == 2
        result = self.tool.execute(draw_ctx, index=0)
        assert result["status"] == "ok"
        assert draw_ctx.doc.getDrawPages().getCount() == 1

    def test_out_of_range(self, draw_ctx):
        with pytest.raises(IndexError):
            self.tool.execute(draw_ctx, index=99)


class TestReadSlideText:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = ReadSlideText()

    def test_validate_no_required(self):
        ok, _ = self.tool.validate()
        assert ok is True

    def test_doc_types_draw_impress(self):
        assert self.tool.doc_types == ["draw", "impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is False

    def test_happy_path(self, draw_ctx):
        result = self.tool.execute(draw_ctx)
        assert result["status"] == "ok"
        assert len(result["texts"]) == 1
        assert result["texts"][0]["text"] == "Hello"

    def test_with_page_index(self, draw_ctx):
        draw_ctx.doc.add_page()
        result = self.tool.execute(draw_ctx, page_index=0)
        assert result["status"] == "ok"
        assert len(result["texts"]) == 1

    def test_out_of_range_page(self, draw_ctx):
        result = self.tool.execute(draw_ctx, page_index=99)
        assert result["status"] == "error"

    def test_empty_page(self, empty_draw_ctx):
        empty_draw_ctx.doc.add_page()
        result = self.tool.execute(empty_draw_ctx)
        assert result["status"] == "ok"
        assert len(result["texts"]) == 0

    def test_notes_included(self, impress_ctx):
        result = self.tool.execute(impress_ctx)
        assert result["status"] == "ok"
        assert result["notes"] == "Welcome everyone"


class TestGetPresentationInfo:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = GetPresentationInfo()

    def test_validate_no_required(self):
        ok, _ = self.tool.validate()
        assert ok is True

    def test_doc_types_draw_impress(self):
        assert self.tool.doc_types == ["draw", "impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is False

    def test_happy_path_draw(self, draw_ctx):
        result = self.tool.execute(draw_ctx)
        assert result["status"] == "ok"
        assert result["slide_count"] == 1
        assert result["is_impress"] is False

    def test_happy_path_impress(self, impress_ctx):
        result = self.tool.execute(impress_ctx)
        assert result["status"] == "ok"
        assert result["is_impress"] is True

    def test_master_slides(self, draw_ctx):
        result = self.tool.execute(draw_ctx)
        assert result["status"] == "ok"
        assert len(result["master_slides"]) >= 0

    def test_empty_doc(self, empty_draw_ctx):
        result = self.tool.execute(empty_draw_ctx)
        assert result["status"] == "ok"
        assert result["slide_count"] == 0


# ── masters.py (parameter validation + mutation) ──────────────────


class TestListMasterSlides:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = ListMasterSlides()

    def test_validate_no_required(self):
        ok, _ = self.tool.validate()
        assert ok is True

    def test_doc_types(self):
        assert self.tool.doc_types == ["draw", "impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is False

    def test_happy_path(self, draw_ctx):
        result = self.tool.execute(draw_ctx)
        assert result["status"] == "ok"
        assert result["count"] >= 0


class TestGetSlideMaster:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = GetSlideMaster()

    def test_validate_no_required(self):
        ok, _ = self.tool.validate()
        assert ok is True

    def test_doc_types(self):
        assert self.tool.doc_types == ["draw", "impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is False

    def test_happy_path(self, draw_ctx):
        page = draw_ctx.doc.getDrawPages().getByIndex(0)
        page.MasterPage = draw_ctx.doc._master_pages[0]
        result = self.tool.execute(draw_ctx, page_index=0)
        assert result["status"] == "ok"


class TestSetSlideMaster:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = SetSlideMaster()

    def test_validate_required(self):
        ok, err = self.tool.validate()
        assert ok is False
        assert "master_name" in err

    def test_validate_with_required(self):
        ok, _ = self.tool.validate(master_name="Default")
        assert ok is True

    def test_doc_types(self):
        assert self.tool.doc_types == ["draw", "impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is True

    def test_happy_path(self, draw_ctx):
        result = self.tool.execute(draw_ctx, master_name="Default", page_index=0)
        assert result["status"] == "ok"
        assert result["master_name"] == "Default"

    def test_unknown_master(self, draw_ctx):
        result = self.tool.execute(draw_ctx, master_name="NonExistent", page_index=0)
        assert result["status"] == "error"


# ── notes.py (parameter validation + mutation) ───────────────────


class TestGetSpeakerNotes:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = GetSpeakerNotes()

    def test_validate_no_required(self):
        ok, _ = self.tool.validate()
        assert ok is True

    def test_doc_types_impress_only(self):
        assert self.tool.doc_types == ["impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is False

    def test_happy_path(self, impress_ctx):
        result = self.tool.execute(impress_ctx, page_index=0)
        assert result["status"] == "ok"
        assert result["notes"] == "Welcome everyone"


class TestSetSpeakerNotes:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = SetSpeakerNotes()

    def test_validate_required(self):
        ok, err = self.tool.validate()
        assert ok is False
        assert "text" in err

    def test_validate_with_required(self):
        ok, _ = self.tool.validate(text="New notes")
        assert ok is True

    def test_doc_types_impress_only(self):
        assert self.tool.doc_types == ["impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is True

    def test_happy_path(self, impress_ctx):
        result = self.tool.execute(impress_ctx, text="New notes", page_index=0)
        assert result["status"] == "ok"

    def test_append(self, impress_ctx):
        result = self.tool.execute(
            impress_ctx, text="appended", page_index=0, append=True
        )
        assert result["status"] == "ok"


# ── transitions.py (parameter validation + mutation) ──────────────


class TestGetSlideTransition:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = GetSlideTransition()

    def test_validate_no_required(self):
        ok, _ = self.tool.validate()
        assert ok is True

    def test_doc_types_impress_only(self):
        assert self.tool.doc_types == ["impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is False

    def test_happy_path(self, impress_ctx):
        result = self.tool.execute(impress_ctx)
        assert result["status"] == "ok"
        assert "effect" in result


class TestSetSlideTransition:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = SetSlideTransition()

    def test_validate_no_required(self):
        ok, _ = self.tool.validate()
        assert ok is True

    def test_doc_types_impress_only(self):
        assert self.tool.doc_types == ["impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is True

    def test_speed_enum(self):
        ok, err = self.tool.validate(speed="turbo")
        assert ok is False
        assert "speed" in err

    def test_advance_enum(self):
        ok, err = self.tool.validate(advance="manually")
        assert ok is False
        assert "advance" in err


class TestGetSlideLayout:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = GetSlideLayout()

    def test_validate_no_required(self):
        ok, _ = self.tool.validate()
        assert ok is True

    def test_doc_types_impress_only(self):
        assert self.tool.doc_types == ["impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is False

    def test_happy_path(self, impress_ctx):
        result = self.tool.execute(impress_ctx)
        assert result["status"] == "ok"
        assert "layout_id" in result


class TestSetSlideLayout:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = SetSlideLayout()

    def test_validate_required(self):
        ok, err = self.tool.validate()
        assert ok is False
        assert "layout" in err

    def test_doc_types_impress_only(self):
        assert self.tool.doc_types == ["impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is True

    def test_invalid_layout(self, impress_ctx):
        result = self.tool.execute(impress_ctx, layout="nonexistent")
        assert result["status"] == "error"

    def test_valid_layout(self, impress_ctx):
        result = self.tool.execute(impress_ctx, layout="blank")
        assert result["status"] == "ok"


# ── placeholders.py (parameter validation + mutation) ─────────────


class TestListPlaceholders:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = ListPlaceholders()

    def test_validate_no_required(self):
        ok, _ = self.tool.validate()
        assert ok is True

    def test_doc_types(self):
        assert self.tool.doc_types == ["draw", "impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is False

    def test_happy_path(self, draw_ctx):
        result = self.tool.execute(draw_ctx)
        assert result["status"] == "ok"
        assert result["count"] == 1


class TestGetPlaceholderText:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = GetPlaceholderText()

    def test_validate_no_required(self):
        ok, _ = self.tool.validate()
        assert ok is True

    def test_doc_types(self):
        assert self.tool.doc_types == ["draw", "impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is False

    def test_by_shape_index(self, draw_ctx):
        result = self.tool.execute(draw_ctx, shape_index=0)
        assert result["status"] == "ok"
        assert result["text"] == "Hello"

    def test_out_of_range_shape_index(self, draw_ctx):
        result = self.tool.execute(draw_ctx, shape_index=99)
        assert result["status"] == "error"

    def test_no_role_or_index(self, draw_ctx):
        result = self.tool.execute(draw_ctx)
        assert result["status"] == "error"


class TestSetPlaceholderText:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tool = SetPlaceholderText()

    def test_validate_required(self):
        ok, err = self.tool.validate()
        assert ok is False
        assert "text" in err

    def test_validate_with_required(self):
        ok, _ = self.tool.validate(text="Hello")
        assert ok is True

    def test_doc_types(self):
        assert self.tool.doc_types == ["draw", "impress"]

    def test_detects_mutation(self):
        assert self.tool.detects_mutation() is True

    def test_happy_path(self, draw_ctx):
        result = self.tool.execute(draw_ctx, text="New text", shape_index=0)
        assert result["status"] == "ok"
        shape = draw_ctx.doc.getDrawPages().getByIndex(0).getByIndex(0)
        assert shape.getString() == "New text"

    def test_out_of_range_shape_index(self, draw_ctx):
        result = self.tool.execute(draw_ctx, text="x", shape_index=99)
        assert result["status"] == "error"

    def test_no_role_or_index(self, draw_ctx):
        result = self.tool.execute(draw_ctx, text="x")
        assert result["status"] == "error"
