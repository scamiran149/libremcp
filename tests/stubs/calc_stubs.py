import re

from stubs.uno_stubs import (
    PropertyHolder,
    ServiceInfoMixin,
    IndexAccessStub,
    NameAccessStub,
    SearchDescriptorStub,
    ReplaceDescriptorStub,
    Point,
    Size,
)


class CellStub(PropertyHolder, ServiceInfoMixin):
    def __init__(self, col=0, row=0, value=None, formula="", string=""):
        super().__init__(
            CharWeight=None,
            CharPosture=None,
            CharColor=None,
            CharFontName=None,
            CharHeight=None,
            CellBackColor=None,
            HoriJustify=None,
            VertJustify=None,
            IsTextWrapped=None,
            LeftBorder=None,
            RightBorder=None,
            TopBorder=None,
            BottomBorder=None,
            NumberFormat=-1,
        )
        self._col = col
        self._row = row
        self._value = value
        self._formula = formula
        self._string = string
        self._cell_type = "empty"
        self._services = {"com.sun.star.table.Cell"}

    @property
    def address(self):
        col_letter = chr(ord("A") + self._col) if self._col < 26 else ""
        return "%s%d" % (col_letter, self._row + 1)

    def getValue(self):
        return self._value

    def setValue(self, v):
        self._value = float(v) if v is not None else None
        self._cell_type = "value"
        self._string = str(v) if v is not None else ""

    def getString(self):
        return self._string

    def setString(self, s):
        self._string = s
        self._cell_type = "string"
        self._value = None

    def getFormula(self):
        return self._formula

    def setFormula(self, f):
        self._formula = f
        self._cell_type = "formula"
        self._string = f

    def getType(self):
        if self._cell_type == "formula":
            return 3
        if self._value is not None:
            return 1
        if self._string:
            return 2
        return 0

    def getCellAddress(self):
        return _CellAddressStub(self._col, self._row)

    def getAnnotation(self):
        annots = self._sheet.getAnnotations() if self._sheet else None
        if annots:
            ann = annots._find_at(self._col, self._row)
            if ann:
                return ann
        return _AnnotationStub(self._col, self._row, "")


class _CellAddressStub:
    def __init__(self, col, row, sheet=0):
        self.Column = col
        self.Row = row
        self.Sheet = sheet


class _AnnotationStub:
    def __init__(self, col, row, text, author="test"):
        self._col = col
        self._row = row
        self._text = text
        self._author = author
        self._visible = bool(text)

    def getPosition(self):
        return _CellAddressStub(self._col, self._row)

    def getAuthor(self):
        return self._author

    def getDate(self):
        return "2025-01-01"

    def getString(self):
        return self._text

    def setString(self, text):
        self._text = text

    def getIsVisible(self):
        return self._visible


