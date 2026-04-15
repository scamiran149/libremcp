from stubs.uno_stubs import (
    PropertyHolder,
    ServiceInfoMixin,
    Point,
    Size,
    IndexAccessStub,
)


class ShapeStub(PropertyHolder, ServiceInfoMixin):
    def __init__(
        self,
        shape_type="RectangleShape",
        x=0,
        y=0,
        width=5000,
        height=3000,
        text="",
        **kwargs,
    ):
        super().__init__(
            FillColor=kwargs.pop("fill_color", None),
            LineColor=kwargs.pop("line_color", None),
            **kwargs,
        )
        self._shape_type = shape_type
        self._x = x
        self._y = y
        self._width = width
        self._height = height
        self._text = text
        self._services = {
            "com.sun.star.drawing.%s" % shape_type,
            "com.sun.star.drawing.Shape",
        }
        if "RectangleShape" in shape_type:
            self._services.add("com.sun.star.drawing.RectangleShape")
        if "EllipseShape" in shape_type:
            self._services.add("com.sun.star.drawing.EllipseShape")
        if "TextShape" in shape_type:
            self._services.add("com.sun.star.drawing.TextShape")
        if "LineShape" in shape_type:
            self._services.add("com.sun.star.drawing.LineShape")

    def getShapeType(self):
        return "com.sun.star.drawing.%s" % self._shape_type

    def getPosition(self):
        return Point(self._x, self._y)

    def setPosition(self, point):
        self._x = point.X
        self._y = point.Y

    def getSize(self):
        return Size(self._width, self._height)

    def setSize(self, size):
        self._width = size.Width
        self._height = size.Height

    def getString(self):
        return self._text

    def setString(self, value):
        self._text = value


class DrawPageStub(PropertyHolder):
    def __init__(self, name="Page 1"):
        super().__init__()
        self._name = name
        self._shapes = []
        self._speaker_notes = ""
        self._master_page = None
        self._transition_type = 0
        self._transition_duration = 0.0
        self.Width = 25400
        self.Height = 19050
        self.Name = name
        self.MasterPage = None
        self.Layout = 11

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

    def add_shape(self, shape_type, x=0, y=0, width=5000, height=3000, text=""):
        shape = ShapeStub(
            shape_type=shape_type,
            x=x,
            y=y,
            width=width,
            height=height,
            text=text,
        )
        self._shapes.append(shape)
        return shape

    def getNotesPage(self):
        return _NotesPageStub(self._speaker_notes)


class _NotesPageStub:
    def __init__(self, notes_text=""):
        self._notes_text = notes_text
        self._shapes = [
            _NotesShapeStub(""),
            _NotesShapeStub(notes_text),
        ]

    def getCount(self):
        return len(self._shapes)

    def getByIndex(self, index):
        if 0 <= index < len(self._shapes):
            return self._shapes[index]
        raise IndexError("Shape index %d out of range" % index)


class _NotesShapeStub:
    def __init__(self, text=""):
        self._text = text

    def getString(self):
        return self._text

    def setString(self, value):
        self._text = value


class _DrawPagesAccess(IndexAccessStub):
    def __init__(self, pages_list):
        self._items = pages_list

    def insertNewByIndex(self, index):
        page = DrawPageStub(name="Page %d" % (len(self._items) + 1))
        self._items.insert(index, page)
        return page

    def remove(self, page):
        if page in self._items:
            self._items.remove(page)


class _MasterPagesAccess:
    def __init__(self, pages):
        self._pages = pages

    def getCount(self):
        return len(self._pages)

    def getByIndex(self, index):
        if 0 <= index < len(self._pages):
            return self._pages[index]
        raise IndexError("Master page index %d out of range" % index)


class _MasterPageStub(PropertyHolder):
    def __init__(self, name="Default"):
        super().__init__()
        self._name = name
        self.Width = 25400
        self.Height = 19050
        self.Name = name


class DrawDocStub(PropertyHolder, ServiceInfoMixin):
    def __init__(self, doc_type="draw", **kwargs):
        super().__init__(**kwargs)
        self._doc_type = doc_type
        self._pages = []
        self._url = kwargs.pop("url", "test://%s" % doc_type)
        self._services = set()
        if doc_type == "draw":
            self._services.add("com.sun.star.drawing.DrawingDocument")
        elif doc_type == "impress":
            self._services.add("com.sun.star.presentation.PresentationDocument")
            self._services.add("com.sun.star.drawing.DrawingDocument")

        self._controller = _DrawControllerStub(self)
        self._style_families = _DrawStyleFamilies()
        self._master_pages = [_MasterPageStub("Default")]

        if doc_type == "impress":
            self.getPresentation = lambda: _PresentationStub()

    def add_page(self):
        page = DrawPageStub(name="Page %d" % (len(self._pages) + 1))
        self._pages.append(page)
        return page

    def getDrawPages(self):
        return _DrawPagesAccess(self._pages)

    def getCurrentController(self):
        return self._controller

    def getURL(self):
        return self._url

    def supportsService(self, name):
        return name in self._services

    def createInstance(self, service_name):
        if service_name.startswith("com.sun.star.drawing."):
            shape_type = service_name.split(".")[-1]
            return ShapeStub(shape_type=shape_type)
        raise AttributeError(
            "DrawDocStub does not implement createInstance('%s')" % service_name
        )

    def getStyleFamilies(self):
        return self._style_families

    def getMasterPages(self):
        return _MasterPagesAccess(self._master_pages)

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
                class UDP:
                    _values = {}

                    def getPropertyValue(self, name):
                        if name in self._values:
                            return self._values[name]
                        raise AttributeError("Not found")

                    def addProperty(self, name, attrs, value):
                        self._values[name] = value

                return UDP()

        return Props()

    def close(self, flag):
        pass

    def store(self):
        pass

    def storeToURL(self, url, props):
        pass


class _DrawControllerStub:
    def __init__(self, doc):
        self._doc = doc
        self._current_page = None
        self._selection = None
        self._view_cursor = None

    def getCurrentPage(self):
        if self._current_page is not None:
            return self._current_page
        if self._doc._pages:
            return self._doc._pages[0]
        return None

    def setCurrentPage(self, page):
        self._current_page = page

    def getModel(self):
        return self._doc

    def getFrame(self):
        class Frame:
            def getTitle(self):
                return "TestDraw"

        return Frame()

    def getSelection(self):
        return self._selection

    def getViewCursor(self):
        return self._view_cursor


class _PresentationStub:
    pass


class _DrawStyleFamilies:
    def getElementNames(self):
        return ["GraphicStyles"]

    def hasByName(self, name):
        return name == "GraphicStyles"

    def getByName(self, name):
        return _GraphicStylesStub()


class _GraphicStylesStub:
    def getElementNames(self):
        return []

    def hasByName(self, name):
        return False

    def getByName(self, name):
        raise KeyError("Style not found: %s" % name)
