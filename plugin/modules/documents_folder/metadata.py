# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Document metadata read/write — ODF and OOXML, pure stdlib.

Reads and writes document properties from zip archives without
opening the document in LibreOffice.
"""

import os
import logging
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET

log = logging.getLogger("nelson.documents.folder")

# Namespaces — ODF
_DC = "http://purl.org/dc/elements/1.1/"
_META = "urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"

# Namespaces — OOXML
_CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_EP = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
_VT = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
_DCTERMS = "http://purl.org/dc/terms/"

# Extension -> doc_type mapping
_EXT_DOC_TYPE = {
    "odt": "writer", "doc": "writer", "docx": "writer",
    "rtf": "writer", "txt": "writer", "html": "writer", "htm": "writer",
    "ods": "calc", "xls": "calc", "xlsx": "calc", "csv": "calc",
    "odp": "impress", "ppt": "impress", "pptx": "impress",
    "odg": "draw",
    "pdf": "other",
}

# Extension -> MIME type mapping
_EXT_MIME = {
    "odt": "application/vnd.oasis.opendocument.text",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "odp": "application/vnd.oasis.opendocument.presentation",
    "odg": "application/vnd.oasis.opendocument.graphics",
    "docx": "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument"
            ".presentationml.presentation",
    "doc": "application/msword",
    "xls": "application/vnd.ms-excel",
    "ppt": "application/vnd.ms-powerpoint",
    "pdf": "application/pdf",
    "rtf": "application/rtf",
    "txt": "text/plain",
    "csv": "text/csv",
    "html": "text/html",
    "htm": "text/html",
}


def detect_doc_type(ext):
    """Map file extension to nelson doc_type string."""
    return _EXT_DOC_TYPE.get(ext.lower().lstrip("."), "other")


def ext_to_mime(ext):
    """Map document extension to MIME type."""
    return _EXT_MIME.get(ext.lower().lstrip("."), "application/octet-stream")


def read_document_metadata(file_path):
    """Extract metadata from document properties.

    Supports ODF (meta.xml) and OOXML (docProps/core.xml + app.xml).
    Returns dict with optional keys:
        title, description, subject, keywords (list), creator,
        page_count, word_count, character_count, paragraph_count,
        image_count, table_count.
    """
    ext = os.path.splitext(file_path)[1].lower().lstrip(".")

    if ext in ("odt", "ods", "odp", "odg"):
        return _read_odf_metadata(file_path)
    if ext in ("docx", "xlsx", "pptx"):
        return _read_ooxml_metadata(file_path)
    return {}


def _read_odf_metadata(file_path):
    """Read metadata from ODF meta.xml."""
    meta = {}
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            if "meta.xml" not in zf.namelist():
                return meta
            data = zf.read("meta.xml")
        root = ET.fromstring(data)

        # dc:title
        el = root.find(".//{%s}title" % _DC)
        if el is not None and el.text:
            meta["title"] = el.text.strip()

        # dc:description (= "Comments" in LO File > Properties)
        el = root.find(".//{%s}description" % _DC)
        if el is not None and el.text:
            meta["description"] = el.text.strip()

        # dc:subject
        el = root.find(".//{%s}subject" % _DC)
        if el is not None and el.text:
            meta["subject"] = el.text.strip()

        # dc:creator
        el = root.find(".//{%s}creator" % _DC)
        if el is not None and el.text:
            meta["creator"] = el.text.strip()

        # meta:keyword (one per element)
        keywords = []
        for el in root.findall(".//{%s}keyword" % _META):
            if el.text and el.text.strip():
                keywords.append(el.text.strip())
        if keywords:
            meta["keywords"] = keywords

        # meta:document-statistic attributes
        stat_el = root.find(".//{%s}document-statistic" % _META)
        if stat_el is not None:
            _STAT_MAP = {
                "{%s}page-count" % _META: "page_count",
                "{%s}word-count" % _META: "word_count",
                "{%s}character-count" % _META: "character_count",
                "{%s}paragraph-count" % _META: "paragraph_count",
                "{%s}image-count" % _META: "image_count",
                "{%s}table-count" % _META: "table_count",
            }
            for attr, key in _STAT_MAP.items():
                val = stat_el.get(attr)
                if val is not None:
                    try:
                        meta[key] = int(val)
                    except (ValueError, TypeError):
                        pass

    except Exception:
        log.debug("Failed to read ODF metadata from %s", file_path,
                  exc_info=True)
    return meta


def _read_ooxml_metadata(file_path):
    """Read metadata from OOXML docProps/core.xml + docProps/app.xml."""
    meta = {}
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            names = zf.namelist()

            # -- core.xml --
            if "docProps/core.xml" in names:
                root = ET.fromstring(zf.read("docProps/core.xml"))

                el = root.find("{%s}title" % _DC)
                if el is not None and el.text:
                    meta["title"] = el.text.strip()

                el = root.find("{%s}description" % _DC)
                if el is not None and el.text:
                    meta["description"] = el.text.strip()

                el = root.find("{%s}subject" % _DC)
                if el is not None and el.text:
                    meta["subject"] = el.text.strip()

                el = root.find("{%s}creator" % _DC)
                if el is not None and el.text:
                    meta["creator"] = el.text.strip()

                el = root.find("{%s}keywords" % _CP)
                if el is not None and el.text:
                    kw = [k.strip() for k in el.text.split(",") if k.strip()]
                    if kw:
                        meta["keywords"] = kw

            # -- app.xml (document statistics) --
            if "docProps/app.xml" in names:
                root = ET.fromstring(zf.read("docProps/app.xml"))

                _APP_MAP = {
                    "Pages": "page_count",
                    "Words": "word_count",
                    "Characters": "character_count",
                    "Paragraphs": "paragraph_count",
                    "Slides": "page_count",  # pptx
                }
                for tag, key in _APP_MAP.items():
                    el = root.find("{%s}%s" % (_EP, tag))
                    if el is not None and el.text:
                        try:
                            meta[key] = int(el.text)
                        except (ValueError, TypeError):
                            pass

    except Exception:
        log.debug("Failed to read OOXML metadata from %s", file_path,
                  exc_info=True)
    return meta


# ── Writing metadata ─────────────────────────────────────────────────

# Writable formats
_ODF_FORMATS = {"odt", "ods", "odp", "odg"}
_OOXML_FORMATS = {"docx", "xlsx", "pptx"}


def can_write_metadata(file_path):
    """Check if metadata can be written to this file format."""
    ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    return ext in _ODF_FORMATS or ext in _OOXML_FORMATS


def write_document_metadata(file_path, metadata):
    """Write metadata into document properties.

    Supports ODF (meta.xml) and OOXML (docProps/core.xml).
    Merges with existing metadata — only supplied keys are updated.

    Args:
        file_path: Path to the document file.
        metadata: dict with optional keys: title, description, subject,
                  keywords (list of strings).

    Raises:
        ValueError: If the format is not supported.
        OSError: If the file cannot be written.
    """
    ext = os.path.splitext(file_path)[1].lower().lstrip(".")

    if ext in _ODF_FORMATS:
        _write_odf_metadata(file_path, metadata)
    elif ext in _OOXML_FORMATS:
        _write_ooxml_metadata(file_path, metadata)
    else:
        raise ValueError(
            "Metadata writing not supported for .%s files" % ext)


def _rewrite_zip(src_path, replacements):
    """Rewrite a zip file, replacing or adding specific entries.

    Args:
        src_path: Path to the zip file.
        replacements: dict of {entry_name: new_bytes_content}.
                      Existing entries are replaced; new entries are added.
    """
    fd, tmp_path = tempfile.mkstemp(
        suffix=os.path.splitext(src_path)[1],
        dir=os.path.dirname(src_path),
    )
    os.close(fd)
    try:
        written = set()
        with zipfile.ZipFile(src_path, "r") as zin:
            with zipfile.ZipFile(tmp_path, "w",
                                 compression=zin.compression) as zout:
                for item in zin.infolist():
                    if item.filename in replacements:
                        zout.writestr(item, replacements[item.filename])
                        written.add(item.filename)
                    else:
                        zout.writestr(item, zin.read(item.filename))
                # Add new entries that didn't exist in the original
                for name, content in replacements.items():
                    if name not in written:
                        zout.writestr(name, content)
        # Atomic replace
        shutil.move(tmp_path, src_path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def _write_odf_metadata(file_path, metadata):
    """Update metadata in ODF meta.xml."""
    # Register namespaces to avoid ns0: prefixes
    ET.register_namespace("office", _OFFICE)
    ET.register_namespace("meta", _META)
    ET.register_namespace("dc", _DC)

    with zipfile.ZipFile(file_path, "r") as zf:
        if "meta.xml" not in zf.namelist():
            raise ValueError("No meta.xml found in %s" % file_path)
        data = zf.read("meta.xml")

    root = ET.fromstring(data)

    # Find or create office:meta container
    meta_el = root.find(".//{%s}meta" % _OFFICE)
    if meta_el is None:
        raise ValueError("No office:meta element in meta.xml")

    # dc:title
    if "title" in metadata:
        el = meta_el.find("{%s}title" % _DC)
        if el is None:
            el = ET.SubElement(meta_el, "{%s}title" % _DC)
        el.text = metadata["title"]

    # dc:description
    if "description" in metadata:
        el = meta_el.find("{%s}description" % _DC)
        if el is None:
            el = ET.SubElement(meta_el, "{%s}description" % _DC)
        el.text = metadata["description"]

    # dc:subject
    if "subject" in metadata:
        el = meta_el.find("{%s}subject" % _DC)
        if el is None:
            el = ET.SubElement(meta_el, "{%s}subject" % _DC)
        el.text = metadata["subject"]

    # meta:keyword — replace all
    if "keywords" in metadata:
        for old in meta_el.findall("{%s}keyword" % _META):
            meta_el.remove(old)
        for kw in metadata["keywords"]:
            el = ET.SubElement(meta_el, "{%s}keyword" % _META)
            el.text = kw

    new_xml = ET.tostring(root, encoding="unicode", xml_declaration=True)
    _rewrite_zip(file_path, {"meta.xml": new_xml.encode("utf-8")})


def _write_ooxml_metadata(file_path, metadata):
    """Update metadata in OOXML docProps/core.xml."""
    ET.register_namespace("cp", _CP)
    ET.register_namespace("dc", _DC)
    ET.register_namespace("dcterms", _DCTERMS)

    with zipfile.ZipFile(file_path, "r") as zf:
        names = zf.namelist()
        if "docProps/core.xml" in names:
            data = zf.read("docProps/core.xml")
            root = ET.fromstring(data)
        else:
            # Create a minimal core.xml
            root = ET.fromstring(
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<cp:coreProperties xmlns:cp="%s" xmlns:dc="%s" '
                'xmlns:dcterms="%s"/>' % (_CP, _DC, _DCTERMS)
            )

    if "title" in metadata:
        el = root.find("{%s}title" % _DC)
        if el is None:
            el = ET.SubElement(root, "{%s}title" % _DC)
        el.text = metadata["title"]

    if "description" in metadata:
        el = root.find("{%s}description" % _DC)
        if el is None:
            el = ET.SubElement(root, "{%s}description" % _DC)
        el.text = metadata["description"]

    if "subject" in metadata:
        el = root.find("{%s}subject" % _DC)
        if el is None:
            el = ET.SubElement(root, "{%s}subject" % _DC)
        el.text = metadata["subject"]

    if "keywords" in metadata:
        el = root.find("{%s}keywords" % _CP)
        if el is None:
            el = ET.SubElement(root, "{%s}keywords" % _CP)
        el.text = ", ".join(metadata["keywords"])

    new_xml = ET.tostring(root, encoding="unicode", xml_declaration=True)
    _rewrite_zip(file_path, {
        "docProps/core.xml": new_xml.encode("utf-8"),
    })
