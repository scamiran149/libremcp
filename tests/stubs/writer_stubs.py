from stubs.uno_stubs import (
    PropertyHolder,
    ServiceInfoMixin,
    Point,
    Size,
    IndexAccessStub,
    NameAccessStub,
)


class ParagraphStub(PropertyHolder, ServiceInfoMixin):
    def __init__(self, text="", style="Text Body", outline_level=0, **kwargs):
        super().__init__(
            ParaStyleName=style,
            OutlineLevel=outline_level,
            **kwargs,
        )
        self._text = text
        self._para_style_name = style
        self._outline_level = outline_level
        self._services = {
            "com.sun.star.text.Paragraph",
            "com.sun.star.text.TextRange",
        }
        self._start_ref = self
        self._end_ref = self

    @property
    def text(self):
        return self._text

    @property
    def para_style_name(self):
        return self._para_style_name

    @property
    def outline_level(self):
        return self._outline_level

    def getString(self):
        return self._text

    def setString(self, value):
        self._text = value

    def getStart(self):
        return self._start_ref

    def getEnd(self):
        return self._end_ref

    def setStart(self, ref):
        self._start_ref = ref

    def setEnd(self, ref):
        self._end_ref = ref

    def getText(self):
        return self._owner_text if hasattr(self, "_owner_text") else None

    def gotoRange(self, other, expand):
        pass


class TextStub:
    def __init__(self, paragraphs=None):
        self._paragraphs = list(paragraphs or [])
        for p in self._paragraphs:
            p._owner_text = self

    def createEnumeration(self):
        return _ParagraphEnumerator(self._paragraphs)

    def createTextCursor(self):
        return TextCursorStub(self, 0)

    def createTextCursorByRange(self, range_obj):
        pos = 0
        for i, p in enumerate(self._paragraphs):
            if p is range_obj:
                pos = i
                break
        return TextCursorStub(self, pos)

    def insertString(self, cursor, text, absorb):
        if isinstance(cursor, TextCursorStub):
            cursor.insert_string(text)

    def insertControlCharacter(self, cursor, char, absorb):
        if isinstance(cursor, TextCursorStub):
            cursor.insert_string("\n")

    def getString(self):
        return "\n".join(p.getString() for p in self._paragraphs)

    def setString(self, value):
        if self._paragraphs:
            self._paragraphs[0].setString(value)

    def compareRegionStarts(self, a, b):
        return 0

    def insertTextContent(self, cursor, content, absorb):
        self._paragraphs.append(ParagraphStub(text="", style="Text Body"))


class _ParagraphEnumerator:
    def __init__(self, paragraphs):
        self._paragraphs = paragraphs
        self._index = 0

    def hasMoreElements(self):
        return self._index < len(self._paragraphs)

    def nextElement(self):
        if self._index >= len(self._paragraphs):
            raise StopIteration
        el = self._paragraphs[self._index]
        self._index += 1
        return el


class TextCursorStub(PropertyHolder):
    def __init__(self, text_stub, position=0):
        super().__init__()
        self._text = text_stub
        self._position = position
        self._selection_start = position
        self._selection_end = position
        self._is_collapsed = True

    def insert_string(self, text):
        paras = self._text._paragraphs
        if not paras:
            return
        if self._position < len(paras):
            current = paras[self._position]
            current._text += text
        elif paras:
            paras[-1]._text += text

    def gotoStart(self, expand):
        self._position = 0
        if not expand:
            self._selection_start = 0
            self._selection_end = 0
            self._is_collapsed = True

    def gotoEnd(self, expand):
        n = len(self._text._paragraphs)
        self._position = n
        if not expand:
            self._selection_start = n
            self._selection_end = n
            self._is_collapsed = True

    def gotoStartOfParagraph(self, expand):
        if not expand:
            self._is_collapsed = True

    def gotoEndOfParagraph(self, expand):
        self._is_collapsed = not expand if not expand else False

    def gotoPreviousParagraph(self, expand):
        if self._position > 0:
            self._position -= 1
        if not expand:
            self._is_collapsed = True

    def gotoNextParagraph(self, expand):
        self._position += 1
        if not expand:
            self._is_collapsed = True

    def goRight(self, count, expand):
        pass

    def gotoRange(self, range_obj, expand):
        if isinstance(range_obj, ParagraphStub):
            for i, p in enumerate(self._text._paragraphs):
                if p is range_obj:
                    self._position = i
                    break
        elif isinstance(range_obj, TextCursorStub):
            self._position = range_obj._position

    def getString(self):
        if self._selection_start == self._selection_end:
            return ""
        return ""

    def setString(self, value):
        paras = self._text._paragraphs
        if self._position < len(paras):
            paras[self._position].setString(value)

    def setPropertyValue(self, name, value):
        paras = self._text._paragraphs
        if self._position < len(paras):
            paras[self._position].setPropertyValue(name, value)
        super().setPropertyValue(name, value)


