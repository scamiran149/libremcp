import pytest

from stubs.uno_stubs import install_uno_stubs

install_uno_stubs()

from stubs.writer_stubs import WriterDocStub
from stubs.calc_stubs import CalcDocStub
from stubs.draw_stubs import DrawDocStub
from stubs.service_stubs import StubServiceRegistry, StubJobManager
from plugin.framework.tool_context import ToolContext
from plugin.framework.tool_registry import ToolRegistry

from plugin.modules.doc.tools.undo import Undo, Redo
from plugin.modules.doc.tools.print_doc import PrintDocument
from plugin.modules.doc.tools.hyperlinks import (
    ListHyperlinks,
    InsertHyperlink,
    RemoveHyperlink,
    EditHyperlink,
)
from plugin.modules.doc.tools.file_ops import (
    SaveDocument,
    ExportPdf,
    SaveDocumentAs,
    CreateDocument,
    OpenDocument,
    CloseDocument,
    ListOpenDocuments,
    GetRecentDocuments,
    SetDocumentProperties,
)
from plugin.modules.doc.tools.document_info import GetDocumentInfo
from plugin.modules.doc.tools.diagnostics import (
    DocumentHealthCheck,
    SetDocumentProtection,
)
from plugin.modules.core.tools.list_jobs import ListJobs
from plugin.modules.core.tools.get_job import GetJob
from plugin.modules.batch.tools.batch import ExecuteBatch


def _make_ctx(doc, doc_type, services):
    return ToolContext(
        doc=doc, ctx=None, doc_type=doc_type, services=services, caller="test"
    )


def _replace_service(services, name, instance):
    services._services[name] = instance
    return services


def _writer_ctx(doc=None, services=None):
    doc = doc or WriterDocStub()
    services = services or StubServiceRegistry(doc)
    return _make_ctx(doc, "writer", services)


def _calc_ctx(doc=None, services=None):
    doc = doc or CalcDocStub()
    services = services or StubServiceRegistry(doc)
    return _make_ctx(doc, "calc", services)


def _draw_ctx(doc=None, services=None):
    doc = doc or DrawDocStub(doc_type="draw")
    doc.add_page()
    services = services or StubServiceRegistry(doc)
    return _make_ctx(doc, "draw", services)


class _UndoManagerStub:
    def __init__(self, undo_count=0, redo_count=0):
        self._undo_count = undo_count
        self._redo_count = redo_count

    def isUndoPossible(self):
        return self._undo_count > 0

    def isRedoPossible(self):
        return self._redo_count > 0

    def undo(self):
        if self._undo_count > 0:
            self._undo_count -= 1
            self._redo_count += 1

    def redo(self):
        if self._redo_count > 0:
            self._redo_count -= 1
            self._undo_count += 1

    def enterUndoContext(self, title):
        pass

    def leaveUndoContext(self):
        pass


class _DocWithModified(WriterDocStub):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._modified = False
        self._cached_props = None

    def getUndoManager(self):
        return self._undo_mgr

    def isModified(self):
        return self._modified

    def getDocumentProperties(self):
        if self._cached_props is None:
            self._cached_props = super().getDocumentProperties()
        return self._cached_props


class _CalcDocWithModified(CalcDocStub):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._modified = False
        self._cached_props = None

    def isModified(self):
        return self._modified

    def getDocumentProperties(self):
        if self._cached_props is None:
            self._cached_props = super().getDocumentProperties()
        return self._cached_props


class _DrawDocWithModified(DrawDocStub):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._modified = False
        self._cached_props = None

    def isModified(self):
        return self._modified

    def getDocumentProperties(self):
        if self._cached_props is None:
            self._cached_props = super().getDocumentProperties()
        return self._cached_props


class _TextSectionsStub:
    def __init__(self, sections=None):
        self._sections = sections or []

    def getCount(self):
        return len(self._sections)

    def getByIndex(self, index):
        return self._sections[index]


