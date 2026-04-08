# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Terminal detection and command building — shared by launcher and deps."""

import logging
import os
import shlex
import shutil
import subprocess
import sys

log = logging.getLogger("nelson.terminal")

# Windows: open subprocess in a new console window
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
_CREATION_FLAGS = CREATE_NEW_CONSOLE if sys.platform == "win32" else 0


def find_terminal(configured=None):
    """Return terminal command (str).

    If *configured* is set, use it directly.  Otherwise auto-detect.
    """
    if configured:
        return configured

    # Check $TERMINAL env var
    env_term = os.environ.get("TERMINAL")
    if env_term and shutil.which(env_term):
        return env_term

    if sys.platform == "win32":
        if shutil.which("wt"):
            return "wt"
        return "conhost"

    if sys.platform == "darwin":
        return "open"  # handled specially in build_terminal_cmd

    for term in [
        "gnome-terminal",
        "konsole",
        "xfce4-terminal",
        "mate-terminal",
        "tilix",
        "alacritty",
        "kitty",
        "xterm",
    ]:
        if shutil.which(term):
            return term

    return "xterm"


def build_terminal_cmd(terminal, cli_cmd):
    """Build full command list: terminal wrapper + inner command."""
    if sys.platform == "darwin" and terminal == "open":
        shell_cmd = " ".join(shlex.quote(c) for c in cli_cmd)
        return ["osascript", "-e",
                'tell app "Terminal" to do script "%s"'
                % shell_cmd.replace('"', '\\"')]

    base = os.path.basename(terminal)

    if base in ("wt", "wt.exe"):
        return [terminal, "new-tab", "--", *cli_cmd]

    if base in ("conhost", "conhost.exe"):
        return [terminal, *cli_cmd]

    if base in ("gnome-terminal", "mate-terminal"):
        return [terminal, "--", *cli_cmd]

    if base == "tilix":
        return [terminal, "-e", " ".join(shlex.quote(c) for c in cli_cmd)]

    if base == "konsole":
        return [terminal, "-e", *cli_cmd]

    if base == "xfce4-terminal":
        return [terminal, "-e", " ".join(shlex.quote(c) for c in cli_cmd)]

    if base in ("alacritty", "kitty"):
        return [terminal, "-e", *cli_cmd]

    # Generic fallback (xterm and others)
    return [terminal, "-e", *cli_cmd]


def launch_in_terminal(script_path, args=None, cwd=None, pause=False):
    """Launch a script in a visible terminal window.

    On Windows: PowerShell in a new console.
    On Linux/macOS: auto-detected terminal emulator.

    If *pause* is True, the terminal waits for Enter after the script finishes.
    Scripts that handle their own pause should set pause=False (the default).
    """
    args = args or []

    if sys.platform == "win32":
        if pause:
            # Wrap with -Command to add a Read-Host after the script
            escaped = script_path.replace("'", "''")
            ps_args = " ".join("'%s'" % a.replace("'", "''") for a in args)
            invoke = "& '%s' %s" % (escaped, ps_args) if args else "& '%s'" % escaped
            full_cmd = [
                "powershell", "-ExecutionPolicy", "Bypass", "-Command",
                "%s; Write-Host; Write-Host 'Done. Press Enter to close.'; Read-Host"
                % invoke,
            ]
        else:
            full_cmd = [
                "powershell", "-ExecutionPolicy", "Bypass",
                "-File", script_path,
            ] + args
    else:
        term = find_terminal()
        shell_parts = ["bash", shlex.quote(script_path)] + [shlex.quote(a) for a in args]
        shell_str = " ".join(shell_parts)
        if pause:
            shell_str += "; echo; echo 'Done. Press Enter to close.'; read"
        cli_cmd = ["bash", "-c", shell_str]
        full_cmd = build_terminal_cmd(term, cli_cmd)

    log.info("Launching in terminal: %s", " ".join(str(c) for c in full_cmd))
    subprocess.Popen(
        full_cmd,
        start_new_session=True,
        creationflags=_CREATION_FLAGS,
        cwd=cwd,
    )


def run_headless(script_path, args=None, timeout=120):
    """Run a script without a terminal window.  Returns True on success."""
    args = args or []

    if sys.platform == "win32":
        cmd = ["powershell", "-ExecutionPolicy", "Bypass",
               "-File", script_path] + args
        creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        cmd = ["bash", script_path] + args
        creation = 0

    log.info("Running headless: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=creation,
        )
        if result.stdout.strip():
            log.info("Script stdout: %s", result.stdout.strip())
        if result.returncode != 0:
            log.warning("Script exited %d: %s",
                        result.returncode, result.stderr.strip())
            return False
        return True
    except subprocess.TimeoutExpired:
        log.warning("Script timed out after %ds", timeout)
        return False
    except Exception:
        log.warning("Headless script failed", exc_info=True)
        return False
