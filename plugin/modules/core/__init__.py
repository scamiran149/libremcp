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
        bus = services.events
        bus.subscribe("tool:completed", self._on_tool_completed)

    def _on_tool_completed(self, name=None, caller=None, result=None,
                           is_mutation=False, doc=None, **_kw):
        """Auto-scroll to mutation location when follow_activity is on."""
        if not is_mutation or caller != "mcp" or doc is None:
            return
        if not self._cfg.get("follow_activity", True):
            return
        if result is None or result.get("status") == "error":
            return
        # Extract paragraph index from result
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