class _SectionStub:
    def __init__(self):
        self._protected = False
        self._password = None

    def setPropertyValue(self, name, value):
        if name == "IsProtected":
            self._protected = value

    def getPropertyValue(self, name):
        if name == "IsProtected":
            return self._protected
        return None

    def setProtectionPassword(self, password):
        self._password = password


class _WriterDocWithSections(_DocWithModified):
    def __init__(self, section_count=0, **kwargs):
        super().__init__(**kwargs)
        self._sections = _TextSectionsStub(
            [_SectionStub() for _ in range(section_count)]
        )

    def getTextSections(self):
        return self._sections


class _JobStub:
    def __init__(self, job_id, status="completed", result=None):
        self.job_id = job_id
        self._status = status
        self._result = result

    def to_dict(self):
        return {"job_id": self.job_id, "status": self._status, "result": self._result}


class _StubJobsService:
    name = "jobs"

    def __init__(self, jobs=None):
        self._jobs = jobs or {}

    def list(self, limit=10):
        return list(self._jobs.values())[:limit]

    def get(self, job_id):
        return self._jobs.get(job_id)

    def submit(self, func, **kwargs):
        return "stub-job-id"


def _make_services_with_jobs(jobs=None):
    reg = StubServiceRegistry()
    _replace_service(reg, "jobs", _StubJobsService(jobs))
    return reg


# ── Undo ────────────────────────────────────────────────────


class TestUndo:
    def test_execute_happy_path(self):
        doc = _WriterDocWithSections(section_count=0)
        doc._undo_mgr = _UndoManagerStub(undo_count=3, redo_count=0)
        ctx = _writer_ctx(doc)
        tool = Undo()
        result = tool.execute(ctx, steps=2)
        assert result["status"] == "ok"
        assert result["undone"] == 2
        assert result["can_undo"] is True
        assert result["can_redo"] is True

    def test_execute_none_available(self):
        doc = _WriterDocWithSections(section_count=0)
        doc._undo_mgr = _UndoManagerStub(undo_count=0, redo_count=0)
        ctx = _writer_ctx(doc)
        tool = Undo()
        result = tool.execute(ctx, steps=5)
        assert result["status"] == "ok"
        assert result["undone"] == 0

    def test_execute_default_one_step(self):
        doc = _WriterDocWithSections(section_count=0)
        doc._undo_mgr = _UndoManagerStub(undo_count=2, redo_count=0)
        ctx = _writer_ctx(doc)
        tool = Undo()
        result = tool.execute(ctx)
        assert result["undone"] == 1

    def test_execute_no_undo_manager(self):
        doc = WriterDocStub()
        ctx = _writer_ctx(doc)
        tool = Undo()
        result = tool.execute(ctx)
        assert result["status"] == "error"

    def test_is_mutation(self):
        assert Undo().detects_mutation() is True

    def test_no_required_params(self):
        tool = Undo()
        ok, _ = tool.validate()
        assert ok is True

    def test_doc_types_universal(self):
        assert Undo.doc_types is None


# ── Redo ────────────────────────────────────────────────────


class TestRedo:
    def test_execute_happy_path(self):
        doc = _WriterDocWithSections(section_count=0)
        doc._undo_mgr = _UndoManagerStub(undo_count=0, redo_count=2)
        ctx = _writer_ctx(doc)
        tool = Redo()
        result = tool.execute(ctx, steps=1)
        assert result["status"] == "ok"
        assert result["redone"] == 1
        assert result["can_redo"] is True

    def test_execute_none_available(self):
        doc = _WriterDocWithSections(section_count=0)
        doc._undo_mgr = _UndoManagerStub(undo_count=0, redo_count=0)
        ctx = _writer_ctx(doc)
        tool = Redo()
        result = tool.execute(ctx, steps=5)
        assert result["status"] == "ok"
        assert result["redone"] == 0

    def test_execute_no_undo_manager(self):
        doc = WriterDocStub()
        ctx = _writer_ctx(doc)
        tool = Redo()
        result = tool.execute(ctx)
        assert result["status"] == "error"

    def test_is_mutation(self):
        assert Redo().detects_mutation() is True

    def test_doc_types_universal(self):
        assert Redo.doc_types is None