class _AnnotationsCollection:
    def __init__(self, sheet):
        self._sheet = sheet
        self._items = []

    def getCount(self):
        return len(self._items)

    def getByIndex(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        raise IndexError("Annotation index %d out of range" % index)

    def insertNew(self, addr, text):
        ann = _AnnotationStub(addr.Column, addr.Row, text)
        self._items.append(ann)

    def removeByIndex(self, index):
        if 0 <= index < len(self._items):
            self._items.pop(index)

    def _find_at(self, col, row):
        for ann in self._items:
            pos = ann.getPosition()
            if pos.Column == col and pos.Row == row:
                return ann
        return None


class CellRangeStub(PropertyHolder):
    def __init__(self, start_col=0, start_row=0, end_col=0, end_row=0, sheet=None):
        super().__init__(ConditionalFormat=_ConditionalFormatEntries())
        self._start_col = start_col
        self._start_row = start_row
        self._end_col = end_col
        self._end_row = end_row
        self._sheet = sheet
        self._merged = False
        self._cells_cleared = 0

    def merge(self, merge_flag):
        self._merged = merge_flag

    def clearContents(self, flags):
        self._cells_cleared = flags
        if self._sheet:
            for r in range(self._start_row, self._end_row + 1):
                for c in range(self._start_col, self._end_col + 1):
                    cell = self._sheet._get_or_create_cell(c, r)
                    cell._value = None
                    cell._string = ""
                    cell._formula = ""

    def createSortDescriptor(self):
        return []

    def sort(self, descriptor):
        pass

    def getRangeAddress(self):
        return _RangeAddressStub(
            self._start_col, self._start_row, self._end_col, self._end_row
        )

    def getDataArray(self):
        if not self._sheet:
            return []
        rows = []
        for r in range(self._start_row, self._end_row + 1):
            row = []
            for c in range(self._start_col, self._end_col + 1):
                cell = self._sheet._get_or_create_cell(c, r)
                if cell._value is not None:
                    row.append(cell._value)
                elif cell._formula:
                    row.append(cell._formula)
                else:
                    row.append(cell._string)
            rows.append(tuple(row))
        return tuple(rows)

    def setDataArray(self, data):
        if not self._sheet:
            return
        for r_idx, row in enumerate(data):
            for c_idx, val in enumerate(row):
                cell = self._sheet._get_or_create_cell(
                    self._start_col + c_idx, self._start_row + r_idx
                )
                if isinstance(val, (int, float)):
                    cell.setValue(val)
                elif isinstance(val, str) and val.startswith("="):
                    cell.setFormula(val)
                else:
                    cell.setString(str(val) if val is not None else "")


class _RangeAddressStub:
    def __init__(self, start_col, start_row, end_col, end_row, sheet_index=0):
        self.StartColumn = start_col
        self.StartRow = start_row
        self.EndColumn = end_col
        self.EndRow = end_row
        self.Sheet = sheet_index


class SheetStub(PropertyHolder, ServiceInfoMixin):
    def __init__(self, name="Sheet1"):
        super().__init__()
        self._name = name
        self._cells = {}
        self._data_area = None
        self._charts = []
        self._conditional_formats = []
        self._comments = {}
        self._services = {
            "com.sun.star.sheet.Spreadsheet",
        }
        self.DrawPage = _CalcDrawPageStub()
        self._annotations = _AnnotationsCollection(self)
        self._cursor_data_area = None

    @property
    def name(self):
        return self._name

    def getName(self):
        return self._name

    def _cell_key(self, col, row):
        return (col, row)

    def _get_or_create_cell(self, col, row):
        key = self._cell_key(col, row)
        if key not in self._cells:
            cell = CellStub(col=col, row=row)
            cell._sheet = self
            self._cells[key] = cell
        return self._cells[key]

    def set_cell(self, addr, value):
        m = re.match(r"([A-Z]+)(\d+)", addr.upper())
        if not m:
            raise ValueError("Invalid cell address: %s" % addr)
        col = _col_letter_to_index(m.group(1))
        row = int(m.group(2)) - 1
        cell = self._get_or_create_cell(col, row)
        if isinstance(value, (int, float)):
            cell.setValue(value)
        elif isinstance(value, str) and value.startswith("="):
            cell.setFormula(value)
        else:
            cell.setString(str(value))
        self._update_data_area(col, row)

    def get_cell(self, addr):
        m = re.match(r"([A-Z]+)(\d+)", addr.upper())
        if not m:
            raise ValueError("Invalid cell address: %s" % addr)
        col = _col_letter_to_index(m.group(1))
        row = int(m.group(2)) - 1
        return self._get_or_create_cell(col, row)

    def getCellByPosition(self, col, row):
        return self._get_or_create_cell(col, row)

    def getCellRangeByPosition(self, start_col, start_row, end_col, end_row):
        return CellRangeStub(start_col, start_row, end_col, end_row, sheet=self)

    def _update_data_area(self, col, row):
        if self._data_area is None:
            self._data_area = (0, 0, col, row)
        else:
            sc, sr, ec, er = self._data_area
            self._data_area = (min(sc, col), min(sr, row), max(ec, col), max(er, row))

    def get_data_area(self):
        if self._data_area is None:
            return (0, 0, 0, 0)
        return self._data_area

    def getCellRangeByName(self, range_str):
        m = re.match(r"([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?", range_str.upper())
        if not m:
            raise ValueError("Invalid range: %s" % range_str)
        start_col = _col_letter_to_index(m.group(1))
        start_row = int(m.group(2)) - 1
        if m.group(3):
            end_col = _col_letter_to_index(m.group(3))
            end_row = int(m.group(4)) - 1
        else:
            end_col = start_col
            end_row = start_row
        return CellRangeStub(start_col, start_row, end_col, end_row, sheet=self)

    def createSearchDescriptor(self):
        return SearchDescriptorStub()

    def createReplaceDescriptor(self):
        return ReplaceDescriptorStub()

    def findAll(self, descriptor):
        pattern = descriptor.SearchString
        results = _FoundCellsCollection()
        if not pattern:
            return None
        import re as _re

        flags = (
            0 if getattr(descriptor, "SearchCaseSensitive", True) else _re.IGNORECASE
        )
        if getattr(descriptor, "SearchRegularExpression", False):
            try:
                rx = _re.compile(pattern, flags)
            except _re.error:
                return None
        else:
            rx = _re.compile(_re.escape(pattern), flags)
        for (col, row), cell in self._cells.items():
            s = cell.getString()
            if s and rx.search(s):
                results.add(cell)
        return results if results.getCount() > 0 else None

    def replaceAll(self, descriptor):
        search = descriptor.SearchString
        replace = descriptor.ReplaceString
        count = 0
        for cell in self._cells.values():
            s = cell.getString()
            if search in s:
                cell.setString(s.replace(search, replace))
                count += 1
        return count

    def createCursor(self):
        da = self.get_data_area()
        if da == (0, 0, 0, 0):
            return _CursorStub(0, 0, 0, 0, sheet=self)
        return _CursorStub(da[0], da[1], da[2], da[3], sheet=self)

    def getAnnotations(self):
        return self._annotations

    def getRows(self):
        return _RowsColumnsStub()

    def getColumns(self):
        return _RowsColumnsStub()

    def getCharts(self):
        return _ChartsCollection(self._charts)

    def getRangeAddress(self):
        return _RangeAddressStub(0, 0, 0, 0, sheet_index=0)

    def getPropertyValue(self, name):
        if name == "HasMergedCells":
            return False
        return super().getPropertyValue(name)


class _CalcDrawPageStub:
    def __init__(self):
        self._shapes = []

    def getCount(self):
        return len(self._shapes)

    def getByIndex(self, index):
        if 0 <= index < len(self._shapes):
            return self._shapes[index]
        raise IndexError("Shape index %d out of range" % index)

    def add(self, shape):
        self._shapes.append(shape)

    def remove(self, shape):
        if shape in self._shapes:
            self._shapes.remove(shape)


class _CursorStub:
    def __init__(self, start_col, start_row, end_col, end_row, sheet=None):
        self._start_col = start_col
        self._start_row = start_row
        self._end_col = end_col
        self._end_row = end_row
        self._sheet = sheet

    def gotoStartOfUsedArea(self, expand):
        pass

    def gotoEndOfUsedArea(self, expand):
        pass

    def getRangeAddress(self):
        return _RangeAddressStub(
            self._start_col, self._start_row, self._end_col, self._end_row
        )


class _FoundCellsCollection:
    def __init__(self):
        self._cells = []

    def add(self, cell):
        self._cells.append(cell)

    def getCount(self):
        return len(self._cells)

    def getByIndex(self, index):
        if 0 <= index < len(self._cells):
            return self._cells[index]
        raise IndexError("Found cell index %d out of range" % index)


class _RowsColumnsStub:
    def removeByIndex(self, index, count):
        pass

    def insertByIndex(self, index, count):
        pass


class _ChartsCollection:
    def __init__(self, charts_list):
        self._charts = {
            c.get("name", "Chart_%d" % i): c for i, c in enumerate(charts_list)
        }
        self._order = list(self._charts.keys())

    def getCount(self):
        return len(self._charts)

    def getElementNames(self):
        return self._order

    def hasByName(self, name):
        return name in self._charts

    def getByName(self, name):
        if name in self._charts:
            return self._charts[name]
        raise KeyError("Chart '%s' not found" % name)

    def addNewByName(self, name, rect, ranges, col_headers, row_headers):
        chart_obj = {"name": name, "rect": rect, "ranges": ranges}
        self._charts[name] = chart_obj
        self._order.append(name)

    def removeByName(self, name):
        if name in self._charts:
            del self._charts[name]
            self._order.remove(name)


class _NamedRangesStub:
    def __init__(self):
        self._ranges = {}

    def getElementNames(self):
        return list(self._ranges.keys())

    def getByName(self, name):
        if name in self._ranges:
            return self._ranges[name]
        raise KeyError("Named range '%s' not found" % name)

    def addNewByName(self, name, content, ref, _type):
        self._ranges[name] = _NamedRangeStub(name, content, ref)

    def removeByName(self, name):
        if name in self._ranges:
            del self._ranges[name]


class _NamedRangeStub:
    def __init__(self, name, content, ref):
        self._name = name
        self._content = content
        self._ref = ref

    def getContent(self):
        return self._content

    def getReferredCells(self):
        return self._ref


class _ConditionalFormatEntries:
    def __init__(self):
        self._entries = []

    def getCount(self):
        return len(self._entries)

    def getByIndex(self, index):
        if 0 <= index < len(self._entries):
            return self._entries[index]
        raise IndexError("Conditional entry index %d out of range" % index)

    def addNew(self, props_tuple):
        entry = _ConditionalEntry(props_tuple)
        self._entries.append(entry)

    def removeByIndex(self, index):
        if 0 <= index < len(self._entries):
            self._entries.pop(index)

    def clear(self):
        self._entries.clear()


class _ConditionalEntry:
    def __init__(self, props_tuple):
        self._operator = "EQUAL"
        self._formula1 = ""
        self._formula2 = ""
        self._style_name = ""
        for pv in props_tuple:
            if pv.Name == "Operator":
                self._operator = str(pv.Value)
            elif pv.Name == "Formula1":
                self._formula1 = str(pv.Value)
            elif pv.Name == "Formula2":
                self._formula2 = str(pv.Value)
            elif pv.Name == "StyleName":
                self._style_name = str(pv.Value)

    def getOperator(self):
        return _ConditionOperatorEnum(self._operator)

    def getFormula1(self):
        return self._formula1

    def getFormula2(self):
        return self._formula2

    def getPropertyValue(self, name):
        if name == "StyleName":
            return self._style_name
        raise AttributeError("Property '%s' not found" % name)


class _ConditionOperatorEnum:
    def __init__(self, name):
        self.value = name

    def __str__(self):
        return self.value


class CalcDocStub(PropertyHolder, ServiceInfoMixin):
    def __init__(self, **kwargs):
        super().__init__(
            CharLocale=kwargs.pop("char_locale", "en-US"),
            **kwargs,
        )
        self._sheets = {}
        self._sheet_order = []
        self._active_sheet_name = None
        self._url = kwargs.pop("url", "test://calc")
        self._services = {
            "com.sun.star.sheet.SpreadsheetDocument",
        }
        self._controller = _CalcControllerStub(self)
        self._style_families = _CalcStyleFamilies()
        self._number_formats = _NumberFormatsStub()
        self.NamedRanges = _NamedRangesStub()

    def add_sheet(self, name="Sheet1"):
        sheet = SheetStub(name)
        self._sheets[name] = sheet
        self._sheet_order.append(name)
        if self._active_sheet_name is None:
            self._active_sheet_name = name
        return sheet

    def getSheets(self):
        return _SheetsCollection(self)

    def getCurrentController(self):
        return self._controller

    def getURL(self):
        return self._url

    def getStyleFamilies(self):
        return self._style_families

    def getNumberFormats(self):
        return self._number_formats

    def supportsService(self, name):
        return name in self._services

    def createInstance(self, service_name):
        raise AttributeError(
            "CalcDocStub does not implement createInstance('%s')" % service_name
        )

    def lockControllers(self):
        pass

    def unlockControllers(self):
        pass

    def getDocumentProperties(self):
        class Props:
            Title = ""
            Subject = ""
            Author = ""
            Description = ""
            Keywords = ()

            def getUserDefinedProperties(self):
                return _UserDefinedPropsStub()

        return Props()

    def close(self, flag):
        pass

    def store(self):
        pass

    def storeToURL(self, url, props):
        pass


class _SheetsCollection(NameAccessStub):
    def __init__(self, doc):
        self._doc = doc
        super().__init__(doc._sheets)

    def insertNewByName(self, name, position):
        sheet = SheetStub(name)
        self._doc._sheets[name] = sheet
        self._doc._sheet_order.append(name)

    def getByIndex(self, index):
        if index < len(self._doc._sheet_order):
            name = self._doc._sheet_order[index]
            return self._doc._sheets[name]
        raise IndexError("Sheet index %d out of range" % index)


class _CalcControllerStub:
    def __init__(self, doc):
        self._doc = doc
        self._selection = None
        self._view_cursor = None

    def getActiveSheet(self):
        if self._doc._active_sheet_name:
            return self._doc._sheets[self._doc._active_sheet_name]
        if self._doc._sheets:
            return list(self._doc._sheets.values())[0]
        return None

    def setActiveSheet(self, sheet):
        for name, s in self._doc._sheets.items():
            if s is sheet:
                self._doc._active_sheet_name = name
                return

    def getModel(self):
        return self._doc

    def getFrame(self):
        class Frame:
            def getTitle(self):
                return "TestCalc"

        return Frame()

    def getSelection(self):
        return self._selection

    def getViewCursor(self):
        return self._view_cursor


class _CalcStyleFamilies(NameAccessStub):
    def __init__(self):
        super().__init__(
            {
                "CellStyles": _StyleFamilyStub([]),
                "PageStyles": _StyleFamilyStub([]),
            }
        )


class _StyleFamilyStub(NameAccessStub):
    pass


class _NumberFormatsStub:
    def queryKey(self, fmt, locale, create):
        return 0

    def addNew(self, fmt, locale):
        return 0


class _UserDefinedPropsStub:
    def __init__(self):
        self._values = {}

    def getPropertyValue(self, name):
        if name in self._values:
            return self._values[name]
        raise AttributeError("Property '%s' not found" % name)

    def addProperty(self, name, attrs, value):
        self._values[name] = value


def _col_letter_to_index(letters):
    result = 0
    for ch in letters:
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result - 1
