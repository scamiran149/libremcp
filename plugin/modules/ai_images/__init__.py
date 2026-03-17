# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""AI Images module — AI image generation provider registry."""

import logging

from plugin.framework.module_base import ModuleBase

log = logging.getLogger("nelson.ai_images")


def _check_indexing_ready(services):
    """Return error message if indexing can't run, or None if OK.

    The pipeline is multi-pass: Forge (CLIP) and Ollama (LLM) are
    independent.  We only require that at least one backend is available
    AND at least one gallery has AI indexing enabled.
    """
    gallery_svc = services.get("images")
    if not gallery_svc:
        return "Images service not available."

    # Check at least one gallery wants indexing
    has_gallery = False
    for inst in gallery_svc.list_instances():
        gp = inst.provider
        if hasattr(gp, "wants_ai_index") and gp.wants_ai_index():
            has_gallery = True
            break
    if not has_gallery:
        return ("No gallery has AI indexing enabled.\n"
                "Enable 'AI Auto-Index' and 'Allow Adding Images' on a folder\n"
                "in Options > Image Folders.")

    # Check at least one backend is reachable (Forge OR Ollama)
    has_backend = False
    ai_images_svc = services.get("ai_images")
    if ai_images_svc:
        for inst in ai_images_svc.list_instances():
            p = inst.provider
            if hasattr(p, "supports_interrogate") and p.supports_interrogate():
                ok, _ = p.check()
                if ok:
                    has_backend = True
                    break

    ai_text_svc = services.get("ai")
    if ai_text_svc:
        try:
            ok, _ = ai_text_svc.check()
            if ok:
                has_backend = True
        except Exception:
            pass

    if not has_backend:
        return ("No AI backend available.\n"
                "Start Forge (for CLIP pass) or Ollama (for LLM passes).")

    return None


class AiImagesModule(ModuleBase):

    def __init__(self):
        self._services = None

    def initialize(self, services):
        from plugin.modules.ai_images.service import ImageService

        self._services = services
        svc = ImageService()
        services.register(svc)

        cfg = services.config.proxy_for(self.name)
        default_id = cfg.get("default_instance") or ""
        if default_id:
            svc.set_active(default_id)

    def on_action(self, action):
        from plugin.modules.ai_images.indexer import (
            is_running, start_indexing, stop_indexing)

        if action in ("ai_index_pass1", "ai_index_pass2"):
            if is_running():
                stop_indexing()
                return
            if not self._services:
                return
            # Launch directly — the pipeline skips passes whose
            # backend is not available.  No blocking check on main thread.
            passes = (1,) if action == "ai_index_pass1" else (2, 3)
            start_indexing(self._services, passes=passes)
        else:
            super().on_action(action)

    def get_menu_text(self, action):
        from plugin.modules.ai_images.indexer import running_passes

        rp = running_passes()
        if action == "ai_index_pass1":
            if 1 in rp:
                return "Stop Indexing (Pass 1)"
            return "Pass 1 — Image AI (CLIP)"
        if action == "ai_index_pass2":
            if 2 in rp or 3 in rp:
                return "Stop Indexing (Pass 2)"
            return "Pass 2 — Text AI (LLM)"
        return super().get_menu_text(action)
