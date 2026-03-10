# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""File operation tools: save, export, lifecycle, metadata."""

import logging
import os

import uno
from com.sun.star.beans import PropertyValue

from plugin.framework.tool_base import ToolBase
from plugin.framework.uno_context import get_ctx

log = logging.getLogger("nelson.common")

_PDF_FILTERS = {
    "writer": "writer_pdf_Export",
    "calc": "calc_pdf_Export",
    "draw": "draw_pdf_Export",
    "impress": "impress_pdf_Export",
}


class SaveDocument(ToolBase):
    """Save the current document to its existing location."""

    name = "save_document"
    description = (
        "Saves the current document. Only works if the document has already "
        "been saved to a file (has a URL). Returns an error for unsaved "
        "new documents."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    doc_types = None
    tier = "core"
    is_mutation = True

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        url = doc.getURL()
        if not url:
            return {
                "status": "error",
                "error": "Document has never been saved. Use File > Save As "
                         "in LibreOffice to save it first.",
            }

        doc.store()
        return {"status": "ok", "file_url": url}


class ExportPdf(ToolBase):
    """Export the current document as PDF."""

    name = "export_pdf"
    description = (
        "Exports the current document to a PDF file at the given path."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Output PDF file path (absolute).",
            },
        },
        "required": ["path"],
    }
    doc_types = None
    tier = "core"
    is_mutation = False

    def execute(self, ctx, **kwargs):
        path = kwargs["path"]
        doc_type = ctx.doc_type

        filter_name = _PDF_FILTERS.get(doc_type)
        if not filter_name:
            return {
                "status": "error",
                "error": "Unsupported document type for PDF export: %s"
                         % doc_type,
            }

        # Convert local path to file:// URL.
        if not path.startswith("file://"):
            url = uno.systemPathToFileUrl(path)
        else:
            url = path

        pv = PropertyValue()
        pv.Name = "FilterName"
        pv.Value = filter_name

        try:
            ctx.doc.storeToURL(url, (pv,))
        except Exception as exc:
            log.exception("PDF export failed: %s", exc)
            return {"status": "error", "error": str(exc)}

        return {"status": "ok", "file_url": url, "filter": filter_name}


# ── Extension → filter name mapping ──────────────────────────────────

_EXT_FILTERS = {
    ".odt": "writer8",
    ".docx": "MS Word 2007 XML",
    ".ods": "calc8",
    ".xlsx": "Calc MS Excel 2007 XML",
    ".odp": "impress8",
    ".pptx": "Impress MS PowerPoint 2007 XML",
}


class SaveDocumentAs(ToolBase):
    """Save a copy of the document to a new path."""

    name = "save_document_as"
    intent = "media"
    description = "Save a copy of the document to a new path."
    parameters = {
        "type": "object",
        "properties": {
            "target_path": {
                "type": "string",
                "description": "Absolute file path to save the copy to.",
            },
        },
        "required": ["target_path"],
    }
    doc_types = None
    is_mutation = False

    def execute(self, ctx, **kwargs):
        target_path = kwargs["target_path"]

        # Convert to file:// URL.
        url = uno.systemPathToFileUrl(target_path)

        # Determine filter from extension.
        _, ext = os.path.splitext(target_path)
        ext = ext.lower()
        filter_name = _EXT_FILTERS.get(ext)
        if not filter_name:
            return {
                "status": "error",
                "error": "Unsupported file extension: %s. Supported: %s"
                         % (ext, ", ".join(sorted(_EXT_FILTERS))),
            }

        pv = PropertyValue()
        pv.Name = "FilterName"
        pv.Value = filter_name

        try:
            ctx.doc.storeToURL(url, (pv,))
        except Exception as exc:
            log.exception("SaveAs failed: %s", exc)
            return {"status": "error", "error": str(exc)}

        return {"status": "ok", "file_url": url}


# ── Factory URLs for new documents ───────────────────────────────────

_FACTORY_URLS = {
    "writer": "private:factory/swriter",
    "calc": "private:factory/scalc",
    "impress": "private:factory/simpress",
    "draw": "private:factory/sdraw",
}


def _get_desktop():
    """Return the com.sun.star.frame.Desktop singleton."""
    ctx = get_ctx()
    smgr = ctx.ServiceManager
    return smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)