class TableStub:
    def __init__(self, name="Table1", rows=2, cols=2):
        self.name = name
        self.rows = rows
        self.cols = cols
        self._cells = {}
        for r in range(rows):
            for c in range(cols):
                key = chr(ord("A") + c) + str(r + 1)
                self._cells[key] = ""

    def getCellByName(self, name):
        return self._cells.get(name, "")

    def getCellByPosition(self, col, row):
        key = chr(ord("A") + col) + str(row + 1)
        return self._cells.get(key, "")


class TextRangeStub(PropertyHolder, ServiceInfoMixin):
    def __init__(self, start=0, end=0, text=""):
        super().__init__()
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


class DrawPageStub:
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


class WriterDocStub(PropertyHolder, ServiceInfoMixin):
    def __init__(self, **kwargs):
        super().__init__(
            PageCount=kwargs.pop("page_count", 1),
            CharLocale=kwargs.pop("char_locale", "en-US"),
            **kwargs,
        )
        self._paragraphs = []
        self._tables = []
        self._draw_page = DrawPageStub()
        self._bookmarks = NameAccessStub()
        self._comments = []
        self._text_frames = []
        self._text = None
        self._url = kwargs.pop("url", "test://writer")
        self._services = {
            "com.sun.star.text.TextDocument",
        }
        self._style_families = _WriterStyleFamilies()
        self._controller = ControllerStub(self)
        self._controller._view_cursor = None
        self._replace_count = 0
        self._search_count = 0
        self._instances = {}

    @property
    def paragraphs(self):
        return self._paragraphs

    def add_paragraph(self, text, style="Text Body", outline_level=None, **kwargs):
        if outline_level is None:
            if style.startswith("Heading "):
                try:
                    outline_level = int(style.split()[-1])
                except (ValueError, IndexError):
                    outline_level = 0
            else:
                outline_level = 0
        p = ParagraphStub(text=text, style=style, outline_level=outline_level, **kwargs)
        self._paragraphs.append(p)
        self._text = None
        return p

    def getText(self):
        if self._text is None:
            self._text = TextStub(self._paragraphs)
        return self._text

    def getDrawPage(self):
        return self._draw_page

    def getDrawPages(self):
        pages = IndexAccessStub([self._draw_page])
        return pages

    def getBookmarks(self):
        return self._bookmarks

    def getURL(self):
        return self._url

    def getCurrentController(self):
        return self._controller

    def getStyleFamilies(self):
        return self._style_families

    def supportsService(self, name):
        return name in self._services

    def createReplaceDescriptor(self):
        return _ReplaceDescriptorStub()

    def replaceAll(self, descriptor):
        search = getattr(descriptor, "SearchString", "")
        replace = getattr(descriptor, "ReplaceString", "")
        count = 0
        for p in self._paragraphs:
            if search in p._text:
                count += p._text.count(search)
                p._text = p._text.replace(search, replace)
        self._replace_count += count
        return count

    def findFirst(self, descriptor):
        search = getattr(descriptor, "SearchString", "")
        for p in self._paragraphs:
            if search in p._text:
                return TextRangeStub(0, len(search), search)
        return None

    def createSearchDescriptor(self):
        return _SearchDescriptorStub()

    def createInstance(self, service_name):
        if service_name.startswith("com.sun.star.drawing."):
            from stubs.draw_stubs import ShapeStub

            shape_type = service_name.split(".")[-1]
            return ShapeStub(shape_type=shape_type)
        if service_name == "com.sun.star.text.textfield.Annotation":
            return _AnnotationStub()
        raise AttributeError(
            "WriterDocStub does not implement createInstance('%s')" % service_name
        )

    def lockControllers(self):
        pass

    def unlockControllers(self):
        pass

    def getTextFields(self):
        return _TextFieldEnumerationStub(self._comments)

    def insertTextContent(self, cursor, content, absorb):
        pass

    def removeTextContent(self, content):
        pass

    def getDocumentProperties(self):
        return _DocPropertiesStub()

    def close(self, flag):
        pass

    def store(self):
        pass

    def storeToURL(self, url, props):
        pass

    RecordChanges = False

    def findNext(self, after, descriptor):
        search = getattr(descriptor, "SearchString", "")
        start_idx = 0
        if hasattr(after, "_para_idx"):
            start_idx = after._para_idx + 1
        for i, p in enumerate(self._paragraphs):
            if i < start_idx:
                continue
            if search in p._text:
                return TextRangeStub(0, len(search), search)
        return None

    def find_paragraph_by_text(self, text):
        for i, p in enumerate(self._paragraphs):
            if p._text == text:
                return i
        return None


