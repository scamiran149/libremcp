# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Heading tree tools: get_document_tree, get_heading_children."""

from plugin.framework.tool_base import ToolBase


class GetDocumentTree(ToolBase):
    name = "get_document_tree"
    tier = "core"
    intent = "navigate"
    description = (
        "Get the document heading tree with bookmarks and content previews. "
        "ALWAYS call this before editing to get stable _mcp_ bookmarks for headings "
        "(e.g. bookmark:_mcp_a1b2c3d4). These bookmarks survive edits unlike paragraph indices. "
        "Use depth=0 for the complete tree (recommended for AI), depth=1 for top-level only. "
        "Content strategies: heading_only (just headings), first_lines (default, first line per section), "
        "full (all text, can be large)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "content_strategy": {
                "type": "string",
                "enum": ["heading_only", "first_lines", "ai_summary_first", "full"],
                "description": "Content to include: heading_only=just headings, first_lines=preview per section (default), full=all text",
            },
            "depth": {
                "type": "integer",
                "description": "Tree depth: 0=unlimited full tree (recommended), 1=top-level only (default). Use depth=0 for AI navigation.",
            },
        },
        "required": [],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        tree_svc = ctx.services.writer_tree
        result = tree_svc.get_document_tree(
            ctx.doc,
            content_strategy=kwargs.get("content_strategy", "first_lines"),
            depth=kwargs.get("depth", 1),
        )
        return {"status": "ok", **result}


class GetHeadingChildren(ToolBase):
    name = "get_heading_children"
    tier = "core"
    intent = "navigate"
    description = (
        "Drill into a heading's body paragraphs and sub-headings. "
        "Use after get_document_tree to explore specific sections. "
        "Identify the heading by locator: 'bookmark:_mcp_xxx' (from get_document_tree), "
        "'heading_text:Title' (fuzzy match on heading text), or 'paragraph:N'. "
        "Returns paragraphs with text, style, and bookmark for stable reference."
    )
    parameters = {
        "type": "object",
        "properties": {
            "locator": {
                "type": "string",
                "description": "Locator string: 'bookmark:_mcp_xxx', 'heading_text:Title', or 'paragraph:N'",
            },
            "heading_para_index": {
                "type": "integer",
                "description": "Paragraph index of the heading",
            },
            "heading_bookmark": {
                "type": "string",
                "description": "Bookmark name of the heading",
            },
            "content_strategy": {
                "type": "string",
                "enum": ["heading_only", "first_lines", "ai_summary_first", "full"],
                "description": "Content strategy (default: first_lines)",
            },
            "depth": {
                "type": "integer",
                "description": "Max sub-heading depth (default: 1)",
            },
        },
        "required": [],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        tree_svc = ctx.services.writer_tree
        try:
            result = tree_svc.get_heading_children(
                ctx.doc,
                heading_para_index=kwargs.get("heading_para_index"),
                heading_bookmark=kwargs.get("heading_bookmark"),
                locator=kwargs.get("locator"),
                content_strategy=kwargs.get("content_strategy", "first_lines"),
                depth=kwargs.get("depth", 1),
            )
            return {"status": "ok", **result}
        except ValueError as e:
            return {"status": "error", "error": str(e)}
