import pytest

from stubs.uno_stubs import install_uno_stubs

install_uno_stubs()

from stubs.calc_stubs import CalcDocStub, SheetStub, CellStub, CellRangeStub
from stubs.writer_stubs import WriterDocStub
from stubs.service_stubs import StubServiceRegistry
from plugin.framework.tool_context import ToolContext
from plugin.modules.calc.tools.cells import (
    ReadCellRange,
    WriteCellRange,
    SetCellStyle,
    MergeCells,
    ClearRange,
    SortRange,
    ImportCsv,
    WriteCellRangeFromLists,
    DeleteStructure,
)
from plugin.modules.calc.tools.sheets import (
    ListSheets,
    SwitchSheet,
    CreateSheet,
    GetSheetSummary,
    CreateChart,
)
from plugin.modules.calc.tools.search import (
    SearchInSpreadsheet,
    ReplaceInSpreadsheet,
)
from plugin.modules.calc.tools.navigation import (
    ListNamedRanges,
    GetSheetOverview,
)
from plugin.modules.calc.tools.formulas import DetectErrors
from plugin.modules.calc.tools.conditional import (
    ListConditionalFormats,
    AddConditionalFormat,
    RemoveConditionalFormat,
    ClearConditionalFormats,
)
from plugin.modules.calc.tools.comments import (
    ListCellComments,
    AddCellComment,
    DeleteCellComment,
)
from plugin.modules.calc.tools.charts import (
    ListCharts,
    GetChartInfo,
    EditChart,
    DeleteChart,
)


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
def calc_services(calc_doc):
    return StubServiceRegistry(doc=calc_doc)


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
def writer_doc():
    doc = WriterDocStub()
    doc.add_paragraph("Hello", style="Text Body")
    return doc


@pytest.fixture
def writer_context(writer_doc):
    return ToolContext(
        doc=writer_doc,
        ctx=None,
        doc_type="writer",
        services=StubServiceRegistry(doc=writer_doc),
        caller="test",
    )


ALL_TOOLS = [
    ReadCellRange,
    WriteCellRange,
    SetCellStyle,
    MergeCells,
    ClearRange,
    SortRange,
    ImportCsv,
    WriteCellRangeFromLists,
    DeleteStructure,
    ListSheets,
    SwitchSheet,
    CreateSheet,
    GetSheetSummary,
    CreateChart,
    SearchInSpreadsheet,
    ReplaceInSpreadsheet,
    ListNamedRanges,
    GetSheetOverview,
    DetectErrors,
    ListConditionalFormats,
    AddConditionalFormat,
    RemoveConditionalFormat,
    ClearConditionalFormats,
    ListCellComments,
    AddCellComment,
    DeleteCellComment,
    ListCharts,
    GetChartInfo,
    EditChart,
    DeleteChart,
]


class TestParameterValidation:
    @pytest.mark.parametrize("tool_cls", ALL_TOOLS, ids=lambda t: t.name)
    def test_missing_required_params(self, tool_cls):
        tool = tool_cls()
        schema = tool.parameters or {}
        required = schema.get("required", [])
        if not required:
            ok, err = tool.validate()
            assert ok is True
            return
        ok, err = tool.validate()
        assert ok is False
        assert "Missing required" in err

    @pytest.mark.parametrize("tool_cls", ALL_TOOLS, ids=lambda t: t.name)
    def test_valid_all_required(self, tool_cls):
        tool = tool_cls()
        schema = tool.parameters or {}
        required = schema.get("required", [])
        props = schema.get("properties", {})
        kwargs = {}
        for r in required:
            prop = props.get(r, {})
            if "enum" in prop:
                kwargs[r] = prop["enum"][0]
            elif prop.get("type") == "string":
                kwargs[r] = "test"
            elif prop.get("type") == "integer":
                kwargs[r] = 0
            elif prop.get("type") == "number":
                kwargs[r] = 1.0
            elif prop.get("type") == "boolean":
                kwargs[r] = True
            elif isinstance(prop.get("type"), list):
                if "string" in prop["type"]:
                    kwargs[r] = "test"
                elif "integer" in prop["type"]:
                    kwargs[r] = 0
                else:
                    kwargs[r] = "test"
            elif prop.get("type") == "array":
                kwargs[r] = []
            else:
                kwargs[r] = "test"
        ok, err = tool.validate(**kwargs)
        assert ok is True


