from stubs.writer_stubs import WriterDocStub, ParagraphStub, TextStub
from stubs.calc_stubs import CalcDocStub, SheetStub, CellStub, CellRangeStub
from stubs.draw_stubs import DrawDocStub, DrawPageStub, ShapeStub
from stubs.service_stubs import (
    StubServiceRegistry,
    StubDocumentService,
    StubConfigService,
)
from stubs.uno_stubs import install_uno_stubs, Point, Size, PropertyHolder


class TestUnoStubs:
    def test_install_uno_stubs(self):
        install_uno_stubs()
        import uno

        assert hasattr(uno, "systemPathToFileUrl")

    def test_property_holder(self):
        ph = PropertyHolder(Foo=1, Bar="hello")
        assert ph.getPropertyValue("Foo") == 1
        assert ph.getPropertyValue("Bar") == "hello"
        ph.setPropertyValue("Foo", 2)
        assert ph.getPropertyValue("Foo") == 2
        try:
            ph.getPropertyValue("Missing")
            assert False, "Should have raised"
        except AttributeError:
            pass

    def test_point_and_size(self):
        p = Point(100, 200)
        assert p.X == 100
        assert p.Y == 200
        s = Size(50, 75)
        assert s.Width == 50
        assert s.Height == 75


class TestWriterStubs:
    def test_create_writer_doc(self):
        doc = WriterDocStub()
        doc.add_paragraph("Hello", style="Text Body")
        text = doc.getText()
        assert text.getString() == "Hello"

    def test_multiple_paragraphs(self):
        doc = WriterDocStub()
        doc.add_paragraph("First", style="Text Body")
        doc.add_paragraph("Second", style="Text Body")
        text = doc.getText()
        assert text.getString() == "First\nSecond"

    def test_heading_outline_levels(self):
        doc = WriterDocStub()
        doc.add_paragraph("Title", style="Heading 1")
        assert doc._paragraphs[0].outline_level == 1
        doc.add_paragraph("Body", style="Text Body")
        assert doc._paragraphs[1].outline_level == 0

    def test_enumeration(self):
        doc = WriterDocStub()
        doc.add_paragraph("A", style="Text Body")
        doc.add_paragraph("B", style="Text Body")
        text = doc.getText()
        enum = text.createEnumeration()
        items = []
        while enum.hasMoreElements():
            items.append(enum.nextElement())
        assert len(items) == 2
        assert items[0].getString() == "A"
        assert items[1].getString() == "B"

    def test_supports_service(self):
        doc = WriterDocStub()
        assert doc.supportsService("com.sun.star.text.TextDocument")
        assert not doc.supportsService("com.sun.star.sheet.SpreadsheetDocument")

    def test_get_url(self):
        doc = WriterDocStub()
        assert doc.getURL() == "test://writer"

    def test_paragraph_properties(self):
        doc = WriterDocStub()
        p = doc.add_paragraph("Hello", style="Heading 1")
        assert p.getPropertyValue("ParaStyleName") == "Heading 1"
        assert p.getPropertyValue("OutlineLevel") == 1
        p.setPropertyValue("ParaStyleName", "Text Body")
        assert p.getPropertyValue("ParaStyleName") == "Text Body"

    def test_style_families(self):
        doc = WriterDocStub()
        families = doc.getStyleFamilies()
        assert families.hasByName("ParagraphStyles")
        para_styles = families.getByName("ParagraphStyles")
        assert "Heading 1" in para_styles.getElementNames()

    def test_draw_page(self):
        doc = WriterDocStub()
        dp = doc.getDrawPage()
        assert dp.getCount() == 0

    def test_replace_descriptor(self):
        doc = WriterDocStub()
        doc.add_paragraph("Hello World", style="Text Body")
        rd = doc.createReplaceDescriptor()
        rd.SearchString = "Hello"
        rd.ReplaceString = "Hi"
        count = doc.replaceAll(rd)
        assert count == 1
        assert doc._paragraphs[0].getString() == "Hi World"


class TestCalcStubs:
    def test_create_calc_doc(self):
        doc = CalcDocStub()
        sheet = doc.add_sheet("Sheet1")
        sheet.set_cell("A1", 42)
        cell = sheet.getCellByPosition(0, 0)
        assert cell.getValue() == 42.0

    def test_cell_string(self):
        doc = CalcDocStub()
        sheet = doc.add_sheet("Data")
        sheet.set_cell("A1", "Hello")
        cell = sheet.getCellByPosition(0, 0)
        assert cell.getString() == "Hello"

    def test_cell_formula(self):
        doc = CalcDocStub()
        sheet = doc.add_sheet("Sheet1")
        cell = sheet.getCellByPosition(0, 0)
        cell.setFormula("=SUM(A1:A10)")
        assert cell.getFormula() == "=SUM(A1:A10)"

    def test_sheets_collection(self):
        doc = CalcDocStub()
        doc.add_sheet("First")
        doc.add_sheet("Second")
        sheets = doc.getSheets()
        assert sheets.getCount() == 2
        assert sheets.hasByName("First")
        assert not sheets.hasByName("Third")
        s2 = sheets.getByName("Second")
        assert s2.getName() == "Second"

    def test_controller(self):
        doc = CalcDocStub()
        sheet = doc.add_sheet("Sheet1")
        ctrl = doc.getCurrentController()
        assert ctrl.getActiveSheet() is sheet

    def test_supports_service(self):
        doc = CalcDocStub()
        assert doc.supportsService("com.sun.star.sheet.SpreadsheetDocument")
        assert not doc.supportsService("com.sun.star.text.TextDocument")

    def test_cell_range(self):
        doc = CalcDocStub()
        sheet = doc.add_sheet("Sheet1")
        rng = sheet.getCellRangeByPosition(0, 0, 2, 2)
        rng.merge(True)
        assert rng._merged is True


