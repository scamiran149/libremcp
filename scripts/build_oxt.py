# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

#!/usr/bin/env python3
"""Build an .oxt LibreOffice extension from the plugin/ directory.

Two-step process:
  1. Assemble all files into build/bundle/ with final archive paths
  2. Zip build/bundle/ into the .oxt

This lets you tweak files in build/bundle/ and re-zip with --repack.

Usage:
    python3 scripts/build_oxt.py                    # full build
    python3 scripts/build_oxt.py --repack           # re-zip bundle only
    python3 scripts/build_oxt.py --modules core mcp
"""

import argparse
import os
import shutil
import sys
import zipfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files/dirs always included from extension/
ALWAYS_INCLUDE_EXTENSION = [
    "extension/description.xml",
    "extension/META-INF/",
    "extension/Jobs.xcu",
    "extension/ProtocolHandler.xcu",
    "extension/registration/",
    "extension/registry/",
    "extension/dialogs/",
    "extension/assets/",
]

# Files/dirs always included from plugin/
ALWAYS_INCLUDE_PLUGIN = [
    "plugin/__init__.py",
    "plugin/main.py",
    "plugin/options_handler.py",
    "plugin/version.py",
    "plugin/_manifest.py",
    "plugin/_layout.py",
    "plugin/plugin.yaml",
    "plugin/framework/",
    "plugin/lib/",
]


# Auto-discover all top-level module directories
def _discover_modules(base_dir):
    """Return sorted list of top-level module directory names."""
    modules_dir = os.path.join(base_dir, "plugin", "modules")
    if not os.path.isdir(modules_dir):
        return []
    return sorted(
        d
        for d in os.listdir(modules_dir)
        if os.path.isdir(os.path.join(modules_dir, d)) and not d.startswith(("_", "."))
    )


EXCLUDE_PATTERNS = (
    ".git",
    ".DS_Store",
    "__pycache__",
    ".pyc",
    ".pyo",
    "module.yaml",
    "tests/",
    "test_",
)

# Generated files (XCS/XCU, XDL dialogs, OptionsDialog.xcu)
GENERATED_INCLUDES = [
    "build/generated/registry/",
    "build/generated/dialogs/",
    "build/generated/assets/",
    "build/generated/OptionsDialog.xcu",
    "build/generated/Addons.xcu",
    "build/generated/Accelerators.xcu",
    "build/help/html/",
]

BUNDLE_DIR = "build/bundle"


def should_exclude(path):
    for pat in EXCLUDE_PATTERNS:
        if pat in path:
            return True
    return False


def collect_files(base_dir, include_paths):
    """Collect all files from a list of paths relative to base_dir."""
    files = []
    for inc in include_paths:
        full = os.path.join(base_dir, inc)
        if os.path.isfile(full):
            if not should_exclude(inc):
                files.append(inc)
        elif os.path.isdir(full):
            for root, dirs, filenames in os.walk(full):
                dirs[:] = [d for d in dirs if not should_exclude(d)]
                for fn in filenames:
                    filepath = os.path.join(root, fn)
                    relpath = os.path.relpath(filepath, base_dir)
                    if not should_exclude(relpath):
                        files.append(relpath)
        else:
            print("  WARNING: %s not found, skipping" % inc, file=sys.stderr)
    return sorted(set(files))


def remap_path(f):
    """Convert a project-relative path to its .oxt archive path."""
    f = f.replace(os.sep, "/")
    if f.startswith("extension/"):
        return f[len("extension/") :]
    if f.startswith("build/generated/"):
        return f[len("build/generated/") :]
    if f.startswith("build/help/html/"):
        return "help/" + f[len("build/help/html/") :]
    return f