class CreateDocument(ToolBase):
    """Create a new empty document in LibreOffice."""

    name = "create_document"
    intent = "media"
    description = "Create a new empty document in LibreOffice."
    parameters = {
        "type": "object",
        "properties": {
            "doc_type": {
                "type": "string",
                "enum": ["writer", "calc", "impress", "draw"],
                "description": "Type of document to create.",
            },
            "content": {
                "type": "string",
                "description": (
                    "Optional initial text content (only for writer documents)."
                ),
            },
        },
        "required": ["doc_type"],
    }
    doc_types = None
    is_mutation = False
    requires_doc = False

    def execute(self, ctx, **kwargs):
        doc_type = kwargs["doc_type"]
        content = kwargs.get("content")

        factory_url = _FACTORY_URLS.get(doc_type)
        if not factory_url:
            return {
                "status": "error",
                "error": "Unknown doc_type: %s" % doc_type,
            }

        try:
            desktop = _get_desktop()
            new_doc = desktop.loadComponentFromURL(
                factory_url, "_blank", 0, ()
            )
        except Exception as exc:
            log.exception("CreateDocument failed: %s", exc)
            return {"status": "error", "error": str(exc)}

        # Optionally set initial content for writer documents.
        if content and doc_type == "writer":
            try:
                new_doc.getText().setString(content)
            except Exception as exc:
                log.warning("Could not set initial content: %s", exc)

        return {"status": "ok", "doc_type": doc_type}


class OpenDocument(ToolBase):
    """Open a document file in LibreOffice."""

    name = "open_document"
    intent = "media"
    description = "Open a document file in LibreOffice."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the document file.",
            },
        },
        "required": ["file_path"],
    }
    doc_types = None
    is_mutation = False
    requires_doc = False

    def execute(self, ctx, **kwargs):
        file_path = kwargs["file_path"]

        if not file_path.startswith("file://"):
            url = uno.systemPathToFileUrl(file_path)
        else:
            url = file_path

        try:
            desktop = _get_desktop()
            desktop.loadComponentFromURL(url, "_blank", 0, ())
        except Exception as exc:
            log.exception("OpenDocument failed: %s", exc)
            return {"status": "error", "error": str(exc)}

        return {"status": "ok", "file_url": url}


