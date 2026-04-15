# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Writer outline / heading navigation tools.

NOTE: GetDocumentOutline and GetHeadingContent are deprecated.
Use get_document_tree and get_heading_children from writer_nav instead.
These tools remain for backward compatibility and fall back to the core
document service's simpler heading tree when writer_nav is not available.
"""

import logging

from plugin.framework.tool_base import ToolBase

log = logging.getLogger("libremcp.writer")


class GetDocumentOutline(ToolBase):
    """Return the heading tree (outline) of a Writer document.

    .. deprecated::
        Use ``get_document_tree`` with ``content_strategy="heading_only"``
        and ``depth=0`` for equivalent or richer output.
    """

    name = "get_document_outline"
    description = (
        "Returns the document outline (headings hierarchy). "
        "Prefer get_document_tree(content_strategy='heading_only', depth=0) "
        "for richer output with bookmarks and para indices."
    )
    parameters = {
        "type": "object",
        "properties": {
            "max_depth": {
                "type": "integer",
                "description": "Maximum heading depth to return (default: all).",
            },
        },
        "required": [],
    }
    doc_types = ["writer"]
    tier = "core"

    def execute(self, ctx, **kwargs):
        tree_svc = ctx.services.get("writer_tree")
        if tree_svc is not None:
            tree = tree_svc.build_heading_tree(ctx.doc)
        else:
            tree_svc = ctx.services.document
            tree = tree_svc.build_heading_tree(ctx.doc)
        max_depth = kwargs.get("max_depth")
        if max_depth is not None:
            tree = [_prune_tree(node, max_depth) for node in tree]
        return {"status": "ok", "outline": tree}


class GetHeadingContent(ToolBase):
    """Return content under a heading identified by its path.

    .. deprecated::
        Use ``get_heading_children`` with ``locator="heading:N.N"`` and
        ``content_strategy="full"`` for equivalent or richer output.
    """

    name = "get_heading_content"
    intent = "navigate"
    description = (
        "Returns content under a heading identified by its path "
        "(e.g. '1.2' for the second child of the first heading). "
        "Prefer get_heading_children(locator='heading:1.2', content_strategy='full') "
        "for richer output with bookmark support."
    )
    parameters = {
        "type": "object",
        "properties": {
            "heading_path": {
                "type": "string",
                "description": "Dot-separated heading path, e.g. '1', '2.3'.",
            },
            "max_paragraphs": {
                "type": "integer",
                "description": "Maximum paragraphs to return (default: 50).",
            },
        },
        "required": ["heading_path"],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        heading_path = kwargs["heading_path"]
        max_paragraphs = kwargs.get("max_paragraphs", 50)

        tree_svc = ctx.services.get("writer_tree")
        if tree_svc is not None:
            tree = tree_svc.build_heading_tree(ctx.doc)
            # Convert rich tree format to simple format for path walking.
            simple_tree = _simplify_tree(tree)
        else:
            doc_svc = ctx.services.document
            simple_tree = doc_svc.build_heading_tree(ctx.doc)

        parts = _parse_path(heading_path)
        if parts is None:
            return {
                "status": "error",
                "message": "Invalid heading path: %s" % heading_path,
            }

        node = _walk_tree(simple_tree, parts)
        if node is None:
            return {
                "status": "error",
                "message": "Heading '%s' not found." % heading_path,
            }

        doc_svc = ctx.services.document
        para_ranges = doc_svc.get_paragraph_ranges(ctx.doc)
        heading_level = node.get("level", 1)
        heading_title = node.get("title", "")

        start_idx = _find_heading_para_index(para_ranges, heading_title, heading_level)
        if start_idx is None:
            return {
                "status": "error",
                "message": "Could not locate heading in paragraphs.",
            }

        paragraphs = []
        for i in range(start_idx + 1, len(para_ranges)):
            if len(paragraphs) >= max_paragraphs:
                break
            p = para_ranges[i]
            if not hasattr(p, "getString"):
                continue
            try:
                level = p.getPropertyValue("OutlineLevel")
            except Exception:
                level = 0
            if level > 0 and level <= heading_level:
                break
            paragraphs.append(p.getString())

        return {
            "status": "ok",
            "heading_path": heading_path,
            "heading_title": heading_title,
            "paragraphs": paragraphs,
            "sub_headings": node.get("children", []),
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _prune_tree(node, max_depth, current_depth=1):
    """Remove children deeper than *max_depth*."""
    pruned = dict(node)
    if current_depth >= max_depth:
        pruned["children"] = []
    else:
        pruned["children"] = [
            _prune_tree(c, max_depth, current_depth + 1)
            for c in node.get("children", [])
        ]
    return pruned


def _parse_path(path_str):
    """Parse ``'1.2.3'`` into ``[1, 2, 3]`` (1-based). Returns None on error."""
    try:
        parts = [int(p) for p in path_str.strip().split(".")]
        if all(p >= 1 for p in parts):
            return parts
    except (ValueError, AttributeError):
        pass
    return None


def _walk_tree(tree, parts):
    """Walk a nested heading tree by 1-based indices.

    *tree* is a list of top-level heading dicts, each with a
    ``'children'`` list.
    """
    nodes = tree
    node = None
    for idx in parts:
        if idx < 1 or idx > len(nodes):
            return None
        node = nodes[idx - 1]
        nodes = node.get("children", [])
    return node


def _find_heading_para_index(para_ranges, title, level):
    """Scan paragraph ranges for a heading matching *title* and *level*."""
    for i, p in enumerate(para_ranges):
        if not hasattr(p, "getString"):
            continue
        try:
            p_level = p.getPropertyValue("OutlineLevel")
        except Exception:
            continue
        if p_level == level and p.getString().strip() == title:
            return i
    return None


def _simplify_tree(rich_tree):
    """Convert rich tree from TreeService to simple {level, title, children}."""
    result = []
    for node in rich_tree:
        simple = {
            "level": node.get("level", 1),
            "title": node.get("text", ""),
            "children": _simplify_tree(node.get("children", [])),
        }
        result.append(simple)
    return result