class TestDocTypeFiltering:
    @pytest.mark.parametrize("tool_cls", ALL_TOOLS, ids=lambda t: t.name)
    def test_calc_doc_type(self, tool_cls):
        tool = tool_cls()
        assert tool.doc_types == ["calc"]

    @pytest.mark.parametrize("tool_cls", ALL_TOOLS, ids=lambda t: t.name)
    def test_rejects_writer_doc_type(self, tool_cls):
        tool = tool_cls()
        assert "writer" not in (tool.doc_types or [])


class TestMutationDetection:
    MUTATION_TOOLS = [
        WriteCellRange,
        SetCellStyle,
        MergeCells,
        ClearRange,
        SortRange,
        ImportCsv,
        WriteCellRangeFromLists,
        DeleteStructure,
        SwitchSheet,
        CreateSheet,
        CreateChart,
        ReplaceInSpreadsheet,
        AddConditionalFormat,
        RemoveConditionalFormat,
        ClearConditionalFormats,
        AddCellComment,
        DeleteCellComment,
        EditChart,
        DeleteChart,
    ]

    NON_MUTATION_TOOLS = [
        ReadCellRange,
        ListSheets,
        GetSheetSummary,
        SearchInSpreadsheet,
        ListNamedRanges,
        GetSheetOverview,
        DetectErrors,
        ListConditionalFormats,
        ListCellComments,
        ListCharts,
        GetChartInfo,
    ]

    @pytest.mark.parametrize("tool_cls", MUTATION_TOOLS, ids=lambda t: t.name)
    def test_is_mutation(self, tool_cls):
        tool = tool_cls()
        assert tool.detects_mutation() is True

    @pytest.mark.parametrize("tool_cls", NON_MUTATION_TOOLS, ids=lambda t: t.name)
    def test_is_not_mutation(self, tool_cls):
        tool = tool_cls()
        assert tool.detects_mutation() is False


class TestReadCellRange:
    def test_read_single_cell(self, calc_context):
        tool = ReadCellRange()
        result = tool.execute(calc_context, range_name="A1")
        assert result["status"] == "ok"
        assert result["result"] is not None

    def test_read_range(self, calc_context):
        tool = ReadCellRange()
        result = tool.execute(calc_context, range_name="A1:B2")
        assert result["status"] == "ok"
        data = result["result"]
        assert len(data) == 2
        assert len(data[0]) == 2

    def test_read_range_values(self, calc_context):
        tool = ReadCellRange()
        result = tool.execute(calc_context, range_name="A1:B2")
        assert result["status"] == "ok"
        data = result["result"]
        assert data[0][0]["value"] == "Name"
        assert data[1][1]["value"] == 42.0

    def test_read_list_of_ranges(self, calc_context):
        tool = ReadCellRange()
        result = tool.execute(calc_context, range_name=["A1", "B2"])
        assert result["status"] == "ok"
        assert len(result["result"]) == 2


class TestWriteCellRange:
    def test_write_single_value(self, calc_context):
        tool = WriteCellRange()
        result = tool.execute(calc_context, range_name="C1", formula_or_values=99)
        assert result["status"] == "ok"

    def test_write_formula(self, calc_context):
        tool = WriteCellRange()
        result = tool.execute(calc_context, range_name="C1", formula_or_values="=B2*2")
        assert result["status"] == "ok"

    def test_write_list_of_ranges(self, calc_context):
        tool = WriteCellRange()
        result = tool.execute(
            calc_context, range_name=["C1", "D1"], formula_or_values=1
        )
        assert result["status"] == "ok"
        assert "2 ranges" in result["message"]


class TestSetCellStyle:
    def test_set_bold(self, calc_context):
        tool = SetCellStyle()
        result = tool.execute(calc_context, range_name="A1", bold=True)
        assert result["status"] == "ok"

    def test_set_style_with_bg_color(self, calc_context):
        tool = SetCellStyle()
        result = tool.execute(calc_context, range_name="A1", bg_color="yellow")
        assert result["status"] == "ok"

    def test_set_style_hex_color(self, calc_context):
        tool = SetCellStyle()
        result = tool.execute(calc_context, range_name="A1", font_color="#FF0000")
        assert result["status"] == "ok"