# ── PrintDocument ────────────────────────────────────────────


class TestPrintDocument:
    def test_is_not_mutation(self):
        assert PrintDocument().detects_mutation() is False

    def test_no_required_params(self):
        tool = PrintDocument()
        ok, _ = tool.validate()
        assert ok is True

    def test_doc_types_universal(self):
        assert PrintDocument.doc_types is None

    def test_validate_optional_params(self):
        tool = PrintDocument()
        ok, _ = tool.validate(printer="HP", pages="1-3", copies=2)
        assert ok is True


# ── ListHyperlinks ──────────────────────────────────────────


class TestListHyperlinks:
    def test_is_not_mutation(self):
        assert ListHyperlinks().detects_mutation() is False

    def test_no_required_params(self):
        tool = ListHyperlinks()
        ok, _ = tool.validate()
        assert ok is True

    def test_doc_types_writer_calc(self):
        assert ListHyperlinks.doc_types == ["writer", "calc"]

    def test_validate_with_calc_options(self):
        tool = ListHyperlinks()
        ok, _ = tool.validate(calc={"sheet_name": "Sheet1"})
        assert ok is True


# ── InsertHyperlink ─────────────────────────────────────────


class TestInsertHyperlink:
    def test_is_mutation(self):
        assert InsertHyperlink().detects_mutation() is True

    def test_url_required(self):
        tool = InsertHyperlink()
        ok, err = tool.validate()
        assert ok is False
        assert "url" in err

    def test_validate_with_url(self):
        tool = InsertHyperlink()
        ok, _ = tool.validate(url="https://example.com")
        assert ok is True

    def test_doc_types_writer_calc(self):
        assert InsertHyperlink.doc_types == ["writer", "calc"]

    def test_execute_missing_url_returns_error(self):
        ctx = _writer_ctx()
        tool = InsertHyperlink()
        result = tool.execute(ctx, url="")
        assert result["status"] == "error"


# ── RemoveHyperlink ─────────────────────────────────────────


class TestRemoveHyperlink:
    def test_is_mutation(self):
        assert RemoveHyperlink().detects_mutation() is True

    def test_index_required(self):
        tool = RemoveHyperlink()
        ok, err = tool.validate()
        assert ok is False
        assert "index" in err

    def test_validate_with_index(self):
        tool = RemoveHyperlink()
        ok, _ = tool.validate(index=0)
        assert ok is True

    def test_doc_types_writer_calc(self):
        assert RemoveHyperlink.doc_types == ["writer", "calc"]


# ── EditHyperlink ────────────────────────────────────────────


class TestEditHyperlink:
    def test_is_mutation(self):
        assert EditHyperlink().detects_mutation() is True

    def test_index_required(self):
        tool = EditHyperlink()
        ok, err = tool.validate()
        assert ok is False
        assert "index" in err

    def test_validate_with_index(self):
        tool = EditHyperlink()
        ok, _ = tool.validate(index=1, url="https://new.com")
        assert ok is True

    def test_doc_types_writer_calc(self):
        assert EditHyperlink.doc_types == ["writer", "calc"]

    def test_execute_no_changes_returns_error(self):
        ctx = _writer_ctx()
        tool = EditHyperlink()
        result = tool.execute(ctx, index=0)
        assert result["status"] == "error"


# ── SaveDocument ─────────────────────────────────────────────


class TestSaveDocument:
    def test_is_mutation(self):
        assert SaveDocument().detects_mutation() is True

    def test_no_required_params(self):
        tool = SaveDocument()
        ok, _ = tool.validate()
        assert ok is True

    def test_doc_types_universal(self):
        assert SaveDocument.doc_types is None


# ── ExportPdf ────────────────────────────────────────────────


class TestExportPdf:
    def test_is_not_mutation(self):
        assert ExportPdf().detects_mutation() is False

    def test_path_required(self):
        tool = ExportPdf()
        ok, err = tool.validate()
        assert ok is False
        assert "path" in err

    def test_validate_with_path(self):
        tool = ExportPdf()
        ok, _ = tool.validate(path="/tmp/out.pdf")
        assert ok is True

    def test_doc_types_universal(self):
        assert ExportPdf.doc_types is None