class _WriterStyleFamilies(NameAccessStub):
    def __init__(self):
        super().__init__(
            {
                "ParagraphStyles": _StyleFamilyStub(
                    [
                        ("Heading 1", False, True, "Standard"),
                        ("Heading 2", False, True, "Heading 1"),
                        ("Heading 3", False, True, "Heading 2"),
                        ("Text Body", False, True, "Standard"),
                        ("Title", False, True, "Standard"),
                        ("Standard", False, True, None),
                        ("List Bullet", False, True, "Standard"),
                    ]
                ),
                "CharacterStyles": _StyleFamilyStub([]),
                "PageStyles": _StyleFamilyStub([]),
            }
        )


class _StyleFamilyStub(NameAccessStub):
    def __init__(self, style_defs=None):
        items = {}
        for name, is_user, is_in_use, parent in style_defs or []:
            items[name] = _StyleEntryStub(name, is_user, is_in_use, parent)
        super().__init__(items)
        self._style_defs = style_defs


class _StyleEntryStub(PropertyHolder, ServiceInfoMixin):
    def __init__(self, name, is_user_defined=False, is_in_use=False, parent=None):
        super().__init__(ParentStyle=parent)
        self._name = name
        self._is_user_defined = is_user_defined
        self._is_in_use = is_in_use
        self._services = set()

    def isUserDefined(self):
        return self._is_user_defined

    def isInUse(self):
        return self._is_in_use


class _DocPropertiesStub:
    def __init__(self):
        self.Title = ""
        self.Subject = ""
        self.Author = ""
        self.Description = ""
        self.Keywords = ()

    def getUserDefinedProperties(self):
        return _UserDefinedPropsStub()


class _UserDefinedPropsStub:
    def __init__(self):
        self._props = {}
        self._values = {}

    def getPropertyValue(self, name):
        if name in self._values:
            return self._values[name]
        raise AttributeError("Property '%s' not found" % name)

    def addProperty(self, name, attrs, value):
        self._values[name] = value


class _SearchDescriptorStub(PropertyHolder):
    def __init__(self):
        super().__init__()
        self.SearchString = ""
        self.SearchRegularExpression = False
        self.SearchCaseSensitive = True


class _ReplaceDescriptorStub(_SearchDescriptorStub):
    def __init__(self):
        super().__init__()
        self.ReplaceString = ""


class ControllerStub:
    def __init__(self, doc):
        self._doc = doc
        self._selection = None
        self._view_cursor = None

    def getModel(self):
        return self._doc

    def getFrame(self):
        return _FrameStub()

    def getSelection(self):
        return self._selection

    def getViewCursor(self):
        return self._view_cursor


class _TextFieldEnumerationStub:
    def __init__(self, comments=None):
        self._comments = list(comments or [])

    def createEnumeration(self):
        return _ListEnumerator(self._comments)

    def getCount(self):
        return len(self._comments)


class _ListEnumerator:
    def __init__(self, items):
        self._items = list(items)
        self._index = 0

    def hasMoreElements(self):
        return self._index < len(self._items)

    def nextElement(self):
        if self._index >= len(self._items):
            raise StopIteration
        item = self._items[self._index]
        self._index += 1
        return item


class _AnnotationStub(PropertyHolder, ServiceInfoMixin):
    def __init__(
        self,
        author="",
        content="",
        name="",
        parent_name="",
        resolved=False,
        date_year=2025,
        date_month=1,
        date_day=1,
        date_hours=12,
        date_minutes=0,
    ):
        super().__init__()
        self._services = {"com.sun.star.text.textfield.Annotation"}
        self.Author = author
        self.Content = content
        self.Name = name
        self.ParentName = parent_name
        self.Resolved = resolved
        self._date = _DateStub(
            date_year, date_month, date_day, date_hours, date_minutes
        )

    def getAnchor(self):
        return _AnchorStub()

    def getPropertyValues(self):
        return {}


class _DateStub:
    def __init__(self, year, month, day, hours, minutes):
        self.Year = year
        self.Month = month
        self.Day = day
        self.Hours = hours
        self.Minutes = minutes


class _AnchorStub:
    def getStart(self):
        return TextRangeStub(0, 0, "")

    def getString(self):
        return ""

    def setString(self, value):
        pass


class _FrameStub:
    def getTitle(self):
        return "TestWriter"

    def activate(self):
        pass
