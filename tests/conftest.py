import os
import sys
import pytest

_tests_dir = os.path.dirname(os.path.abspath(__file__))
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

from stubs.writer_stubs import WriterDocStub
from stubs.calc_stubs import CalcDocStub
from stubs.draw_stubs import DrawDocStub
from stubs.service_stubs import StubServiceRegistry
from plugin.framework.tool_context import ToolContext


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
def calc_doc():
    doc = CalcDocStub()
    sheet = doc.add_sheet("Sheet1")
    sheet.set_cell("A1", "Name")
    sheet.set_cell("B1", "Value")
    sheet.set_cell("A2", "Test")
    sheet.set_cell("B2", 42)
    return doc


@pytest.fixture
def draw_doc():
    doc = DrawDocStub(doc_type="draw")
    page = doc.add_page()
    page.add_shape(
        "RectangleShape", x=1000, y=1000, width=5000, height=3000, text="Hello"
    )
    return doc


@pytest.fixture(params=["writer_doc", "calc_doc", "draw_doc"])
def any_doc(request):
    return request.getfixturevalue(request.param)


@pytest.fixture
def services():
    return StubServiceRegistry()


@pytest.fixture
def writer_services(writer_doc):
    return StubServiceRegistry(doc=writer_doc)


@pytest.fixture
def calc_services(calc_doc):
    return StubServiceRegistry(doc=calc_doc)


@pytest.fixture
def draw_services(draw_doc):
    return StubServiceRegistry(doc=draw_doc)


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
def calc_context(calc_doc, calc_services):
    return ToolContext(
        doc=calc_doc,
        ctx=None,
        doc_type="calc",
        services=calc_services,
        caller="test",
    )


@pytest.fixture
def draw_context(draw_doc, draw_services):
    return ToolContext(
        doc=draw_doc,
        ctx=None,
        doc_type="draw",
        services=draw_services,
        caller="test",
    )