class TestMergeCells:
    def test_merge_range(self, calc_context):
        tool = MergeCells()
        result = tool.execute(calc_context, range_name="A1:D1")
        assert result["status"] == "ok"
        assert "Merged" in result["message"]

    def test_merge_no_center(self, calc_context):
        tool = MergeCells()
        result = tool.execute(calc_context, range_name="A1:D1", center=False)
        assert result["status"] == "ok"


class TestClearRange:
    def test_clear_range(self, calc_context):
        tool = ClearRange()
        result = tool.execute(calc_context, range_name="A1:B2")
        assert result["status"] == "ok"
        assert "Cleared" in result["message"]


class TestSortRange:
    def test_sort_range_default(self, calc_context):
        tool = SortRange()
        result = tool.execute(calc_context, range_name="A1:B2")
        assert result["status"] == "ok"

    def test_sort_descending(self, calc_context):
        tool = SortRange()
        result = tool.execute(calc_context, range_name="A1:B2", ascending=False)
        assert result["status"] == "ok"


class TestImportCsv:
    def test_import_csv(self, calc_context):
        tool = ImportCsv()
        result = tool.execute(calc_context, csv_data="X,Y\n1,2\n3,4")
        assert result["status"] == "ok"
        assert "Imported" in result["message"]


class TestWriteCellRangeFromLists:
    def test_write_2d_values(self, calc_context):
        tool = WriteCellRangeFromLists()
        result = tool.execute(
            calc_context, start_cell="C1", values=[["A", "B"], [1, 2]]
        )
        assert result["status"] == "ok"
        assert "2 rows" in result["message"]

    def test_write_with_formulas(self, calc_context):
        tool = WriteCellRangeFromLists()
        result = tool.execute(calc_context, start_cell="C1", values=[["=SUM(B1:B2)"]])
        assert result["status"] == "ok"

    def test_write_to_missing_sheet(self, calc_context):
        tool = WriteCellRangeFromLists()
        result = tool.execute(
            calc_context, start_cell="C1", values=[["x"]], sheet_name="NoSheet"
        )
        assert result["status"] == "error"

    def test_empty_values_array(self, calc_context):
        tool = WriteCellRangeFromLists()
        result = tool.execute(calc_context, start_cell="C1", values=[])
        assert result["status"] == "ok"
        assert "0 rows" in result["message"]


class TestDeleteStructure:
    def test_delete_rows(self, calc_context):
        tool = DeleteStructure()
        result = tool.execute(calc_context, structure_type="rows", start=1)
        assert result["status"] == "ok"

    def test_delete_columns(self, calc_context):
        tool = DeleteStructure()
        result = tool.execute(calc_context, structure_type="columns", start="A")
        assert result["status"] == "ok"

    def test_delete_invalid_type(self, calc_context):
        tool = DeleteStructure()
        result = tool.execute(calc_context, structure_type="invalid", start=1)
        assert result["status"] == "error"

    def test_validate_enum(self):
        tool = DeleteStructure()
        ok, err = tool.validate(structure_type="bad", start=1)
        assert ok is False


class TestListSheets:
    def test_list_sheets(self, calc_context):
        tool = ListSheets()
        result = tool.execute(calc_context)
        assert result["status"] == "ok"
        assert "Sheet1" in result["result"]

    def test_list_sheets_multi(self, calc_context):
        calc_context.doc.add_sheet("Sheet2")
        tool = ListSheets()
        result = tool.execute(calc_context)
        assert result["status"] == "ok"
        assert len(result["result"]) == 2


class TestSwitchSheet:
    def test_switch_sheet(self, calc_context):
        calc_context.doc.add_sheet("Other")
        tool = SwitchSheet()
        result = tool.execute(calc_context, sheet_name="Other")
        assert result["status"] == "ok"

    def test_switch_missing_sheet(self, calc_context):
        tool = SwitchSheet()
        result = tool.execute(calc_context, sheet_name="NotFound")
        assert result["status"] == "error"


class TestCreateSheet:
    def test_create_sheet(self, calc_context):
        tool = CreateSheet()
        result = tool.execute(calc_context, sheet_name="NewSheet")
        assert result["status"] == "ok"

    def test_create_sheet_with_position(self, calc_context):
        tool = CreateSheet()
        result = tool.execute(calc_context, sheet_name="PosSheet", position=0)
        assert result["status"] == "ok"


