# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""AI gallery indexer — multi-pass image indexation pipeline.

Pass 1 (CLIP):     Image → literal description + raw tags via CLIP interrogate
Pass 2 (Universe): Folder → thematic universe via LLM (one call per folder)
Pass 3 (Tags):     Image + universe → rich thematic tags via LLM

Runs as a sequential job. User controls when each backend is available:
- Forge for pass 1 (CLIP)
- Ollama for passes 2-3 (LLM text)
"""

import base64
import json
import logging
import os
import re
import subprocess
import struct
import threading

log = logging.getLogger("nelson.ai_images.indexer")

# Windows: hide subprocess console window
_CREATION_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Max dimension for the thumbnail sent to CLIP
_THUMB_MAX = 512

# Extensions treated as context files in folders
_CONTEXT_EXTENSIONS = (".txt", ".md")

# Max chars of raw context before summarizing
_CONTEXT_MAX_RAW = 2000

# Singleton state
_stop_event = threading.Event()
_running = False
_running_passes = ()  # which passes are currently running
_current_job = None
_status_indicator = None


def is_running():
    return _running


def running_passes():
    """Return tuple of pass numbers currently running, or ()."""
    return _running_passes if _running else ()


def start_indexing(services, passes=(1, 2, 3)):
    global _current_job
    _stop_event.clear()
    job = services.jobs.enqueue(
        _run_indexer,
        kind="ai_gallery_index",
        params={"status": "queued", "passes": list(passes),
                "pass": 0, "total": 0, "indexed": 0},
        services=services,
        passes=passes,
    )
    _current_job = job
    return job


def stop_indexing():
    _stop_event.set()


# ---------------------------------------------------------------------------
# Progress helpers
# ---------------------------------------------------------------------------

def _update_progress(status, pass_num=0, total=0, indexed=0, current=""):
    job = _current_job
    if job is None:
        return
    job.params.update({
        "status": status, "pass": pass_num,
        "total": total, "indexed": indexed,
    })
    if current:
        job.params["current"] = current


def _statusbar_start(text, total):
    global _status_indicator
    try:
        from plugin.framework.uno_context import get_ctx
        from plugin.framework.main_thread import post_to_main_thread
        ctx = get_ctx()
        if not ctx:
            return
        desktop = ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", ctx)
        frame = desktop.getCurrentFrame()
        if frame is None:
            return
        sb = frame.createStatusIndicator()
        _status_indicator = sb
        post_to_main_thread(lambda: sb.start(text, total))
    except Exception:
        pass


def _statusbar_update(value, text=None):
    sb = _status_indicator
    if sb is None:
        return
    try:
        from plugin.framework.main_thread import post_to_main_thread
        if text:
            post_to_main_thread(lambda: (sb.setText(text), sb.setValue(value)))
        else:
            post_to_main_thread(lambda: sb.setValue(value))
    except Exception:
        pass


def _statusbar_end(text=None):
    global _status_indicator
    sb = _status_indicator
    _status_indicator = None
    if sb is None:
        return
    try:
        from plugin.framework.main_thread import post_to_main_thread
        if text:
            post_to_main_thread(lambda: (sb.setText(text), sb.setValue(100)))
            threading.Timer(5.0, lambda: post_to_main_thread(sb.end)).start()
        else:
            post_to_main_thread(sb.end)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _run_indexer(services, passes=(1, 2, 3)):
    global _running, _running_passes
    _running = True
    _running_passes = tuple(passes)
    try:
        return _run_pipeline(services, passes=passes)
    finally:
        _running = False
        _running_passes = ()
        _update_progress("done")


def _run_pipeline(services, passes=(1, 2, 3)):
    """Run requested passes across all galleries."""
    gallery_svc = services.get("images")
    ai_images_svc = services.get("ai_images")
    ai_text_svc = services.get("ai")

    if not gallery_svc:
        return {"error": "No images service"}

    # Configured language override (empty = auto-detect)
    forced_lang = ""
    try:
        forced_lang = services.config.proxy_for("ai_images").get(
            "index_language") or ""
    except Exception:
        pass

    results = {"pass1": 0, "pass2": 0, "pass3": 0, "errors": 0}

    for gallery_inst in gallery_svc.list_instances():
        if _stop_event.is_set():
            break

        gp = gallery_inst.provider
        if not (hasattr(gp, "wants_ai_index") and gp.wants_ai_index()):
            continue

        # Rescan to pick up new files
        if hasattr(gp, "rescan"):
            try:
                gp.rescan()
            except Exception:
                log.exception("Rescan failed for '%s'", gallery_inst.name)

        index = gp._index if hasattr(gp, "_index") else None
        if index is None:
            continue
        root = gp._root if hasattr(gp, "_root") else ""

        # Pass 1: CLIP
        if 1 in passes and ai_images_svc and not _stop_event.is_set():
            clip_provider = _find_clip_provider(ai_images_svc, services)
            if clip_provider:
                n, e = _run_pass1_clip(
                    services, gallery_inst, index, clip_provider)
                results["pass1"] += n
                results["errors"] += e

        # Pass 2: Folder universe via LLM
        if 2 in passes and ai_text_svc and not _stop_event.is_set():
            ok, _ = ai_text_svc.check()
            if ok:
                n, e = _run_pass2_universe(
                    services, gallery_inst, index, ai_text_svc, root,
                    forced_lang=forced_lang)
                results["pass2"] += n
                results["errors"] += e

        # Pass 3: Per-image tags via LLM
        if 3 in passes and ai_text_svc and not _stop_event.is_set():
            ok, _ = ai_text_svc.check()
            if ok:
                n, e = _run_pass3_tags(
                    services, gallery_inst, index, ai_text_svc, gp,
                    forced_lang=forced_lang)
                results["pass3"] += n
                results["errors"] += e

    msg = ("AI indexing done: %d CLIP, %d universes, %d tagged, %d errors"
           % (results["pass1"], results["pass2"],
              results["pass3"], results["errors"]))
    log.info(msg)
    _statusbar_end(msg)
    return results


# ---------------------------------------------------------------------------
# Pass 1: CLIP interrogation
# ---------------------------------------------------------------------------

def _find_clip_provider(ai_images_svc, services):
    """Find a provider that supports interrogation (CLIP)."""
    cfg = services.config.proxy_for("ai_images")
    interrogate_id = cfg.get("interrogate_instance") or ""
    if interrogate_id:
        inst = ai_images_svc.get_instance(interrogate_id)
        if inst:
            return inst.provider
    for inst in ai_images_svc.list_instances():
        p = inst.provider
        if hasattr(p, "supports_interrogate") and p.supports_interrogate():
            return p
    return None


def _run_pass1_clip(services, gallery_inst, index, clip_provider):
    """CLIP pass: describe unprocessed images (stage < 1)."""
    images = index.list_at_stage(1, limit=500)
    if not images:
        return (0, 0)

    total = len(images)
    log.info("Pass 1 (CLIP): %d images in '%s'", total, gallery_inst.name)
    _update_progress("pass1_clip", pass_num=1, total=total, indexed=0)
    _statusbar_start("Pass 1 (CLIP) '%s': 0/%d" % (gallery_inst.name, total),
                     total)

    endpoint = ""
    try:
        pcfg = clip_provider._config if hasattr(clip_provider, "_config") else {}
        endpoint = pcfg.get("endpoint", "")
    except Exception:
        pass

    indexed = 0
    errors = 0
    gp = gallery_inst.provider

    for i, item in enumerate(images):
        if _stop_event.is_set():
            break

        image_id = item.get("id", "")
        file_path = item.get("file_path", "")
        if not file_path:
            continue

        try:
            image_b64 = _resize_and_encode(file_path)
            if not image_b64:
                continue

            if endpoint:
                services.jobs.acquire_endpoint(endpoint)
            try:
                caption, err = clip_provider.interrogate(image_b64)
            finally:
                if endpoint:
                    services.jobs.release_endpoint(endpoint)

            if err:
                log.warning("CLIP failed for %s: %s", image_id, err)
                errors += 1
                continue

            if caption:
                meta = _parse_caption(caption)
                gp.update_metadata(image_id, meta)
                index.update_stage(image_id, 1)
                indexed += 1
                _update_progress("pass1_clip", pass_num=1, total=total,
                                 indexed=indexed, current=image_id)
                _statusbar_update(i + 1, "CLIP: %d/%d" % (i + 1, total))

        except Exception:
            log.exception("Pass 1 error: %s", image_id)
            errors += 1

    return (indexed, errors)


# ---------------------------------------------------------------------------
# Pass 2: Folder universe via LLM
# ---------------------------------------------------------------------------

def _read_folder_context(folder_path, ai_svc=None):
    """Read all .txt/.md files in a folder as context.

    Concatenates all text files (sorted by name). If total content
    exceeds _CONTEXT_MAX_RAW chars and an LLM is available, summarizes
    it. Otherwise truncates.

    Returns context string or None.
    """
    parts = []
    try:
        for fn in sorted(os.listdir(folder_path)):
            _, ext = os.path.splitext(fn)
            if ext.lower() not in _CONTEXT_EXTENSIONS:
                continue
            fp = os.path.join(folder_path, fn)
            if not os.path.isfile(fp):
                continue
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(5000).strip()
                if content:
                    parts.append("--- %s ---\n%s" % (fn, content))
            except Exception:
                pass
    except OSError:
        pass

    if not parts:
        return None

    merged = "\n\n".join(parts)
    if len(merged) <= _CONTEXT_MAX_RAW:
        return merged

    # Try to summarize via LLM
    if ai_svc:
        try:
            ok, _ = ai_svc.check()
            if ok:
                result = ai_svc.complete([
                    {"role": "system",
                     "content": "Summarize this text in 3-5 sentences. "
                                "Keep key facts: names, dates, places, topics."},
                    {"role": "user", "content": merged[:4000]},
                ], temperature=0.2, max_tokens=300)
                summary = result.get("content", "")
                if summary and not result.get("error"):
                    return summary
        except Exception:
            pass

    # Fallback: truncate
    return merged[:_CONTEXT_MAX_RAW]


def _run_pass2_universe(services, gallery_inst, index, ai_svc, root,
                        forced_lang=""):
    """LLM pass: determine the thematic universe of each folder.

    Processes top-down (root first, then subfolders) so that
    the parent universe can be passed as context to children.
    """
    folders = index.get_folders()
    # Include root folder (empty prefix)
    if "" not in folders:
        folders.insert(0, "")
    # Sort shortest first = top-down (root → subfolders)
    folders.sort(key=len)

    # Store computed universes keyed by folder prefix
    universes = {}  # folder_prefix -> {"summary": ..., "themes": ...}

    indexed = 0
    errors = 0

    for folder in folders:
        if _stop_event.is_set():
            break

        # Get images in this folder at stage 1 (CLIP done, universe not done)
        images = index.list_by_folder(folder, below_stage=2, limit=200)
        if not images:
            continue

        # Full path gives more context
        folder_abs = os.path.join(root, folder) if folder else root
        folder_name = folder_abs.replace("\\", "/")
        log.info("Pass 2 (universe): folder '%s' (%d images)",
                 folder_name, len(images))
        _update_progress("pass2_universe", pass_num=2,
                         total=len(folders), indexed=indexed,
                         current=folder_name)

        # Find parent universe (longest matching prefix)
        parent_universe = None
        for prev_folder in sorted(universes.keys(), key=len, reverse=True):
            if folder.startswith(prev_folder) and folder != prev_folder:
                parent_universe = universes[prev_folder]
                break

        # Build context for the LLM
        descriptions = []
        filenames = []
        for img in images:
            desc = img.get("description", "")
            if desc:
                descriptions.append(desc)
            filenames.append(img.get("name", ""))

        # Read all context text files in folder
        context_text = _read_folder_context(folder_abs, ai_svc=ai_svc)

        lang = forced_lang or _detect_lang(folder_name, filenames)
        prompt = _build_universe_prompt(
            folder_name, descriptions, filenames, context_text, lang,
            parent_universe=parent_universe)

        try:
            from plugin.framework.template_manager import render_file
            system = render_file("ai_images", "universe_system.txt")
            result = ai_svc.complete([
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ], temperature=0.3, max_tokens=1000)

            content = result.get("content", "")
            if result.get("error"):
                log.warning("Pass 2 LLM error for '%s': %s",
                            folder_name, result["error"])
                errors += 1
                continue

            universe = _parse_universe_response(content)
            if universe:
                # Store universe for child folders
                universes[folder] = universe

                # Flatten categorized themes into tag list
                theme_tags = _flatten_themes(universe.get("themes", {}))
                universe_text = universe.get("summary", "")

                for img in images:
                    existing_kw = img.get("keywords", [])
                    if isinstance(existing_kw, str):
                        existing_kw = [k.strip() for k in existing_kw.split(",")
                                       if k.strip()]
                    merged = list(dict.fromkeys(existing_kw + theme_tags))
                    gallery_inst.provider.update_metadata(
                        img["id"],
                        {"keywords": merged})
                    index.update_stage(img["id"], 2)

                indexed += 1
                log.info("Pass 2: '%s' → %s (%d tags)",
                         folder_name, universe_text[:60],
                         len(theme_tags))

        except Exception:
            log.exception("Pass 2 error for folder '%s'", folder_name)
            errors += 1

    return (indexed, errors)


def _detect_lang(folder_name, filenames):
    """Guess user language from folder/file names. Default: English."""
    text = (folder_name + " " + " ".join(filenames[:10])).lower()
    # Simple heuristic based on common words/accents
    if re.search(r'[éèêëàâùûôîïç]|vacances|sortie|fête|école', text):
        return "French"
    if re.search(r'[ñ]|vacaciones|viaje|familia', text):
        return "Spanish"
    if re.search(r'[äöüß]|urlaub|reise|familie', text):
        return "German"
    if re.search(r'[ãõ]|viagem|família|férias', text):
        return "Portuguese"
    if re.search(r'viaggio|famiglia|vacanza', text):
        return "Italian"
    if re.search(r'[\u4e00-\u9fff]', text):
        return "Chinese"
    if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text):
        return "Japanese"
    return "English"


def _flatten_themes(themes):
    """Flatten categorized themes dict into a flat tag list.

    Accepts both:
    - dict: {"context": [...], "activities": [...], ...}
    - list: ["tag1", "tag2"] (backward compat)
    """
    if isinstance(themes, list):
        return themes
    if isinstance(themes, dict):
        tags = []
        for category_tags in themes.values():
            if isinstance(category_tags, list):
                tags.extend(category_tags)
            elif isinstance(category_tags, str):
                tags.append(category_tags)
        return tags
    return []


def _format_universe_for_prompt(universe):
    """Format a universe dict for injection into a child prompt."""
    if not universe:
        return ""
    summary = universe.get("summary", "")
    themes = universe.get("themes", {})
    tags = _flatten_themes(themes)
    parts = []
    if summary:
        parts.append("Summary: %s" % summary)
    if tags:
        parts.append("Tags: %s" % ", ".join(tags))
    return "\n".join(parts)


def _build_universe_prompt(folder_name, descriptions, filenames, context, lang,
                           parent_universe=None):
    """Build the prompt for folder universe detection."""
    from plugin.framework.template_manager import render_file

    context_section = ""
    if context:
        context_section = 'Context files:\n"""\n%s\n"""' % context

    parent_universe_section = ""
    if parent_universe:
        parent_universe_section = (
            'Parent folder universe:\n"""\n%s\n"""'
            % _format_universe_for_prompt(parent_universe)
        )

    desc_lines = "\n".join("- %s" % d for d in descriptions[:20])

    return render_file(
        "ai_images", "universe_user.txt",
        folder_name=folder_name,
        context_section=context_section,
        parent_universe_section=parent_universe_section,
        file_count=str(len(filenames)),
        filenames=", ".join(filenames[:30]),
        descriptions=desc_lines,
        lang=lang,
    )


def _parse_universe_response(text):
    """Parse LLM JSON response for universe."""
    text = text.strip()
    # Strip markdown code block if present
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    log.warning("Could not parse universe response: %s", text[:200])
    return None


# ---------------------------------------------------------------------------
# Pass 3: Per-image tags via LLM
# ---------------------------------------------------------------------------

def _run_pass3_tags(services, gallery_inst, index, ai_svc, gp,
                    forced_lang=""):
    """LLM pass: enrich each image with contextual tags."""
    images = index.list_at_stage(3, limit=500)
    # Only process images that have passed stage 2
    images = [img for img in images if img.get("index_stage", 0) >= 2]
    if not images:
        return (0, 0)

    total = len(images)
    log.info("Pass 3 (tags): %d images in '%s'", total, gallery_inst.name)
    _update_progress("pass3_tags", pass_num=3, total=total, indexed=0)
    _statusbar_start("Pass 3 (tags) '%s': 0/%d" % (gallery_inst.name, total),
                     total)

    indexed = 0
    errors = 0

    for i, img in enumerate(images):
        if _stop_event.is_set():
            break

        image_id = img.get("id", "")
        description = img.get("description", "")
        keywords = img.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        filename = img.get("name", "")
        file_path = img.get("file_path", "")

        # Read per-image context file
        img_context = None
        if file_path:
            txt_path = file_path + ".txt"
            if os.path.isfile(txt_path):
                try:
                    with open(txt_path, "r", encoding="utf-8",
                              errors="replace") as f:
                        img_context = f.read(1000).strip()
                except Exception:
                    pass

        prompt = _build_tags_prompt(
            filename, description, keywords, img_context,
            forced_lang=forced_lang)

        try:
            from plugin.framework.template_manager import render_file
            system = render_file("ai_images", "tags_system.txt")
            result = ai_svc.complete([
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ], temperature=0.3, max_tokens=800)

            content = result.get("content", "")
            if result.get("error"):
                log.warning("Pass 3 LLM error for '%s': %s",
                            image_id, result["error"])
                errors += 1
                continue

            new_tags, remove_tags = _parse_tags_response(content)
            if new_tags or remove_tags:
                cleaned = [k for k in keywords
                           if k.lower() not in
                           {r.lower() for r in remove_tags}]
                merged = list(dict.fromkeys(cleaned + new_tags))
                meta = {"keywords": merged}
                # Apply clean_description if provided
                parsed = _parse_universe_response(content)
                if parsed and parsed.get("clean_description"):
                    meta["description"] = parsed["clean_description"]
                gp.update_metadata(image_id, meta)
                index.update_stage(image_id, 3)
                indexed += 1
                _update_progress("pass3_tags", pass_num=3, total=total,
                                 indexed=indexed, current=image_id)
                _statusbar_update(i + 1, "Tags: %d/%d" % (i + 1, total))

        except Exception:
            log.exception("Pass 3 error: %s", image_id)
            errors += 1

    return (indexed, errors)


def _build_tags_prompt(filename, description, existing_tags, img_context,
                       forced_lang=""):
    """Build prompt for per-image tag enrichment."""
    from plugin.framework.template_manager import render_file

    context_section = ""
    if img_context:
        context_section = 'User context:\n"""\n%s\n"""' % img_context

    lang = forced_lang or "English"

    return render_file(
        "ai_images", "tags_user.txt",
        filename=filename,
        description=description or "",
        existing_tags=", ".join(existing_tags) if existing_tags else "(none)",
        context_section=context_section,
        lang=lang,
    )


def _parse_tags_response(text):
    """Parse LLM JSON response for tags. Returns (new_tags, remove_tags)."""
    parsed = _parse_universe_response(text)  # reuse JSON parser
    if not parsed:
        return ([], [])
    new_tags = parsed.get("tags", [])
    remove_tags = parsed.get("remove", [])
    return (new_tags, remove_tags)


# ---------------------------------------------------------------------------
# CLIP helpers (unchanged)
# ---------------------------------------------------------------------------

def _parse_caption(caption):
    """Convert a CLIP caption into description + keywords."""
    parts = [p.strip() for p in caption.split(",") if p.strip()]
    if not parts:
        return {"description": caption}
    description = parts[0]
    keywords = [k for k in parts[1:] if not _is_noise_tag(k)]
    return {"description": description, "keywords": keywords}


_NOISE_PATTERNS = (
    "a stock photo", "stock photo", "a jigsaw puzzle", "shutterstock",
    "an illustration", "a digital rendering", "a digital painting",
    "a screenshot", "a picture",
)


def _is_noise_tag(tag):
    t = tag.strip().lower()
    for pat in _NOISE_PATTERNS:
        if t == pat or t.startswith(pat):
            return True
    words = tag.strip().split()
    if 2 <= len(words) <= 3 and all(w[0].isupper() for w in words):
        _common = {"The", "A", "An", "In", "On", "At", "By", "Of", "And",
                    "With", "From", "For", "Red", "Blue", "Green", "Black",
                    "White", "Dark", "Light", "Big", "Small", "Old", "New",
                    "High", "Low", "Art", "Style"}
        if not any(w in _common for w in words):
            return True
    return False


def _resize_and_encode(file_path):
    """Read an image, resize to thumbnail, return base64."""
    if not os.path.isfile(file_path):
        return None
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    if ext not in ("jpg", "jpeg", "png", "bmp", "webp", "gif"):
        return None
    w, h = _read_dimensions_quick(file_path, ext)
    if 0 < w <= _THUMB_MAX and 0 < h <= _THUMB_MAX:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    resized = _resize_with_magick(file_path, ext)
    if resized:
        return resized
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        if len(data) > 10 * 1024 * 1024:
            return None
        return base64.b64encode(data).decode("ascii")
    except Exception:
        return None


def _resize_with_magick(file_path, ext):
    import shutil
    import tempfile
    magick = shutil.which("magick") or shutil.which("convert")
    if not magick:
        return None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        cmd = [magick, file_path,
               "-resize", "%dx%d>" % (_THUMB_MAX, _THUMB_MAX),
               "-quality", "85", tmp_path]
        subprocess.run(cmd, capture_output=True, timeout=10,
                       creationflags=_CREATION_FLAGS)
        if os.path.isfile(tmp_path) and os.path.getsize(tmp_path) > 0:
            with open(tmp_path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            os.unlink(tmp_path)
            return data
        os.unlink(tmp_path)
    except Exception:
        log.debug("ImageMagick resize failed for %s", file_path, exc_info=True)
        try:
            if os.path.isfile(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass
    return None


def _read_dimensions_quick(file_path, ext):
    try:
        with open(file_path, "rb") as f:
            header = f.read(32)
        if header[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", header[16:24])
        if header[:6] in (b"GIF87a", b"GIF89a"):
            return struct.unpack("<HH", header[6:10])
        if header[:2] == b"\xff\xd8":
            return _read_jpeg_dims(file_path)
    except Exception:
        pass
    return (0, 0)


def _read_jpeg_dims(path):
    try:
        with open(path, "rb") as f:
            f.read(2)
            while True:
                marker = f.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    break
                mtype = marker[1]
                if mtype in (0xC0, 0xC1, 0xC2):
                    f.read(2)
                    data = f.read(5)
                    if len(data) >= 5:
                        h, w = struct.unpack(">HH", data[1:5])
                        return (w, h)
                    break
                elif mtype in (0xD9, 0xDA):
                    break
                else:
                    seg_len = struct.unpack(">H", f.read(2))[0]
                    f.seek(seg_len - 2, 1)
    except Exception:
        pass
    return (0, 0)