# ── SaveDocumentAs ───────────────────────────────────────────


class TestSaveDocumentAs:
    def test_is_not_mutation(self):
        assert SaveDocumentAs().detects_mutation() is False

    def test_target_path_required(self):
        tool = SaveDocumentAs()
        ok, err = tool.validate()
        assert ok is False
        assert "target_path" in err

    def test_doc_types_universal(self):
        assert SaveDocumentAs.doc_types is None


# ── CreateDocument ───────────────────────────────────────────


class TestCreateDocument:
    def test_is_not_mutation(self):
        assert CreateDocument().detects_mutation() is False

    def test_doc_type_param_required(self):
        tool = CreateDocument()
        ok, err = tool.validate()
        assert ok is False
        assert "doc_type" in err

    def test_validate_invalid_enum(self):
        tool = CreateDocument()
        ok, err = tool.validate(doc_type="invalid")
        assert ok is False

    def test_validate_valid_enum(self):
        tool = CreateDocument()
        for dt in ("writer", "calc", "impress", "draw"):
            ok, _ = tool.validate(doc_type=dt)
            assert ok is True

    def test_doc_types_universal(self):
        assert CreateDocument.doc_types is None

    def test_requires_doc_false(self):
        assert CreateDocument.requires_doc is False

    def test_execute_unknown_doc_type(self):
        ctx = _writer_ctx()
        tool = CreateDocument()
        result = tool.execute(ctx, doc_type="invalid_type")
        assert result["status"] == "error"


# ── OpenDocument ─────────────────────────────────────────────


class TestOpenDocument:
    def test_is_not_mutation(self):
        assert OpenDocument().detects_mutation() is False

    def test_file_path_required(self):
        tool = OpenDocument()
        ok, err = tool.validate()
        assert ok is False
        assert "file_path" in err

    def test_doc_types_universal(self):
        assert OpenDocument.doc_types is None

    def test_requires_doc_false(self):
        assert OpenDocument.requires_doc is False


# ── CloseDocument ────────────────────────────────────────────


class TestCloseDocument:
    def test_is_mutation(self):
        assert CloseDocument().detects_mutation() is True

    def test_no_required_params(self):
        tool = CloseDocument()
        ok, _ = tool.validate()
        assert ok is True

    def test_doc_types_universal(self):
        assert CloseDocument.doc_types is None


# ── ListOpenDocuments ────────────────────────────────────────


class TestListOpenDocuments:
    def test_execute_happy_path(self):
        doc = WriterDocStub()
        svc = StubServiceRegistry(doc)
        ctx = _make_ctx(doc, "writer", svc)
        tool = ListOpenDocuments()
        result = tool.execute(ctx)
        assert result["status"] == "ok"
        assert "documents" in result
        assert result["count"] >= 0

    def test_doc_types_universal(self):
        assert ListOpenDocuments.doc_types is None

    def test_requires_doc_false(self):
        assert ListOpenDocuments.requires_doc is False


# ── GetRecentDocuments ───────────────────────────────────────


class TestGetRecentDocuments:
    def test_no_required_params(self):
        tool = GetRecentDocuments()
        ok, _ = tool.validate()
        assert ok is True

    def test_doc_types_universal(self):
        assert GetRecentDocuments.doc_types is None

    def test_requires_doc_false(self):
        assert GetRecentDocuments.requires_doc is False


# ── SetDocumentProperties ────────────────────────────────────