def assemble_bundle(base_dir, modules):
    """Copy all files into build/bundle/ with final archive paths."""
    bundle_path = os.path.join(base_dir, BUNDLE_DIR)

    # Clean previous bundle
    if os.path.exists(bundle_path):
        shutil.rmtree(bundle_path)

    include = list(ALWAYS_INCLUDE_EXTENSION)
    include.extend(ALWAYS_INCLUDE_PLUGIN)

    for mod in modules:
        mod_dir = "plugin/modules/%s/" % mod
        mod_path = os.path.join(base_dir, mod_dir)
        if os.path.isdir(mod_path):
            include.append(mod_dir)
        else:
            print(
                "  WARNING: module '%s' not found at %s" % (mod, mod_dir),
                file=sys.stderr,
            )

    include.extend(GENERATED_INCLUDES)
    files = collect_files(base_dir, include)

    count = 0
    for f in files:
        src = os.path.join(base_dir, f)
        arcname = remap_path(f)
        dst = os.path.join(bundle_path, arcname)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        count += 1

    # Copy pysqlite3 (Windows) into plugin/lib/ inside the bundle
    pysqlite3_dir = os.path.join(base_dir, "build", "sqlite3_win", "pysqlite3")
    if os.path.isdir(pysqlite3_dir):
        dst_dir = os.path.join(bundle_path, "plugin", "lib", "pysqlite3")
        if os.path.exists(dst_dir):
            shutil.rmtree(dst_dir)
        shutil.copytree(pysqlite3_dir, dst_dir)
        pysqlite3_count = sum(1 for _, _, fs in os.walk(dst_dir) for _ in fs)
        count += pysqlite3_count
        print("Bundled pysqlite3 (%d files) into plugin/lib/" % pysqlite3_count)

    # Copy bundled sqlite3.dll into plugin/lib/sqlite3/ inside the bundle
    sqlite3_src = os.path.join(base_dir, "plugin", "lib", "sqlite3", "sqlite3.dll")
    if os.path.isfile(sqlite3_src):
        dst_dir = os.path.join(bundle_path, "plugin", "lib", "sqlite3")
        os.makedirs(dst_dir, exist_ok=True)
        shutil.copy2(sqlite3_src, os.path.join(dst_dir, "sqlite3.dll"))
        count += 1
        print(
            "Bundled sqlite3.dll (%.1f MB) into plugin/lib/sqlite3/"
            % (os.path.getsize(sqlite3_src) / 1024 / 1024)
        )

    # Copy vendored pip packages into plugin/lib/ inside the bundle
    vendor_dir = os.path.join(base_dir, "vendor")
    if os.path.isdir(vendor_dir):
        vendor_count = 0
        for entry in sorted(os.listdir(vendor_dir)):
            if entry.endswith(".dist-info") or entry.startswith(("_", ".")):
                continue
            src_path = os.path.join(vendor_dir, entry)
            dst_path = os.path.join(bundle_path, "plugin", "lib", entry)
            if os.path.isdir(src_path):
                if os.path.exists(dst_path):
                    shutil.rmtree(dst_path)
                shutil.copytree(src_path, dst_path)
            elif os.path.isfile(src_path):
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)
            vendor_count += 1
        if vendor_count:
            print("Vendored %d packages into plugin/lib/" % vendor_count)

    # XHP help: disabled — LO extensions don't support .xhp help natively
    # Help is served via /api/tools HTML endpoint instead.
    # The generated Markdown in build/help/ can be used as documentation.

    # Generate build ID (timestamp + short hash of assembled files)
    import hashlib
    import datetime

    h = hashlib.md5()
    for root, dirs, files in os.walk(bundle_path):
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            h.update(os.path.relpath(fp, bundle_path).encode())
            h.update(str(os.path.getsize(fp)).encode())
    build_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    build_hash = h.hexdigest()[:8]
    build_id_path = os.path.join(bundle_path, "plugin", "_build_id.py")
    with open(build_id_path, "w") as f:
        f.write('BUILD_ID = "%s-%s"\n' % (build_ts, build_hash))
    count += 1

    print(
        "Assembled %d files in %s (build %s-%s)"
        % (count, BUNDLE_DIR, build_ts, build_hash)
    )
    return count


def zip_bundle(base_dir, output):
    """Zip build/bundle/ into the .oxt."""
    bundle_path = os.path.join(base_dir, BUNDLE_DIR)
    if not os.path.isdir(bundle_path):
        print(
            "ERROR: %s not found. Run without --repack first." % BUNDLE_DIR,
            file=sys.stderr,
        )
        return 1

    output_path = os.path.join(base_dir, output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if os.path.exists(output_path):
        os.remove(output_path)

    count = 0
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, filenames in os.walk(bundle_path):
            dirs[:] = [d for d in dirs if not should_exclude(d)]
            for fn in filenames:
                filepath = os.path.join(root, fn)
                arcname = os.path.relpath(filepath, bundle_path)
                if not should_exclude(arcname):
                    zf.write(filepath, arcname)
                    count += 1

    print("Created %s with %d files" % (output, count))
    return 0


def _is_up_to_date(project_root, output_path):
    """Check if output is newer than all source files."""
    oxt_mtime = os.path.getmtime(output_path)
    source_dirs = ["plugin", "extension", "build/generated", "vendor"]
    for d in source_dirs:
        full = os.path.join(project_root, d)
        if not os.path.isdir(full):
            continue
        for dirpath, _, filenames in os.walk(full):
            for fn in filenames:
                if fn.endswith((".pyc", ".oxt")) or "__pycache__" in dirpath:
                    continue
                fp = os.path.join(dirpath, fn)
                if os.path.getmtime(fp) > oxt_mtime:
                    return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Build LibreMCP .oxt extension")
    parser.add_argument(
        "--modules",
        nargs="+",
        default=None,
        help="Modules to include (default: auto-discover all)",
    )
    parser.add_argument(
        "--output",
        default="build/libremcp.oxt",
        help="Output file (default: build/libremcp.oxt)",
    )
    parser.add_argument(
        "--repack",
        action="store_true",
        help="Only re-zip build/bundle/ (skip assembly)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Skip build if .oxt is newer than all sources",
    )
    args = parser.parse_args()

    if args.check and os.path.isfile(args.output):
        if _is_up_to_date(PROJECT_ROOT, args.output):
            print("%s is up to date." % args.output)
            return 0

    if not args.repack:
        modules = args.modules or _discover_modules(PROJECT_ROOT)
        assemble_bundle(PROJECT_ROOT, modules)

    return zip_bundle(PROJECT_ROOT, args.output)


if __name__ == "__main__":
    sys.exit(main())