class TestGetSheetSummary:
    def test_sheet_summary(self, calc_context):
        tool = GetSheetSummary()
        result = tool.execute(calc_context)
        assert result["status"] == "ok"
        assert "sheet_name" in result["result"]

    def test_sheet_summary_named(self, calc_context):
        tool = GetSheetSummary()
        result = tool.execute(calc_context, sheet_name="Sheet1")
        assert result["status"] == "ok"
        assert result["result"]["sheet_name"] == "Sheet1"


class TestSearchInSpreadsheet:
    def test_search_finds_match(self, calc_context):
        tool = SearchInSpreadsheet()
        result = tool.execute(calc_context, pattern="Name")
        assert result["status"] == "ok"
        assert result["count"] >= 1

    def test_search_no_match(self, calc_context):
        tool = SearchInSpreadsheet()
        result = tool.execute(calc_context, pattern="ZZZZNOTFOUND")
        assert result["status"] == "ok"
        assert result["count"] == 0

    def test_search_empty_pattern(self, calc_context):
        tool = SearchInSpreadsheet()
        result = tool.execute(calc_context, pattern="")
        assert result["status"] == "error"

    def test_search_all_sheets(self, calc_context):
        calc_context.doc.add_sheet("Sheet2")
        tool = SearchInSpreadsheet()
        result = tool.execute(calc_context, pattern="Name", all_sheets=True)
        assert result["status"] == "ok"

    def test_search_case_sensitive(self, calc_context):
        tool = SearchInSpreadsheet()
        result = tool.execute(calc_context, pattern="name", case_sensitive=True)
        assert result["status"] == "ok"

    def test_search_max_results(self, calc_context):
        for i in range(3, 20):
            sheet = calc_context.doc.getSheets().getByName("Sheet1")
            sheet.set_cell("A%d" % i, "Name")
        tool = SearchInSpreadsheet()
        result = tool.execute(calc_context, pattern="Name", max_results=2)
        assert result["status"] == "ok"
        assert result["count"] <= 2


class TestReplaceInSpreadsheet:
    def test_replace_found(self, calc_context):
        tool = ReplaceInSpreadsheet()
        result = tool.execute(calc_context, search="Test", replace="Replaced")
        assert result["status"] == "ok"
        assert result["replacements"] >= 1

    def test_replace_not_found(self, calc_context):
        tool = ReplaceInSpreadsheet()
        result = tool.execute(calc_context, search="ZZZZNOTFOUND", replace="x")
        assert result["status"] == "ok"
        assert result["replacements"] == 0

    def test_replace_empty_search(self, calc_context):
        tool = ReplaceInSpreadsheet()
        result = tool.execute(calc_context, search="", replace="x")
        assert result["status"] == "error"

    def test_replace_all_sheets(self, calc_context):
        calc_context.doc.add_sheet("Sheet2")
        tool = ReplaceInSpreadsheet()
        result = tool.execute(
            calc_context, search="Test", replace="Replaced", all_sheets=True
        )
        assert result["status"] == "ok"


class TestListNamedRanges:
    def test_list_empty(self, calc_context):
        tool = ListNamedRanges()
        result = tool.execute(calc_context)
        assert result["status"] == "ok"
        assert result["count"] == 0

    def test_list_with_named_range(self, calc_context):
        calc_context.doc.NamedRanges.addNewByName(
            "MyRange",
            "$Sheet1.$A$1:$B$2",
            CellRangeStub(0, 0, 1, 1),
            0,
        )
        tool = ListNamedRanges()
        result = tool.execute(calc_context)
        assert result["status"] == "ok"
        assert result["count"] == 1


class TestGetSheetOverview:
    def test_overview_active_sheet(self, calc_context):
        tool = GetSheetOverview()
        result = tool.execute(calc_context)
        assert result["status"] == "ok"
        assert result["sheet"] == "Sheet1"

    def test_overview_named_sheet(self, calc_context):
        tool = GetSheetOverview()
        result = tool.execute(calc_context, sheet_name="Sheet1")
        assert result["status"] == "ok"

    def test_overview_missing_sheet(self, calc_context):
        tool = GetSheetOverview()
        result = tool.execute(calc_context, sheet_name="NotFound")
        assert result["status"] == "error"