class TestSetDocumentProperties:
    def test_is_mutation(self):
        assert SetDocumentProperties().detects_mutation() is True

    def test_no_required_params(self):
        tool = SetDocumentProperties()
        ok, _ = tool.validate()
        assert ok is True

    def test_doc_types_universal(self):
        assert SetDocumentProperties.doc_types is None

    def test_execute_no_properties_returns_error(self):
        ctx = _writer_ctx()
        tool = SetDocumentProperties()
        result = tool.execute(ctx)
        assert result["status"] == "error"

    def test_execute_update_title(self):
        ctx = _writer_ctx()
        tool = SetDocumentProperties()
        result = tool.execute(ctx, title="Test Doc")
        assert result["status"] == "ok"
        assert "title" in result["updated"]

    def test_execute_update_multiple(self):
        ctx = _writer_ctx()
        tool = SetDocumentProperties()
        result = tool.execute(
            ctx,
            title="T",
            author="A",
            subject="S",
            description="D",
            keywords=["k1", "k2"],
        )
        assert result["status"] == "ok"
        assert len(result["updated"]) == 5

    def test_execute_update_keywords(self):
        ctx = _writer_ctx()
        tool = SetDocumentProperties()
        result = tool.execute(ctx, keywords=["alpha", "beta"])
        assert result["status"] == "ok"
        assert "keywords" in result["updated"]

    def test_execute_on_calc(self):
        ctx = _calc_ctx()
        tool = SetDocumentProperties()
        result = tool.execute(ctx, title="Calc Doc")
        assert result["status"] == "ok"

    def test_execute_on_draw(self):
        ctx = _draw_ctx()
        tool = SetDocumentProperties()
        result = tool.execute(ctx, author="Artist")
        assert result["status"] == "ok"


# ── GetDocumentInfo ──────────────────────────────────────────


class TestGetDocumentInfo:
    def test_execute_writer(self):
        doc = _DocWithModified()
        doc.add_paragraph("Hello", style="Text Body")
        ctx = _writer_ctx(doc)
        tool = GetDocumentInfo()
        result = tool.execute(ctx)
        assert result["status"] == "ok"
        assert result["doc_type"] == "writer"
        assert result["is_modified"] is False
        assert "doc_id" in result

    def test_execute_calc(self):
        doc = _CalcDocWithModified()
        doc.add_sheet("Sheet1")
        svc = StubServiceRegistry(doc)
        ctx = _make_ctx(doc, "calc", svc)
        tool = GetDocumentInfo()
        result = tool.execute(ctx)
        assert result["status"] == "ok"
        assert result["doc_type"] == "calc"

    def test_execute_draw(self):
        doc = _DrawDocWithModified(doc_type="draw")
        doc.add_page()
        svc = StubServiceRegistry(doc)
        ctx = _make_ctx(doc, "draw", svc)
        tool = GetDocumentInfo()
        result = tool.execute(ctx)
        assert result["status"] == "ok"
        assert result["doc_type"] == "draw"

    def test_is_not_mutation(self):
        assert GetDocumentInfo().detects_mutation() is False

    def test_no_required_params(self):
        tool = GetDocumentInfo()
        ok, _ = tool.validate()
        assert ok is True

    def test_doc_types_universal(self):
        assert GetDocumentInfo.doc_types is None

    def test_url_populated(self):
        doc = _DocWithModified(url="file:///tmp/test.odt")
        ctx = _writer_ctx(doc)
        tool = GetDocumentInfo()
        result = tool.execute(ctx)
        assert result["file_url"] == "file:///tmp/test.odt"
        assert result["is_new"] is False

    def test_no_url_means_new(self):
        doc = _DocWithModified(url="")
        ctx = _writer_ctx(doc)
        tool = GetDocumentInfo()
        result = tool.execute(ctx)
        assert result["is_new"] is True

    def test_properties_fields(self):
        doc = _DocWithModified()
        props = doc.getDocumentProperties()
        props.Title = "My Doc"
        props.Author = "Me"
        ctx = _writer_ctx(doc)
        tool = GetDocumentInfo()
        result = tool.execute(ctx)
        assert result["title"] == "My Doc"
        assert result["author"] == "Me"

    def test_title_fallback_to_filename(self):
        doc = _DocWithModified(url="file:///tmp/report.odt")
        ctx = _writer_ctx(doc)
        tool = GetDocumentInfo()
        result = tool.execute(ctx)
        assert result["title"] == "report.odt"


# ── DocumentHealthCheck ─────────────────────────────────────


