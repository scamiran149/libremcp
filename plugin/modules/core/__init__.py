# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Core module — provides fundamental services."""

import logging

from plugin.framework.module_base import ModuleBase

log = logging.getLogger("nelson.core")


class Module(ModuleBase):

    def initialize(self, services):
        from plugin.modules.core.services.document import DocumentService
        from plugin.modules.core.services.config import ConfigService
        from plugin.modules.core.services.events import EventBusService
        from plugin.modules.core.services.format import FormatService

        services.register(DocumentService())
        services.register(ConfigService())
        services.register(EventBusService())
        services.register(FormatService())

    def start(self, services):
        self._doc_svc = services.document
        self._cfg = services.config.proxy_for("core")
        self._services = services
        bus = services.events
        bus.subscribe("tool:completed", self._on_tool_completed)

    def start_background(self, services):
        self._attach_cursor_tracker()

    def _on_tool_completed(self, name=None, caller=None, result=None,
                           is_mutation=False, doc=None, **_kw):
        """Auto-scroll to mutation location when follow_activity is on."""
        if not is_mutation or caller != "mcp" or doc is None:
            return
        if not self._cfg.get("follow_activity", True):
            return
        if result is None or result.get("status") == "error":
            return

        # Prefer page-based jump (instant) over paragraph-based
        page = result.get("_page") or result.get("page")
        if page and isinstance(page, int):
            try:
                controller = doc.getCurrentController()
                vc = controller.getViewCursor()
                vc.jumpToPage(page)
                log.debug("follow_activity: jumped to page %d", page)
                return
            except Exception:
                pass

        # Fallback to paragraph-based navigation
        pi = result.get("paragraph_index")
        if pi is None:
            pi = result.get("para_index")
        if pi is None:
            return
        try:
            self._doc_svc.goto_paragraph(doc, pi)
            log.debug("follow_activity: scrolled to paragraph %d", pi)
        except Exception:
            log.debug("follow_activity: scroll failed", exc_info=True)

    def _attach_cursor_tracker(self):
        """Attach a lightweight listener to track the current page."""
        try:
            import unohelper
            from com.sun.star.view import XSelectionChangeListener
            from plugin.modules.core.services.document import DocumentCache
            from plugin.framework.main_thread import post_to_main_thread

            doc_svc = self._doc_svc

            class _CursorTracker(unohelper.Base, XSelectionChangeListener):
                """Ultra-light: just reads vc.getPage() on selection change."""

                def selectionChanged(self, event):
                    try:
                        doc = doc_svc.get_active_document()
                        if doc is None:
                            return
                        controller = doc.getCurrentController()
                        vc = controller.getViewCursor()
                        page = vc.getPage()
                        cache = DocumentCache.get(doc)
                        cache.page_map.observe(None, None)  # no-op
                        # Store current page for quick access
                        cache.current_page = page
                    except Exception:
                        pass

                def disposing(self, event):
                    pass

            def _attach():
                doc = doc_svc.get_active_document()
                if doc is None:
                    return
                try:
                    controller = doc.getCurrentController()
                    controller.addSelectionChangeListener(_CursorTracker())
                    log.debug("Cursor tracker attached")
                except Exception:
                    log.debug("Could not attach cursor tracker", exc_info=True)

            post_to_main_thread(_attach)

        except Exception:
            log.debug("_attach_cursor_tracker failed", exc_info=True)
