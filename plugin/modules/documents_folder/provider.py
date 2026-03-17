# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Folder document provider — scans local folders, indexes with SQLite+FTS5."""

import logging
import os

from plugin.modules.documents.provider_base import DocumentGalleryProvider
from plugin.modules.documents_folder.indexer import DocumentIndex
from plugin.modules.documents_folder.metadata import (
    read_document_metadata, write_document_metadata, can_write_metadata,
)

log = logging.getLogger("nelson.documents.folder")

# Default document extensions
_DEFAULT_EXTENSIONS = (
    "odt,docx,pdf,ods,xlsx,odp,pptx,txt,csv,rtf,html,doc,xls,ppt,odg"
)


class FolderDocumentProvider(DocumentGalleryProvider):
    """Document gallery backed by a local folder with SQLite+FTS5 index."""

    def __init__(self, config_dict):
        self._config = config_dict
        self._root = os.path.abspath(config_dict.get("path", ""))
        self._recursive = config_dict.get("recursive", True)
        self._read_properties = config_dict.get("read_properties", True)
        self._writable = config_dict.get("writable", False)
        ext_str = config_dict.get("extensions", _DEFAULT_EXTENSIONS)
        self._extensions = {
            e.strip().lower() for e in ext_str.split(",") if e.strip()
        }
        self.name = config_dict.get("name", "folder")
        self.root_path = self._root  # exposed for default_save_dir
        self._index = DocumentIndex(self._root)

    def list_items(self, path="", offset=0, limit=50, doc_type=None):
        return self._index.list_items(
            path_prefix=path, offset=offset, limit=limit, doc_type=doc_type)

    def search(self, query, limit=20, doc_type=None):
        return self._index.search(query, limit=limit, doc_type=doc_type)

    def get_item(self, doc_id):
        return self._index.get_item(doc_id)

    def is_writable(self):
        return self._writable

    def update_metadata(self, doc_id, metadata):
        """Update document properties and re-index.

        Args:
            doc_id: Relative path within the gallery.
            metadata: dict with optional keys: title, description, subject,
                      keywords (list of strings).

        Returns:
            Updated document metadata dict.
        """
        if not self._writable:
            raise NotImplementedError(
                "This document gallery provider is read-only. "
                "Enable 'Allow Editing Metadata' in Options.")

        abs_path = os.path.join(self._root, doc_id)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError("Document not found: %s" % doc_id)

        if not can_write_metadata(abs_path):
            raise ValueError(
                "Metadata writing not supported for this file format. "
                "Supported: ODF (.odt, .ods, .odp, .odg) and "
                "OOXML (.docx, .xlsx, .pptx).")

        write_document_metadata(abs_path, metadata)

        # Re-index this file to pick up changes
        reader = read_document_metadata if self._read_properties else _noop
        self._index.scan(
            extensions=self._extensions,
            recursive=self._recursive,
            metadata_reader=reader,
            force=True,
        )
        return self._index.get_item(doc_id)

    def reset_db(self):
        """Delete the index database so it is rebuilt on next rescan."""
        self._index.reset()

    def rescan(self, force=False):
        if not os.path.isdir(self._root):
            log.warning("Document folder does not exist: %s", self._root)
            return {"inserted": 0, "updated": 0, "deleted": 0}

        reader = read_document_metadata if self._read_properties else _noop
        return self._index.scan(
            extensions=self._extensions,
            recursive=self._recursive,
            metadata_reader=reader,
            force=force,
        )


def _noop(path):
    """No-op metadata reader when read_properties is disabled."""
    return {}
