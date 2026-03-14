# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Document gallery provider ABC — contract for document gallery backends."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class DocumentMeta:
    """Metadata for a single document in a gallery."""

    __slots__ = (
        "id", "name", "title", "description", "keywords",
        "file_path", "file_size", "mime_type", "modified",
        "doc_type", "page_count",
    )

    def __init__(self, **kwargs: Any) -> None:
        for slot in self.__slots__:
            setattr(self, slot, kwargs.get(slot))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict, omitting None values."""
        return {k: getattr(self, k) for k in self.__slots__
                if getattr(self, k) is not None}


class DocumentGalleryProvider(ABC):
    """Interface that document gallery backend modules implement."""

    name: Optional[str] = None

    @abstractmethod
    def list_items(self, path: str = "", offset: int = 0,
                   limit: int = 50,
                   doc_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List documents, optionally filtered by path prefix and doc type.

        Returns:
            Document metadata dicts.
        """

    @abstractmethod
    def search(self, query: str, limit: int = 20,
               doc_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search documents by name, title, description, keywords.

        Returns:
            Document metadata dicts.
        """

    @abstractmethod
    def get_item(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a single document.

        Args:
            doc_id: Provider-specific identifier (typically relative path).

        Returns:
            dict or None.
        """

    def update_metadata(self, doc_id: str,
                        metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Update document metadata (title, description, subject, keywords).

        Args:
            doc_id: Provider-specific identifier.
            metadata: dict with keys to update.

        Returns:
            Updated document metadata dict.

        Raises:
            NotImplementedError: If the provider is read-only.
        """
        raise NotImplementedError(
            "This document gallery provider does not support "
            "metadata editing.")

    def is_writable(self) -> bool:
        """Whether this provider supports metadata updates."""
        return False