class TestDetectErrors:
    def test_detect_errors_no_errors(self, calc_context):
        tool = DetectErrors()
        result = tool.execute(calc_context, range_name="A1:B2")
        assert result["status"] == "ok"


class TestConditionalFormats:
    def test_list_conditional_formats_empty(self, calc_context):
        tool = ListConditionalFormats()
        result = tool.execute(calc_context, cell_range="A1:B2")
        assert result["status"] == "ok"

    def test_add_conditional_format_bad_operator(self, calc_context):
        tool = AddConditionalFormat()
        result = tool.execute(
            calc_context,
            cell_range="A1:A10",
            operator="BAD",
            formula1="1",
            style_name="Default",
        )
        assert result["status"] == "error"

    def test_remove_conditional_format_validates(self):
        tool = RemoveConditionalFormat()
        ok, err = tool.validate(cell_range="A1:A10", rule_index=0)
        assert ok is True

    def test_clear_conditional_formats_validates(self):
        tool = ClearConditionalFormats()
        ok, err = tool.validate(cell_range="A1:A10")
        assert ok is True
        ok2, _ = tool.validate()
        assert ok2 is False


class TestComments:
    def test_list_comments_empty(self, calc_context):
        tool = ListCellComments()
        result = tool.execute(calc_context)
        assert result["status"] == "ok"
        assert result["count"] == 0

    def test_add_comment_missing_params(self, calc_context):
        tool = AddCellComment()
        result = tool.execute(calc_context)
        assert result["status"] == "error"

    def test_delete_comment_missing_params(self, calc_context):
        tool = DeleteCellComment()
        result = tool.execute(calc_context)
        assert result["status"] == "error"

    def test_delete_comment_not_found(self, calc_context):
        tool = DeleteCellComment()
        result = tool.execute(calc_context, cell="Z99")
        assert result["status"] == "error"


class TestCharts:
    def test_list_charts_empty(self, calc_context):
        tool = ListCharts()
        result = tool.execute(calc_context)
        assert result["status"] == "ok"
        assert result["count"] == 0

    def test_get_chart_info_missing(self, calc_context):
        tool = GetChartInfo()
        result = tool.execute(calc_context, chart_name="NonExistent")
        assert result["status"] == "error"

    def test_delete_chart_missing(self, calc_context):
        tool = DeleteChart()
        result = tool.execute(calc_context, chart_name="NonExistent")
        assert result["status"] == "error"

    def test_edit_chart_missing(self, calc_context):
        tool = EditChart()
        result = tool.execute(calc_context, chart_name="NonExistent")
        assert result["status"] == "error"


class TestEdgeCases:
    def test_empty_doc_no_sheets(self):
        doc = CalcDocStub()
        ctx = ToolContext(
            doc=doc,
            ctx=None,
            doc_type="calc",
            services=StubServiceRegistry(doc=doc),
            caller="test",
        )
        tool = ListSheets()
        result = tool.execute(ctx)
        assert result["status"] == "ok"
        assert result["result"] == []

    def test_read_cell_out_of_used_area(self, calc_context):
        tool = ReadCellRange()
        result = tool.execute(calc_context, range_name="Z100")
        assert result["status"] == "ok"

    def test_write_and_read_roundtrip(self, calc_context):
        tool_write = WriteCellRange()
        tool_write.execute(calc_context, range_name="C1", formula_or_values=99)
        tool_read = ReadCellRange()
        result = tool_read.execute(calc_context, range_name="C1")
        assert result["status"] == "ok"

    def test_csv_import_then_read(self, calc_context):
        tool_csv = ImportCsv()
        tool_csv.execute(calc_context, csv_data="Header1,Header2\n10,20")
        tool_read = ReadCellRange()
        result = tool_read.execute(calc_context, range_name="A1")
        assert result["status"] == "ok"

    def test_clear_then_read_empty(self, calc_context):
        tool_clear = ClearRange()
        tool_clear.execute(calc_context, range_name="A1:B2")
        tool_read = ReadCellRange()
        result = tool_read.execute(calc_context, range_name="A1")
        assert result["status"] == "ok"
