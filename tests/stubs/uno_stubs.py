class PropertyHolder:
    def __init__(self, **kwargs):
        self._properties = dict(kwargs)

    def getPropertyValue(self, name):
        if name in self._properties:
            return self._properties[name]
        raise AttributeError(
            "%s does not have property '%s' — add it to the stub"
            % (type(self).__name__, name)
        )

    def setPropertyValue(self, name, value):
        self._properties[name] = value

    def getPropertySetInfo(self):
        return PropertySetInfoStub(set(self._properties.keys()))


class PropertySetInfoStub:
    def __init__(self, names=None):
        self._names = names or set()

    def getProperties(self):
        return []

    def hasPropertyByName(self, name):
        return name in self._names


class ServiceInfoMixin:
    _services: set

    def supportsService(self, name):
        return name in self._services


class UnoEnumStub:
    def __init__(self, **members):
        for k, v in members.items():
            setattr(self, k, v)


class Point:
    def __init__(self, X=0, Y=0):
        self.X = X
        self.Y = Y


class Size:
    def __init__(self, Width=0, Height=0):
        self.Width = Width
        self.Height = Height


class BorderLine:
    def __init__(self):
        self.Color = 0
        self.OuterLineWidth = 0
        self.InnerLineWidth = 0
        self.LineDistance = 0


class _TableSortField:
    def __init__(self):
        self.Field = 0
        self.IsAscending = True
        self.IsCaseSensitive = False


class CellAddress:
    def __init__(self):
        self.Sheet = 0
        self.Column = 0
        self.Row = 0


class Rectangle:
    def __init__(self):
        self.X = 0
        self.Y = 0
        self.Width = 0
        self.Height = 0


class PropertyValue:
    def __init__(self, Name="", Value=None):
        self.Name = Name
        self.Value = Value


class ComponentContextStub:
    def __init__(self):
        self.ServiceManager = ServiceManagerStub()


class ServiceManagerStub:
    def createInstanceWithContext(self, name, ctx):
        raise AttributeError(
            "ServiceManagerStub does not implement '%s' — add it to the stub" % name
        )


class DesktopStub:
    def __init__(self):
        self._frames = []
        self._current_component = None

    def getCurrentComponent(self):
        return self._current_component

    def getFrames(self):
        return IndexAccessStub(self._frames)

    def loadComponentFromURL(self, url, frame, flags, args):
        raise AttributeError("DesktopStub does not implement loadComponentFromURL")


class FrameStub:
    def __init__(self, title="", controller=None):
        self._title = title
        self._controller = controller

    def getTitle(self):
        return self._title

    def getController(self):
        return self._controller

    def activate(self):
        pass


class ControllerStub:
    def __init__(self, model=None):
        self._model = model
        self._selection = None
        self._view_cursor = None

    def getModel(self):
        return self._model

    def getFrame(self):
        return FrameStub(controller=self)

    def getSelection(self):
        return self._selection

    def getActiveSheet(self):
        return None

    def setActiveSheet(self, sheet):
        pass

    def getViewCursor(self):
        return self._view_cursor


class ViewCursorStub(PropertyHolder):
    def __init__(self):
        super().__init__()
        self._page = 1
        self._range = TextRangeStub(0, 0)

    def getPage(self):
        return self._page

    def gotoRange(self, range_obj, expand):
        self._range = range_obj

    def jumpToPage(self, page):
        self._page = page

    def jumpToLastPage(self):
        pass

    def getStart(self):
        return self._range