class TestDrawStubs:
    def test_create_draw_doc(self):
        doc = DrawDocStub(doc_type="draw")
        page = doc.add_page()
        page.add_shape("RectangleShape", x=100, y=200, width=300, height=400)
        pages = doc.getDrawPages()
        assert pages.getCount() == 1
        assert page.getCount() == 1

    def test_shape_properties(self):
        doc = DrawDocStub(doc_type="impress")
        page = doc.add_page()
        shape = page.add_shape("RectangleShape", x=100, y=200, width=300, height=400)
        assert shape.getShapeType() == "com.sun.star.drawing.RectangleShape"
        pos = shape.getPosition()
        assert pos.X == 100
        assert pos.Y == 200
        sz = shape.getSize()
        assert sz.Width == 300
        assert sz.Height == 400
        shape.setPosition(Point(500, 600))
        assert shape.getPosition().X == 500

    def test_supports_service(self):
        draw_doc = DrawDocStub(doc_type="draw")
        assert draw_doc.supportsService("com.sun.star.drawing.DrawingDocument")
        impress_doc = DrawDocStub(doc_type="impress")
        assert impress_doc.supportsService(
            "com.sun.star.presentation.PresentationDocument"
        )

    def test_create_shape_via_instance(self):
        doc = DrawDocStub(doc_type="draw")
        page = doc.add_page()
        shape = doc.createInstance("com.sun.star.drawing.TextShape")
        page.add(shape)
        assert page.getCount() == 1


class TestServiceStubs:
    def test_document_service_writer(self):
        doc = WriterDocStub()
        doc.add_paragraph("Hello", style="Heading 1")
        svc = StubDocumentService(doc)
        assert svc.detect_doc_type(doc) == "writer"
        assert svc.is_writer(doc)

    def test_document_service_calc(self):
        doc = CalcDocStub()
        doc.add_sheet("Sheet1")
        svc = StubDocumentService(doc)
        assert svc.detect_doc_type(doc) == "calc"

    def test_document_service_draw(self):
        doc = DrawDocStub(doc_type="draw")
        svc = StubDocumentService(doc)
        assert svc.detect_doc_type(doc) == "draw"

    def test_paragraph_ranges(self):
        doc = WriterDocStub()
        doc.add_paragraph("First", style="Text Body")
        doc.add_paragraph("Second", style="Text Body")
        svc = StubDocumentService(doc)
        ranges = svc.get_paragraph_ranges(doc)
        assert len(ranges) == 2

    def test_heading_tree(self):
        doc = WriterDocStub()
        doc.add_paragraph("Title", style="Heading 1")
        doc.add_paragraph("Body text", style="Text Body")
        doc.add_paragraph("Subtitle", style="Heading 2")
        svc = StubDocumentService(doc)
        tree = svc.build_heading_tree(doc)
        assert len(tree) == 1
        assert tree[0]["text"] == "Title"
        assert len(tree[0]["children"]) == 1
        assert tree[0]["children"][0]["text"] == "Subtitle"

    def test_resolve_locator(self):
        doc = WriterDocStub()
        doc.add_paragraph("Hello", style="Text Body")
        svc = StubDocumentService(doc)
        result = svc.resolve_locator(doc, "paragraph:0")
        assert result["para_index"] == 0
        result = svc.resolve_locator(doc, "first:")
        assert result["para_index"] == 0

    def test_config_service(self):
        reg = StubServiceRegistry()
        config = reg.get("config")
        config.set("test.key", "value")
        assert config.get("test.key") == "value"

    def test_event_bus(self):
        reg = StubServiceRegistry()
        events = reg.get("events")
        received = []
        events.subscribe("test:event", lambda **kw: received.append(kw))
        events.emit("test:event", data=42)
        assert len(received) == 1
        assert received[0]["data"] == 42

    def test_full_registry(self):
        reg = StubServiceRegistry()
        assert reg.get("document") is not None
        assert reg.get("config") is not None
        assert reg.get("events") is not None
        assert reg.get("format") is not None
        assert reg.get("writer_tree") is not None
        assert reg.get("tools") is not None


class TestConftestFixtures:
    def test_writer_doc_fixture(self, writer_doc):
        assert len(writer_doc._paragraphs) == 6
        assert writer_doc._paragraphs[0].getString() == "Introduction"
        assert writer_doc._paragraphs[0].para_style_name == "Heading 1"

    def test_calc_doc_fixture(self, calc_doc):
        sheets = calc_doc.getSheets()
        assert sheets.hasByName("Sheet1")
        sheet = sheets.getByName("Sheet1")
        cell = sheet.getCellByPosition(0, 0)
        assert cell.getString() == "Name"

    def test_draw_doc_fixture(self, draw_doc):
        pages = draw_doc.getDrawPages()
        assert pages.getCount() == 1

    def test_services_fixture(self, services):
        assert services.get("document") is not None
        assert services.get("config") is not None

    def test_tool_context_fixture(self, tool_context):
        assert tool_context.doc_type == "writer"
        assert tool_context.doc is not None
        assert tool_context.services is not None
