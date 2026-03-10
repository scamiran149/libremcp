# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Cross-document hyperlink tools.

Writer: inserts via XTextField (URL field) or sets HyperLinkURL on text range.
Calc: sets HyperLinkURL property on cell.
Draw/Impress: not supported (shapes have their own URL interaction).
"""

import logging

from plugin.framework.tool_base import ToolBase

log = logging.getLogger("nelson.doc")


class ListHyperlinks(ToolBase):
    """List all hyperlinks in the document."""

    name = "list_hyperlinks"
    intent = "navigate"
    description = (
        "List all hyperlinks in the document. "
        "In Writer, scans text fields and text portions for URLs. "
        "In Calc, scans cells in the used area for HyperLinkURL."
    )
    parameters = {
        "type": "object",
        "properties": {
            "calc": {
                "type": "object",
                "description": "Calc options",
                "properties": {
                    "sheet_name": {
                        "type": "string",
                        "description": "Sheet name (active sheet if omitted).",
                    },
                },
            },
        },
        "required": [],
    }
    doc_types = ["writer", "calc"]

    def execute(self, ctx, **kwargs):
        if ctx.doc_type == "writer":
            return self._list_writer(ctx)
        return self._list_calc(ctx, kwargs.get("sheet_name"))

    def _list_writer(self, ctx):
        """List hyperlinks in Writer via text field enumeration."""
        doc = ctx.doc
        links = []
        try:
            fields = doc.getTextFields()
            enum = fields.createEnumeration()
            idx = 0
            while enum.hasMoreElements():
                field = enum.nextElement()
                try:
                    if field.supportsService("com.sun.star.text.TextField.URL"):
                        url = field.getPropertyValue("URL")
                        rep = field.getPropertyValue("Representation")
                        if url:
                            links.append({
                                "index": idx,
                                "url": url,
                                "text": rep or url,
                                "type": "field",
                            })
                            idx += 1
                except Exception:
                    pass
        except Exception:
            pass

        # Also scan text portions for inline HyperLinkURL
        try:
            text = doc.getText()
            enum = text.createEnumeration()
            while enum.hasMoreElements():
                para = enum.nextElement()
                if not hasattr(para, "createEnumeration"):
                    continue
                portions = para.createEnumeration()
                while portions.hasMoreElements():
                    portion = portions.nextElement()
                    try:
                        url = portion.getPropertyValue("HyperLinkURL")
                        if url:
                            name = portion.getPropertyValue("HyperLinkName")
                            txt = portion.getString()
                            links.append({
                                "index": idx,
                                "url": url,
                                "text": txt or name or url,
                                "type": "inline",
                            })
                            idx += 1
                    except Exception:
                        pass
        except Exception:
            pass

        return {"status": "ok", "hyperlinks": links, "count": len(links)}

    def _list_calc(self, ctx, sheet_name=None):
        """List hyperlinks in Calc cells."""
        doc = ctx.doc
        if sheet_name:
            sheets = doc.getSheets()
            if not sheets.hasByName(sheet_name):
                return {"status": "error", "message": "Sheet not found: %s" % sheet_name}
            sheet = sheets.getByName(sheet_name)
        else:
            sheet = doc.getCurrentController().getActiveSheet()

        links = []
        try:
            cursor = sheet.createCursor()
            cursor.gotoStartOfUsedArea(False)
            cursor.gotoEndOfUsedArea(True)
            ra = cursor.getRangeAddress()

            from plugin.modules.calc.address_utils import index_to_column
            idx = 0
            for r in range(ra.StartRow, ra.EndRow + 1):
                for c in range(ra.StartColumn, ra.EndColumn + 1):
                    cell = sheet.getCellByPosition(c, r)
                    try:
                        tf = cell.getTextFields()
                        if tf and tf.getCount() > 0:
                            for fi in range(tf.getCount()):
                                field = tf.getByIndex(fi)
                                url = field.getPropertyValue("URL")
                                if url:
                                    cell_ref = "%s%d" % (index_to_column(c), r + 1)
                                    links.append({
                                        "index": idx,
                                        "cell": cell_ref,
                                        "url": url,
                                        "text": cell.getString(),
                                    })
                                    idx += 1
                    except Exception:
                        pass
        except Exception as e:
            log.debug("list_hyperlinks calc: %s", e)

        return {
            "status": "ok",
            "sheet": sheet.getName(),
            "hyperlinks": links,
            "count": len(links),
        }


class InsertHyperlink(ToolBase):
    """Insert a hyperlink into the document."""

    name = "insert_hyperlink"
    intent = "edit"
    description = (
        "Insert a hyperlink into the document. "
        "In Writer, inserts a URL text field at the cursor or paragraph position. "
        "In Calc, sets the hyperlink on a cell."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to link to.",
            },
            "text": {
                "type": "string",
                "description": "Display text for the link (defaults to URL).",
            },
            "writer": {
                "type": "object",
                "description": "Writer-specific options",
                "properties": {
                    "paragraph_index": {
                        "type": "integer",
                        "description": "Insert at end of this paragraph.",
                    },
                    "locator": {
                        "type": "string",
                        "description": "Unified locator for insertion point.",
                    },
                },
            },
            "calc": {
                "type": "object",
                "description": "Calc-specific options",
                "properties": {
                    "cell": {
                        "type": "string",
                        "description": "Cell reference (e.g. 'A1').",
                    },
                    "sheet_name": {
                        "type": "string",
                        "description": "Sheet name (active sheet if omitted).",
                    },
                },
            },
        },
        "required": ["url"],
    }
    doc_types = ["writer", "calc"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        url = kwargs.get("url", "")
        if not url:
            return {"status": "error", "message": "url is required."}
        text = kwargs.get("text", url)
        extra = {k: v for k, v in kwargs.items() if k not in ("url", "text")}

        if ctx.doc_type == "writer":
            return self._insert_writer(ctx, url, text, **extra)
        return self._insert_calc(ctx, url, text, **extra)

    def _insert_writer(self, ctx, url, text, **kwargs):
        """Insert hyperlink in Writer via HyperLinkURL on a text range."""
        doc = ctx.doc
        doc_svc = ctx.services.document

        try:
            doc_text = doc.getText()
            locator = kwargs.get("locator")
            paragraph_index = kwargs.get("paragraph_index")

            if locator is not None and paragraph_index is None:
                resolved = doc_svc.resolve_locator(doc, locator)
                paragraph_index = resolved.get("para_index")

            if paragraph_index is not None:
                target, _ = doc_svc.find_paragraph_element(doc, paragraph_index)
                if target is None:
                    return {"status": "error", "message": "Paragraph not found."}
                cursor = doc_text.createTextCursorByRange(target.getEnd())
            else:
                cursor = doc_text.createTextCursor()
                cursor.gotoEnd(False)

            # Insert display text then apply hyperlink properties
            doc_text.insertString(cursor, text, False)
            # Move cursor back over the inserted text
            cursor.goLeft(len(text), True)
            cursor.setPropertyValue("HyperLinkURL", url)
            cursor.setPropertyValue("HyperLinkName", text)
            cursor.setPropertyValue("HyperLinkTarget", "")

            return {"status": "ok", "url": url, "text": text}
        except Exception as e:
            log.exception("insert_hyperlink writer failed")
            return {"status": "error", "error": str(e)}

    def _insert_calc(self, ctx, url, text, **kwargs):
        """Set hyperlink on a Calc cell."""
        doc = ctx.doc
        cell_ref = kwargs.get("cell", "A1")
        sheet_name = kwargs.get("sheet_name")

        try:
            if sheet_name:
                sheets = doc.getSheets()
                sheet = sheets.getByName(sheet_name)
            else:
                sheet = doc.getCurrentController().getActiveSheet()

            cell = sheet.getCellRangeByName(cell_ref)

            # Set display text
            cell.setString(text)

            # Insert URL field into cell
            cell_text = cell.getText()
            cursor = cell_text.createTextCursor()
            cursor.gotoStart(False)
            cursor.gotoEnd(True)

            field = doc.createInstance("com.sun.star.text.TextField.URL")
            field.setPropertyValue("URL", url)
            field.setPropertyValue("Representation", text)
            cell_text.insertTextContent(cursor, field, True)

            return {"status": "ok", "cell": cell_ref, "url": url, "text": text}
        except Exception as e:
            return {"status": "error", "error": str(e)}