class TestDocumentHealthCheck:
    def test_execute_clean_writer(self):
        doc = WriterDocStub()
        doc.add_paragraph("Intro", style="Heading 1")
        doc.add_paragraph("Body text.", style="Text Body")
        doc.add_paragraph("Details", style="Heading 2")
        ctx = _writer_ctx(doc)
        tool = DocumentHealthCheck()
        result = tool.execute(ctx)
        assert result["status"] == "ok"
        assert result["issue_count"] == 0
        assert result["total_headings"] == 2

    def test_execute_detects_heading_jump(self):
        doc = WriterDocStub()
        doc.add_paragraph("H1", style="Heading 1")
        doc.add_paragraph("Body.", style="Text Body")
        doc.add_paragraph("H3 (skips 2)", style="Heading 3")
        ctx = _writer_ctx(doc)
        tool = DocumentHealthCheck()
        result = tool.execute(ctx)
        assert result["status"] == "ok"
        assert result["issue_count"] >= 1
        types = [i["type"] for i in result["issues"]]
        assert "heading_level_skip" in types

    def test_is_not_mutation(self):
        assert DocumentHealthCheck().detects_mutation() is False

    def test_doc_types_writer_only(self):
        assert DocumentHealthCheck.doc_types == ["writer"]

    def test_execute_with_empty_heading(self):
        doc = WriterDocStub()
        doc.add_paragraph("", style="Heading 1")
        ctx = _writer_ctx(doc)
        tool = DocumentHealthCheck()
        result = tool.execute(ctx)
        assert result["status"] == "ok"
        types = [i["type"] for i in result["issues"]]
        assert "empty_heading" in types


# ── SetDocumentProtection ────────────────────────────────────


class TestSetDocumentProtection:
    def test_enabled_is_required(self):
        tool = SetDocumentProtection()
        ok, err = tool.validate()
        assert ok is False
        assert "enabled" in err

    def test_is_mutation(self):
        assert SetDocumentProtection().detects_mutation() is True

    def test_doc_types_writer_only(self):
        assert SetDocumentProtection.doc_types == ["writer"]

    def test_execute_no_sections(self):
        doc = _WriterDocWithSections(section_count=0)
        ctx = _writer_ctx(doc)
        tool = SetDocumentProtection()
        result = tool.execute(ctx, enabled=True)
        assert result["status"] == "ok"
        assert result["sections_count"] == 0

    def test_execute_with_sections(self):
        doc = _WriterDocWithSections(section_count=2)
        ctx = _writer_ctx(doc)
        tool = SetDocumentProtection()
        result = tool.execute(ctx, enabled=True)
        assert result["status"] == "ok"
        assert result["sections_count"] == 2
        assert result["protected"] is True

    def test_execute_unprotect(self):
        doc = _WriterDocWithSections(section_count=1)
        ctx = _writer_ctx(doc)
        tool = SetDocumentProtection()
        result = tool.execute(ctx, enabled=False)
        assert result["status"] == "ok"
        assert result["protected"] is False


# ── ListJobs ─────────────────────────────────────────────────


class TestListJobs:
    def test_execute_happy_path(self):
        jobs_svc = _StubJobsService({"j1": _JobStub("j1", "completed", {"x": 1})})
        svc = _make_services_with_jobs(jobs_svc._jobs)
        _replace_service(svc, "jobs", jobs_svc)
        ctx = _make_ctx(WriterDocStub(), "writer", svc)
        tool = ListJobs()
        result = tool.execute(ctx)
        assert result["status"] == "ok"
        assert len(result["jobs"]) == 1

    def test_execute_empty(self):
        svc = _make_services_with_jobs()
        ctx = _make_ctx(WriterDocStub(), "writer", svc)
        tool = ListJobs()
        result = tool.execute(ctx)
        assert result["status"] == "ok"
        assert result["jobs"] == []

    def test_execute_limit(self):
        jobs_svc = _StubJobsService({"j%d" % i: _JobStub("j%d" % i) for i in range(20)})
        svc = _make_services_with_jobs()
        _replace_service(svc, "jobs", jobs_svc)
        ctx = _make_ctx(WriterDocStub(), "writer", svc)
        tool = ListJobs()
        result = tool.execute(ctx, limit=5)
        assert result["status"] == "ok"
        assert len(result["jobs"]) == 5

    def test_is_not_mutation(self):
        assert ListJobs().detects_mutation() is False

    def test_doc_types_universal(self):
        assert ListJobs.doc_types is None

    def test_no_required_params(self):
        tool = ListJobs()
        ok, _ = tool.validate()
        assert ok is True


