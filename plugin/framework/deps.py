# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Script dependency framework — runtime engine.

Each module declares scripts in its module.yaml.  This module handles:
- Resolving script paths (.ps1 on Windows, .sh on Linux/Mac)
- Evaluating check expressions to skip already-satisfied deps
- Tracking once-only execution state in a JSON file
- Launching scripts in a terminal (manual) or headless (auto)
- Resolving placeholder arguments ({lib_dir}, {config:key}, etc.)

See the plan for the full YAML schema and tag combinations.
"""

import datetime
import json
import logging
import os
import re
import sys

log = logging.getLogger("nelson.deps")

# ── State file (persists across extension reinstalls) ────────────────


def _state_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "nelson")


def _state_path():
    return os.path.join(_state_dir(), "deps_state.json")


def _load_state():
    """Load {module/script: {version, ts}} from JSON file."""
    path = _state_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        log.debug("Failed to read deps state", exc_info=True)
        return {}


def _save_state(state):
    """Persist state dict to JSON file."""
    path = _state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        log.warning("Failed to write deps state", exc_info=True)


def _is_done(module_name, script_name, version):
    """Return True if this version was already successfully run."""
    state = _load_state()
    key = "%s/%s" % (module_name, script_name)
    entry = state.get(key)
    if entry is None:
        return False
    return entry.get("version") == str(version)


def _mark_done(module_name, script_name, version):
    """Record a successful execution in state file."""
    state = _load_state()
    key = "%s/%s" % (module_name, script_name)
    state[key] = {
        "version": str(version),
        "ts": datetime.datetime.now().isoformat(),
    }
    _save_state(state)


def _mark_launched(module_name, script_name):
    """Record a manual launch (button click) in state file."""
    state = _load_state()
    key = "%s/%s" % (module_name, script_name)
    entry = state.get(key, {})
    entry["last_launch"] = datetime.datetime.now().isoformat()
    state[key] = entry
    _save_state(state)


def get_last_launch(module_name, script_name):
    """Return human-readable last launch info, or None if never launched."""
    state = _load_state()
    key = "%s/%s" % (module_name, script_name)
    entry = state.get(key)
    if entry is None:
        return None
    ts = entry.get("last_launch") or entry.get("ts")
    if not ts:
        return None
    try:
        dt = datetime.datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts


# ── Check expression ─────────────────────────────────────────────────


def _run_check(check_expr):
    """Evaluate a check expression.  Returns True if dep is present."""
    if not check_expr:
        return False
    try:
        exec(compile(check_expr, "<dep-check>", "exec"),
             {"__builtins__": __builtins__})
        return True
    except Exception:
        return False


# ── Argument resolution ──────────────────────────────────────────────

_PLACEHOLDER_RE = re.compile(r"\{([^}]+)\}")


def _extension_dir():
    """Return the extension root directory.

    Prefers the UNO PackageInformationProvider path (= the actual installed
    extension inside the LO profile).  Falls back to __file__-relative path
    only when UNO is unavailable (e.g. running outside LO).
    """
    try:
        from plugin.framework.uno_context import get_ctx
        ctx = get_ctx()
        if ctx:
            import uno
            pip = ctx.getValueByName(
                "/singletons/com.sun.star.deployment"
                ".PackageInformationProvider")
            loc = pip.getPackageLocation("org.extension.nelson")
            if loc:
                path = uno.fileUrlToSystemPath(loc)
                if os.path.isdir(path):
                    return path
    except Exception:
        pass
    # Fallback: __file__-relative (dev / outside LO)
    plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.dirname(plugin_dir)


def _extension_lib_dir():
    """Return plugin/lib/ inside the installed extension."""
    return os.path.join(_extension_dir(), "plugin", "lib")


def _resolve_args(args, module_name, services=None):
    """Resolve placeholder strings in args list.

    Supported placeholders:
      {lib_dir}      — plugin/lib/ directory
      {ext_dir}      — extension root
      {platform}     — sys.platform
      {config:key}   — read module config value
    """
    if not args:
        return []

    builtins = {
        "lib_dir": _extension_lib_dir(),
        "ext_dir": _extension_dir(),
        "platform": sys.platform,
    }

    resolved = []
    for arg in args:
        def _replace(m):
            token = m.group(1)
            if token in builtins:
                return builtins[token]
            if token.startswith("config:") and services:
                key = token[len("config:"):]
                try:
                    cfg = services.config.proxy_for(module_name)
                    val = cfg.get(key)
                    return str(val) if val is not None else ""
                except Exception:
                    log.debug("Failed to resolve {%s}", token)
                    return ""
            return m.group(0)  # leave unresolved

        resolved.append(_PLACEHOLDER_RE.sub(_replace, str(arg)))
    return resolved


# ── Script resolution ────────────────────────────────────────────────


def _module_dir(module_name):
    """Return the filesystem directory for a module name.

    Dots in module names map to directory separators
    (e.g. 'ai_images.sdapi' -> 'ai_images_sdapi').
    Uses _extension_dir() to resolve from the installed extension path.
    """
    ext_dir = _extension_dir()
    dir_name = module_name.replace(".", "_")
    return os.path.join(ext_dir, "plugin", "modules", dir_name)


def _find_script(module_name, script_name):
    """Return full path to the platform-appropriate script, or None."""
    scripts_dir = os.path.join(_module_dir(module_name), "scripts")
    if sys.platform == "win32":
        path = os.path.join(scripts_dir, "%s.ps1" % script_name)
    else:
        path = os.path.join(scripts_dir, "%s.sh" % script_name)
    if os.path.isfile(path):
        return path
    return None


# ── Hooks ────────────────────────────────────────────────────────────


def _call_hook(hook_path):
    """Call a module.path:function hook.  Returns the function's return value.

    If the hook raises or is not found, returns None.
    """
    if not hook_path:
        return None
    try:
        import importlib
        module_path, func_name = hook_path.rsplit(":", 1)
        mod = importlib.import_module(module_path)
        func = getattr(mod, func_name)
        return func()
    except Exception:
        log.warning("Hook failed: %s", hook_path, exc_info=True)
        return None


# ── Public API ───────────────────────────────────────────────────────


def check_and_run_auto(module_name, scripts_dict, services=None):
    """Run all auto scripts for a module that need running.

    Called from a module's start_background().
    Scripts with visible: true open a terminal window instead of running headless.
    """
    from plugin.framework.terminal import run_headless, launch_in_terminal

    for script_name, script_def in scripts_dict.items():
        if not script_def.get("auto"):
            continue

        # Platform filter
        platform = script_def.get("platform")
        if platform and sys.platform != platform:
            continue

        # Check expression
        check = script_def.get("check")
        if check and _run_check(check):
            log.debug("Auto script %s/%s: check passed, skipping",
                      module_name, script_name)
            continue

        # Once tracking
        version = str(script_def.get("version", "1"))
        if script_def.get("once") and _is_done(module_name, script_name, version):
            log.debug("Auto script %s/%s v%s: already done, skipping",
                      module_name, script_name, version)
            continue

        # Find and run
        script_path = _find_script(module_name, script_name)
        if not script_path:
            log.warning("Auto script %s/%s: file not found", module_name, script_name)
            continue

        args = _resolve_args(script_def.get("args", []), module_name, services)
        visible = script_def.get("visible", True)
        pause = script_def.get("pause", True)
        log.info("Running auto script: %s/%s (v%s, visible=%s)",
                 module_name, script_name, version, visible)

        if visible:
            launch_in_terminal(script_path, args, pause=pause)
            # Can't track success for visible scripts — mark done optimistically
            ok = True
        else:
            ok = run_headless(script_path, args)
        if ok and script_def.get("once"):
            _mark_done(module_name, script_name, version)
            log.info("Auto script %s/%s v%s: done", module_name, script_name, version)
        elif not ok:
            log.warning("Auto script %s/%s: failed", module_name, script_name)


def run_script(module_name, script_name):
    """Launch a script in a visible terminal.  Button callback entry point."""
    from plugin.framework.terminal import launch_in_terminal

    # Load script def from manifest
    script_def = _get_script_def(module_name, script_name)
    if script_def is None:
        log.warning("Script def not found: %s/%s", module_name, script_name)
        return

    # Platform filter
    platform = script_def.get("platform")
    if platform and sys.platform != platform:
        log.info("Script %s/%s: not for this platform (%s)",
                 module_name, script_name, sys.platform)
        try:
            from plugin.framework.dialogs import msgbox
            from plugin.framework.uno_context import get_ctx
            msgbox(get_ctx(), "Nelson",
                   "This script is for %s only." % platform)
        except Exception:
            pass
        return

    script_path = _find_script(module_name, script_name)
    if not script_path:
        log.warning("Script file not found: %s/%s", module_name, script_name)
        try:
            from plugin.framework.dialogs import msgbox
            from plugin.framework.uno_context import get_ctx
            msgbox(get_ctx(), "Nelson",
                   "Script not found:\n%s/%s" % (module_name, script_name))
        except Exception:
            pass
        return

    # Resolve args (services may not be available from options handler context)
    services = None
    try:
        from plugin.main import get_services
        services = get_services()
    except Exception:
        pass

    # Button hooks
    button = script_def.get("button", {})
    if not isinstance(button, dict):
        button = {}
    before = button.get("before")
    if before:
        result = _call_hook(before)
        if result is False:
            log.info("Script %s/%s: cancelled by before hook", module_name, script_name)
            return

    args = _resolve_args(script_def.get("args", []), module_name, services)
    pause = script_def.get("pause", True)
    _mark_launched(module_name, script_name)
    launch_in_terminal(script_path, args, pause=pause)


def _get_script_def(module_name, script_name):
    """Look up a script definition from the manifest."""
    try:
        from plugin._manifest import MODULES
        for m in MODULES:
            if m["name"] == module_name:
                return m.get("scripts", {}).get(script_name)
    except Exception:
        log.debug("Failed to load manifest for script lookup", exc_info=True)
    return None


# ── Module __getattr__ for button dispatch ───────────────────────────
#
# The manifest generator synthesizes button actions like:
#   action: "plugin.framework.deps:run__core__install_deps"
#
# _ButtonActionListener does rsplit(":", 1) to get the function name,
# then calls getattr(module, name)().  We use __getattr__ to dynamically
# create callables for any "run__<module>__<script>" pattern.


def __getattr__(name):
    if name.startswith("run__"):
        parts = name[len("run__"):].split("__", 1)
        if len(parts) == 2:
            mod_name = parts[0].replace("_dot_", ".")
            script_name = parts[1].replace("_", "-")

            def _runner():
                run_script(mod_name, script_name)
            return _runner
    raise AttributeError(name)
