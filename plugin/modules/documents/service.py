# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""DocumentGalleryService — document gallery provider registry.

Manages document gallery provider instances and routes search/list
requests to the active provider.
"""

import logging

from plugin.framework.service_base import ServiceBase

log = logging.getLogger("nelson.documents")


class DocumentGalleryInstance:
    """One document gallery provider instance with metadata."""

    __slots__ = ("name", "module_name", "provider")

    def __init__(self, name, module_name, provider):
        self.name = name
        self.module_name = module_name
        self.provider = provider


class DocumentGalleryService(ServiceBase):
    """Document gallery provider registry.

    Instance ID convention:
      - ``"folder:My Docs"``
    """

    name = "documents"

    def __init__(self):
        self._instances = {}       # instance_id -> DocumentGalleryInstance
        self._active_id = ""       # volatile active selection

    # -- Instance registration -------------------------------------------------

    def register_instance(self, instance_id, instance):
        """Register a document gallery provider instance."""
        self._instances[instance_id] = instance
        log.info("Document gallery provider registered: %s", instance_id)

    def unregister_instance(self, instance_id):
        """Remove a document gallery provider instance."""
        self._instances.pop(instance_id, None)

    # -- Instance lookup -------------------------------------------------------

    def get_instance(self, instance_id=None):
        """Get a DocumentGalleryInstance by ID or active selection.

        Returns DocumentGalleryInstance or None.
        """
        if instance_id:
            return self._instances.get(instance_id)

        # Active selection
        if self._active_id:
            inst = self._instances.get(self._active_id)
            if inst:
                return inst

        # Fallback: first registered instance
        if self._instances:
            return next(iter(self._instances.values()))

        return None

    def get_provider(self, instance_id=None):
        """Get the provider object. Raises RuntimeError if none available."""
        inst = self.get_instance(instance_id=instance_id)
        if inst is None:
            available = ", ".join(self._instances.keys()) or "(none)"
            raise RuntimeError(
                "No document gallery provider available. Registered: %s"
                % available
            )
        return inst.provider

    def list_instances(self):
        """List all registered instances."""
        return list(self._instances.values())

    # -- Delegating methods ----------------------------------------------------

    def search(self, query, instance_id=None, limit=20, doc_type=None):
        """Search documents in a provider."""
        provider = self.get_provider(instance_id=instance_id)
        return provider.search(query, limit=limit, doc_type=doc_type)

    def list_items(self, instance_id=None, path="", offset=0, limit=50,
                   doc_type=None):
        """List documents from a provider."""
        provider = self.get_provider(instance_id=instance_id)
        return provider.list_items(path=path, offset=offset, limit=limit,
                                   doc_type=doc_type)

    def get_item(self, doc_id, instance_id=None):
        """Get metadata for a specific document."""
        provider = self.get_provider(instance_id=instance_id)
        return provider.get_item(doc_id)

    def update_metadata(self, doc_id, metadata, instance_id=None):
        """Update metadata for a document via its provider."""
        provider = self.get_provider(instance_id=instance_id)
        return provider.update_metadata(doc_id, metadata)

    # -- Active selection ------------------------------------------------------

    def set_active(self, instance_id):
        """Set the active provider instance."""
        self._active_id = instance_id
        log.info("Active document gallery provider: %s",
                 instance_id or "(auto)")

    def get_active(self):
        """Return the active instance ID."""
        return self._active_id


def get_instance_options(services):
    """Options provider for the documents.default_instance config select."""
    svc = services.get("documents")
    if not svc:
        return []
    options = [{"value": "", "label": "(auto)"}]
    for iid, inst in svc._instances.items():
        label = "[%s] %s" % (inst.module_name.split(".")[-1], inst.name)
        options.append({"value": iid, "label": label})
    return options