# ── GetJob ───────────────────────────────────────────────────


class TestGetJob:
    def test_execute_happy_path(self):
        job = _JobStub("j42", "completed", {"output": "done"})
        jobs_svc = _StubJobsService({"j42": job})
        svc = _make_services_with_jobs()
        _replace_service(svc, "jobs", jobs_svc)
        ctx = _make_ctx(WriterDocStub(), "writer", svc)
        tool = GetJob()
        result = tool.execute(ctx, job_id="j42")
        assert result["job_id"] == "j42"
        assert "status" in result

    def test_execute_not_found(self):
        svc = _make_services_with_jobs()
        ctx = _make_ctx(WriterDocStub(), "writer", svc)
        tool = GetJob()
        result = tool.execute(ctx, job_id="missing")
        assert result["status"] == "error"

    def test_job_id_required(self):
        tool = GetJob()
        ok, err = tool.validate()
        assert ok is False
        assert "job_id" in err

    def test_is_not_mutation(self):
        assert GetJob().detects_mutation() is False

    def test_doc_types_universal(self):
        assert GetJob.doc_types is None


# ── ExecuteBatch ─────────────────────────────────────────────


class TestExecuteBatch:
    def test_operations_required(self):
        tool = ExecuteBatch()
        ok, err = tool.validate()
        assert ok is False
        assert "operations" in err

    def test_is_mutation(self):
        assert ExecuteBatch().detects_mutation() is True

    def test_execute_empty_operations(self):
        ctx = _writer_ctx()
        tool = ExecuteBatch()
        result = tool.execute(ctx, operations=[])
        assert result["status"] == "error"

    def test_execute_too_many_operations(self):
        ctx = _writer_ctx()
        tool = ExecuteBatch()
        ops = [{"tool": "get_document_info"} for _ in range(51)]
        result = tool.execute(ctx, operations=ops)
        assert result["status"] == "error"

    def test_execute_recursive_batch_rejected(self):
        svc = StubServiceRegistry()
        reg = ToolRegistry(svc)
        reg.register(GetDocumentInfo())
        reg.register(ExecuteBatch())
        _replace_service(svc, "tools", reg)
        ctx = _make_ctx(_DocWithModified(), "writer", svc)
        result = reg.execute(
            "execute_batch",
            ctx,
            operations=[{"tool": "execute_batch", "args": {"operations": []}}],
        )
        assert result["status"] == "error"
        assert any(
            "Recursive" in str(e.get("error", ""))
            for e in result.get("validation_errors", [{}])
        )

    def test_execute_unknown_tool_rejected(self):
        svc = StubServiceRegistry()
        reg = ToolRegistry(svc)
        reg.register(GetDocumentInfo())
        reg.register(ExecuteBatch())
        _replace_service(svc, "tools", reg)
        ctx = _make_ctx(_DocWithModified(), "writer", svc)
        result = reg.execute(
            "execute_batch", ctx, operations=[{"tool": "nonexistent_tool"}]
        )
        assert result["status"] == "error"

    def test_execute_single_step(self):
        svc = StubServiceRegistry()
        reg = ToolRegistry(svc)
        reg.register(GetDocumentInfo())
        reg.register(ExecuteBatch())
        _replace_service(svc, "tools", reg)
        ctx = _make_ctx(_DocWithModified(), "writer", svc)
        result = reg.execute(
            "execute_batch", ctx, operations=[{"tool": "get_document_info"}]
        )
        assert result["status"] == "ok"
        assert result["completed"] == 1

    def test_validate_valid_operations(self):
        tool = ExecuteBatch()
        ok, _ = tool.validate(operations=[{"tool": "undo"}])
        assert ok is True
