# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Folder document gallery sub-module — registers folder instances."""

import json
import logging

from plugin.framework.module_base import ModuleBase

log = logging.getLogger("nelson.documents.folder")


def get_instance_label(item):
    """Label function for list_detail — shows name + document count."""
    import os
    name = item.get("name") or "?"
    path = item.get("path") or ""
    if not path or not os.path.isdir(path):
        return "%s (no folder)" % name
    try:
        from plugin.modules.documents_folder.indexer import FolderIndex
        idx = FolderIndex(path)
        count = idx.count()
        return "%s (%d documents)" % (name, count)
    except Exception:
        return name


def _show_statusbar(text, duration=5.0):
    """Show a message in the LibreOffice status bar for a few seconds."""
    try:
        from plugin.framework.uno_context import get_ctx
        ctx = get_ctx()
        if not ctx:
            return
        desktop = ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", ctx)
        frame = desktop.getCurrentFrame()
        if frame is None:
            return
        sb = frame.createStatusIndicator()
        sb.start(text, 100)
        sb.setValue(100)

        import threading

        def _clear():
            from plugin.framework.main_thread import post_to_main_thread
            post_to_main_thread(sb.end)

        threading.Timer(duration, _clear).start()
    except Exception:
        log.debug("Could not show statusbar message: %s", text)


def on_rescan():
    """Callback for the Rescan Folders button in Options."""
    from plugin.main import get_services
    services = get_services()
    if not services:
        log.warning("on_rescan: services not available")
        return

    svc = services.get("documents")
    if svc is None:
        log.warning("on_rescan: documents service not available")
        return

    inserted = 0
    updated = 0
    deleted = 0
    for inst in svc.list_instances():
        if inst.module_name != "documents.folder":
            continue
        try:
            result = inst.provider.rescan()
            if result:
                inserted += result.get("inserted", 0)
                updated += result.get("updated", 0)
                deleted += result.get("deleted", 0)
            log.info("on_rescan: rescanned %s", inst.name)
        except Exception:
            log.exception("on_rescan: failed for %s", inst.name)

    msg = "Rescan: %d new, %d updated, %d deleted" % (
        inserted, updated, deleted)
    log.info("on_rescan: %s", msg)

    import threading

    def _deferred():
        from plugin.framework.main_thread import post_to_main_thread
        post_to_main_thread(lambda: _show_statusbar(msg))

    threading.Timer(1.0, _deferred).start()


def on_reset_db():
    """Callback for the Reset Database button in Options."""
    from plugin.main import get_services
    services = get_services()
    if not services:
        log.warning("on_reset_db: services not available")
        return

    svc = services.get("documents")
    if svc is None:
        log.warning("on_reset_db: documents service not available")
        return

    count = 0
    for inst in svc.list_instances():
        if inst.module_name != "documents.folder":
            continue
        try:
            inst.provider.reset_db()
            count += 1
            log.info("on_reset_db: reset %s", inst.name)
        except Exception:
            log.exception("on_reset_db: failed for %s", inst.name)

    msg = "Database reset: %d provider(s) cleared" % count

    import threading

    def _deferred():
        from plugin.framework.main_thread import post_to_main_thread
        post_to_main_thread(lambda: _show_statusbar(msg))

    threading.Timer(1.0, _deferred).start()


class DocumentsFolderModule(ModuleBase):

    def initialize(self, services):
        self._svc = services.documents
        self._services = services
        self._sync_instances(services)

    def start(self, services):
        bus = services.events
        bus.subscribe("config:changed", self._on_config_changed)

    def _on_config_changed(self, key=None, changes=None, **_kw):
        if key == "documents.folder.instances":
            self._sync_instances(self._services)
            return
        if changes:
            for diff in changes:
                if diff.get("key") == "documents.folder.instances":
                    self._sync_instances(self._services)
                    return

    def _sync_instances(self, services):
        from plugin.modules.documents.service import DocumentGalleryInstance

        svc = self._svc
        cfg = services.config.proxy_for(self.name)
        raw = cfg.get("instances") or "[]"
        try:
            items = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            items = []
        if not isinstance(items, list):
            items = []

        desired = {}
        for item in items:
            name = item.get("name") or "default"
            instance_id = "folder:%s" % name
            desired[instance_id] = item

        current_ids = [iid for iid, inst in svc._instances.items()
                       if inst.module_name == "documents.folder"]
        for iid in current_ids:
            if iid not in desired:
                svc.unregister_instance(iid)
                log.info("Document folder instance removed: %s", iid)

        for instance_id, item in desired.items():
            name = item.get("name") or "default"
            if instance_id not in current_ids:
                svc.register_instance(instance_id, DocumentGalleryInstance(
                    name=name,
                    module_name="documents.folder",
                    provider=_LazyProvider(item),
                ))
                log.info("Document folder instance added: %s", instance_id)

    def start_background(self, services):
        """Trigger initial scan for all folder instances if enabled."""
        if not hasattr(self, "_svc"):
            return
        cfg = services.config.proxy_for(self.name)
        if not cfg.get("rescan_on_startup", True):
            log.info("Rescan on startup disabled, skipping")
            return
        for inst in self._svc.list_instances():
            if inst.module_name == "documents.folder":
                try:
                    inst.provider.rescan()
                except Exception as e:
                    log.warning("Initial rescan failed for %s: %s",
                                inst.name, e)


class _LazyProvider:
    """Deferred folder provider — avoids import at startup."""

    def __init__(self, config_dict):
        self._config = config_dict
        self._real = None

    def _ensure(self):
        if self._real is None:
            from plugin.modules.documents_folder.provider import (
                FolderDocumentProvider)
            self._real = FolderDocumentProvider(self._config)
        return self._real

    def list_items(self, path="", offset=0, limit=50, doc_type=None):
        return self._ensure().list_items(
            path=path, offset=offset, limit=limit, doc_type=doc_type)

    def search(self, query, limit=20, doc_type=None):
        return self._ensure().search(query, limit=limit, doc_type=doc_type)

    def get_item(self, doc_id):
        return self._ensure().get_item(doc_id)

    def is_writable(self):
        return self._ensure().is_writable()

    def update_metadata(self, doc_id, metadata):
        return self._ensure().update_metadata(doc_id, metadata)

    def reset_db(self):
        return self._ensure().reset_db()

    def rescan(self, force=False):
        return self._ensure().rescan(force=force)