class CloseDocument(ToolBase):
    """Close the current document."""

    name = "close_document"
    intent = "media"
    description = (
        "Close the current document. Use save_document first if needed."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    doc_types = None
    is_mutation = True

    def execute(self, ctx, **kwargs):
        desktop = _get_desktop()
        closing_doc = ctx.doc

        # Collect other document frames before closing
        next_frame = None
        try:
            frames = desktop.getFrames()
            frame_count = frames.getCount()
            log.debug(
                "close_document: %d frames before close", frame_count
            )
            for i in range(frame_count):
                frame = frames.getByIndex(i)
                try:
                    controller = frame.getController()
                    if controller is None:
                        log.debug("  frame %d: no controller", i)
                        continue
                    model = controller.getModel()
                    if model is None:
                        log.debug("  frame %d: no model", i)
                        continue
                    frame_title = frame.getTitle()
                    # Skip the document we're about to close
                    # Use URL + title comparison (UNO proxy identity is unreliable)
                    is_closing = False
                    try:
                        is_closing = (
                            model.getURL() == closing_doc.getURL()
                            and frame_title == closing_doc.getCurrentController().getFrame().getTitle()
                        )
                    except Exception:
                        is_closing = (model is closing_doc)
                    if is_closing:
                        log.debug("  frame %d: closing doc (%s)", i, frame_title)
                        continue
                    # Skip non-document components (Start Center, Basic IDE)
                    if not hasattr(model, "supportsService"):
                        log.debug("  frame %d: not a document (%s)", i, frame_title)
                        continue
                    is_doc = (
                        model.supportsService("com.sun.star.text.TextDocument")
                        or model.supportsService("com.sun.star.sheet.SpreadsheetDocument")
                        or model.supportsService("com.sun.star.drawing.DrawingDocument")
                        or model.supportsService("com.sun.star.presentation.PresentationDocument")
                    )
                    if is_doc:
                        log.debug("  frame %d: next doc candidate (%s)", i, frame_title)
                        next_frame = frame
                        break
                    else:
                        log.debug("  frame %d: not a supported doc (%s)", i, frame_title)
                except Exception:
                    log.debug("  frame %d: exception during inspection", i, exc_info=True)
                    continue
        except Exception:
            log.info("Could not enumerate frames for next-doc activation", exc_info=True)

        # Close the document
        try:
            closing_doc.close(False)
            log.info("close_document: document closed successfully")
        except Exception as exc:
            log.exception("CloseDocument failed: %s", exc)
            return {"status": "error", "error": str(exc)}

        # Activate the next document so getCurrentComponent() returns it
        if next_frame is not None:
            try:
                next_frame.activate()
                next_title = next_frame.getTitle()
                log.info("close_document: activated next doc: %s", next_title)
                return {
                    "status": "ok",
                    "message": "Document closed.",
                    "active_document": next_title,
                }
            except Exception:
                log.warning("close_document: failed to activate next frame", exc_info=True)
        else:
            log.info("close_document: no next frame found")

        return {"status": "ok", "message": "Document closed."}


class ListOpenDocuments(ToolBase):
    """List all currently open documents in LibreOffice."""

    name = "list_open_documents"
    intent = "media"
    description = "List all currently open documents in LibreOffice."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    doc_types = None
    requires_doc = False

    def execute(self, ctx, **kwargs):
        try:
            desktop = _get_desktop()
            frames = desktop.getFrames()
            documents = []
            for i in range(frames.getCount()):
                frame = frames.getByIndex(i)
                comp = frame.getController()
                if comp is None:
                    continue
                doc = comp.getModel()
                if doc is None:
                    continue

                doc_url = ""
                try:
                    doc_url = doc.getURL()
                except Exception:
                    pass

                title = ""
                try:
                    title = doc.getDocumentProperties().Title
                except Exception:
                    pass
                if not title:
                    title = frame.getTitle()

                # Detect document type from supported services.
                dtype = "unknown"
                try:
                    if doc.supportsService(
                        "com.sun.star.text.TextDocument"
                    ):
                        dtype = "writer"
                    elif doc.supportsService(
                        "com.sun.star.sheet.SpreadsheetDocument"
                    ):
                        dtype = "calc"
                    elif doc.supportsService(
                        "com.sun.star.presentation.PresentationDocument"
                    ):
                        dtype = "impress"
                    elif doc.supportsService(
                        "com.sun.star.drawing.DrawingDocument"
                    ):
                        dtype = "draw"
                except Exception:
                    pass

                documents.append({
                    "title": title or "(untitled)",
                    "url": doc_url or None,
                    "doc_type": dtype,
                })

            return {
                "status": "ok",
                "documents": documents,
                "count": len(documents),
            }
        except Exception as exc:
            log.exception("ListOpenDocuments failed: %s", exc)
            return {"status": "error", "error": str(exc)}


class GetRecentDocuments(ToolBase):
    """Get list of recently opened documents from LibreOffice history."""

    name = "get_recent_documents"
    intent = "media"
    description = (
        "Get list of recently opened documents from LibreOffice history."
    )
    parameters = {
        "type": "object",
        "properties": {
            "max_count": {
                "type": "integer",
                "description": "Maximum number of recent documents to return (default 20).",
            },
        },
        "required": [],
    }
    doc_types = None
    requires_doc = False

    def execute(self, ctx, **kwargs):
        max_count = kwargs.get("max_count", 20)
        try:
            uno_ctx = get_ctx()
            smgr = uno_ctx.ServiceManager
            cfg_provider = smgr.createInstanceWithContext(
                "com.sun.star.configuration.ConfigurationProvider", uno_ctx)
            arg = PropertyValue()
            arg.Name = "nodepath"
            arg.Value = (
                "/org.openoffice.Office.Histories/Histories"
                "/org.openoffice.Office.Histories:HistoryInfo['PickList']"
            )
            cfg = cfg_provider.createInstanceWithArguments(
                "com.sun.star.configuration.ConfigurationAccess", (arg,))

            order_list = cfg.getByName("OrderList")
            item_list = cfg.getByName("ItemList")

            docs = []
            names = order_list.getElementNames()
            # Names are string indices — sort numerically
            sorted_names = sorted(names, key=lambda n: int(n))
            for name in sorted_names[:max_count]:
                entry = order_list.getByName(name)
                url = entry.getPropertyValue("HistoryItemRef")
                title = ""
                try:
                    item = item_list.getByName(url)
                    title = item.getPropertyValue("Title")
                except Exception:
                    pass
                try:
                    path = uno.fileUrlToSystemPath(url)
                except Exception:
                    path = url
                doc = {"url": url, "path": path}
                if title:
                    doc["title"] = title
                docs.append(doc)

            return {
                "status": "ok",
                "documents": docs,
                "count": len(docs),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": "Failed to read recent documents: %s" % e,
            }


class SetDocumentProperties(ToolBase):
    """Set document metadata properties."""

    name = "set_document_properties"
    intent = "media"
    description = (
        "Set document metadata properties "
        "(title, subject, author, description, keywords)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Document title.",
            },
            "subject": {
                "type": "string",
                "description": "Document subject.",
            },
            "author": {
                "type": "string",
                "description": "Document author.",
            },
            "description": {
                "type": "string",
                "description": "Document description.",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of keywords.",
            },
        },
        "required": [],
    }
    doc_types = None
    is_mutation = True

    def execute(self, ctx, **kwargs):
        try:
            props = ctx.doc.getDocumentProperties()
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

        updated = []

        if "title" in kwargs:
            props.Title = kwargs["title"]
            updated.append("title")

        if "subject" in kwargs:
            props.Subject = kwargs["subject"]
            updated.append("subject")

        if "author" in kwargs:
            props.Author = kwargs["author"]
            updated.append("author")

        if "description" in kwargs:
            props.Description = kwargs["description"]
            updated.append("description")

        if "keywords" in kwargs:
            props.Keywords = tuple(kwargs["keywords"])
            updated.append("keywords")

        if not updated:
            return {
                "status": "error",
                "error": "No properties provided to update.",
            }

        return {
            "status": "ok",
            "message": "Properties updated.",
            "updated": updated,
        }