class IndexAccessStub:
    def __init__(self, items=None):
        self._items = list(items or [])

    def getCount(self):
        return len(self._items)

    def getByIndex(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        raise IndexError("Index %d out of range" % index)


class NameAccessStub:
    def __init__(self, items=None):
        self._items = dict(items or {})

    def getCount(self):
        return len(self._items)

    def getByIndex(self, index):
        return list(self._items.values())[index]

    def getByName(self, name):
        if name in self._items:
            return self._items[name]
        raise KeyError("Name '%s' not found" % name)

    def hasByName(self, name):
        return name in self._items

    def getElementNames(self):
        return list(self._items.keys())


class TextRangeStub(PropertyHolder, ServiceInfoMixin):
    def __init__(self, start=0, end=0, text="", **kwargs):
        super().__init__(**kwargs)
        self._start = start
        self._end = end
        self._text = text
        self._services = {"com.sun.star.text.TextRange"}

    def getString(self):
        return self._text

    def setString(self, value):
        self._text = value

    def getStart(self):
        return self

    def getEnd(self):
        return self

    def getText(self):
        return None


class SearchDescriptorStub(PropertyHolder):
    def __init__(self):
        super().__init__()
        self.SearchString = ""
        self.SearchRegularExpression = False
        self.SearchCaseSensitive = True


class ReplaceDescriptorStub(SearchDescriptorStub):
    def __init__(self):
        super().__init__()
        self.ReplaceString = ""


_COM_SUN_STAR_TEXT_PARAGRAPH_BREAK = 0


def install_uno_stubs():
    """Install UNO stubs into sys.modules so `import uno` works without LO."""
    import sys
    import types

    if "uno" in sys.modules:
        return

    uno_mod = types.ModuleType("uno")
    uno_mod.systemPathToFileUrl = lambda p: "file://" + p
    uno_mod.fileUrlToSystemPath = lambda u: u.replace("file://", "")
    sys.modules["uno"] = uno_mod

    com_mod = types.ModuleType("com")
    sun_mod = types.ModuleType("com.sun")
    star_mod = types.ModuleType("com.sun.star")
    sys.modules["com"] = com_mod
    sys.modules["com.sun"] = sun_mod
    sys.modules["com.sun.star"] = star_mod

    def _make_star_module(dotted_path, attrs=None):
        mod = types.ModuleType(dotted_path)
        if attrs:
            for k, v in attrs.items():
                setattr(mod, k, v)
        sys.modules[dotted_path] = mod
        return mod

    _make_star_module("com.sun.star.beans", {"PropertyValue": PropertyValue})
    _make_star_module(
        "com.sun.star.awt", {"Point": Point, "Size": Size, "Rectangle": Rectangle}
    )

    text_mod = _make_star_module("com.sun.star.text")
    text_mod.ControlCharacter = types.ModuleType("com.sun.star.text.ControlCharacter")
    text_mod.ControlCharacter.PARAGRAPH_BREAK = _COM_SUN_STAR_TEXT_PARAGRAPH_BREAK
    sys.modules["com.sun.star.text.ControlCharacter"] = text_mod.ControlCharacter

    _make_star_module("com.sun.star.sheet")
    _make_star_module("com.sun.star.drawing")
    _make_star_module("com.sun.star.presentation")
    _make_star_module("com.sun.star.frame")
    _make_star_module("com.sun.star.awt.FontWeight", {"BOLD": 150.0, "NORMAL": 100.0})
    _make_star_module("com.sun.star.awt.FontSlant", {"ITALIC": 1, "NONE": 0})
    _make_star_module(
        "com.sun.star.table",
        {
            "BorderLine": BorderLine,
            "CellAddress": CellAddress,
            "TableSortField": _TableSortField,
        },
    )
    _make_star_module(
        "com.sun.star.table.CellContentType",
        {"EMPTY": 0, "VALUE": 1, "TEXT": 2, "FORMULA": 3},
    )
    _make_star_module(
        "com.sun.star.table.CellHoriJustify",
        {"LEFT": 1, "CENTER": 2, "RIGHT": 3, "BLOCK": 4, "STANDARD": 0},
    )
    _make_star_module(
        "com.sun.star.table.CellVertJustify",
        {"TOP": 1, "CENTER": 2, "BOTTOM": 3, "STANDARD": 0},
    )
    _make_star_module(
        "com.sun.star.sheet.ConditionOperator",
        {
            "NONE": 0,
            "EQUAL": 1,
            "NOT_EQUAL": 2,
            "GREATER": 3,
            "GREATER_EQUAL": 4,
            "LESS": 5,
            "LESS_EQUAL": 6,
            "BETWEEN": 7,
            "NOT_BETWEEN": 8,
            "FORMULA": 9,
        },
    )

    frame_mod = sys.modules["com.sun.star.frame"]
    frame_mod.Desktop = DesktopStub
