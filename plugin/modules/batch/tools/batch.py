# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Batch execution tool: execute_batch."""

import logging
import time

from plugin.framework.tool_base import ToolBase
from plugin.modules.batch.batch_vars import (
    resolve_batch_vars,
    extract_step_info,
)

log = logging.getLogger("libremcp.batch")

_LOCATION_KEYS = (
    "paragraph_index",
    "para_index",
    "locator",
    "page",
    "page_number",
)


def _follow_result(ctx, result):
    """Scroll the view to the location implied by a tool result."""
    if not isinstance(result, dict):
        return
    try:
        doc = ctx.doc
        controller = doc.getCurrentController()
        vc = controller.getViewCursor()

        page = result.get("page") or result.get("page_number")
        if page and isinstance(page, int):
            vc.jumpToPage(page)
            return

        para_idx = result.get("paragraph_index")
        if para_idx is None:
            para_idx = result.get("para_index")
        if para_idx is not None and isinstance(para_idx, int):
            text = doc.getText()
            enum = text.createEnumeration()
            idx = 0
            while enum.hasMoreElements():
                para = enum.nextElement()
                if idx == para_idx:
                    vc.gotoStart(False)
                    vc.gotoRange(para.getStart(), False)
                    return
                idx += 1
    except Exception:
        pass


class ExecuteBatch(ToolBase):
    name = "execute_batch"
    description = (
        "Execute multiple tool calls in a single request (up to 50). "
        "Operations run sequentially; cache invalidation is deferred to the end for performance. "
        "Stops on first error by default (set stop_on_error=false to continue). "
        "BATCH VARIABLES for chaining operations: "
        "$last = paragraph_index from previous step, "
        "$last+N/$last-N = offset (e.g. $last+1 means next paragraph), "
        "$last.bookmark = bookmark from previous step, "
        "$step.N = paragraph_index from a specific step, "
        "$step.N.bookmark = bookmark from step N. "
        "Use in string fields as 'paragraph:$last+1' or in numeric fields as plain $last. "
        "Example: step 1 inserts a heading, step 2 uses $last+1 to insert body text after it. "
        "Cannot call execute_batch recursively."
    )
    parameters = {
        "type": "object",
        "properties": {
            "operations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tool": {
                            "type": "string",
                            "description": "Tool name to execute",
                        },
                        "args": {
                            "type": "object",
                            "description": (
                                "Tool arguments. Use $last, $last+1, "
                                "$step.N for paragraph chaining."
                            ),
                        },
                    },
                    "required": ["tool"],
                },
                "description": ("List of {tool, args} to execute sequentially"),
            },
            "stop_on_error": {
                "type": "boolean",
                "description": ("Halt on first failed operation (default: true)"),
            },
            "follow": {
                "type": "string",
                "description": (
                    "Scroll the view to follow edits. "
                    "'off' = no scroll (default), "
                    "'each' = scroll after every operation, "
                    "'end' = scroll after the last operation only"
                ),
            },
        },
        "required": ["operations"],
    }
    tier = "core"
    is_mutation = True

    def execute(self, ctx, **kwargs):
        operations = kwargs["operations"]
        stop_on_error = kwargs.get("stop_on_error", True)
        follow = kwargs.get("follow", "off")

        if not operations:
            return {"status": "error", "error": "No operations provided"}
        if len(operations) > 50:
            return {"status": "error", "error": "Maximum 50 operations per batch"}

        tool_reg = ctx.services.tools

        # -- Pre-flight validation (pure Python, no UNO) --
        validation_errors = []
        for i, op in enumerate(operations):
            tool_name = op.get("tool", "")
            args = op.get("args") or {}

            if tool_name == "execute_batch":
                validation_errors.append(
                    {
                        "step": i + 1,
                        "tool": tool_name,
                        "error": "Recursive execute_batch not allowed",
                    }
                )
                continue

            tool = tool_reg.get(tool_name)
            if tool is None:
                validation_errors.append(
                    {
                        "step": i + 1,
                        "tool": tool_name,
                        "error": "Unknown tool: %s" % tool_name,
                    }
                )
                continue

            has_vars = (
                any(isinstance(v, str) and "$" in v for v in args.values())
                if isinstance(args, dict)
                else False
            )
            if not has_vars:
                ok, msg = tool.validate(**args)
                if not ok:
                    validation_errors.append(
                        {"step": i + 1, "tool": tool_name, "error": msg}
                    )

        if validation_errors:
            return {
                "status": "error",
                "error": "Validation failed - nothing was executed",
                "validation_errors": validation_errors,
                "total": len(operations),
            }

        # -- Enter batch mode (suppress per-tool cache invalidation) --
        tool_reg.batch_mode = True

        # -- Execute --
        results = []
        stopped = False
        stop_reason = None
        last_result = None
        batch_vars = {}

        try:
            for i, op in enumerate(operations):
                tool_name = op.get("tool", "")
                args = op.get("args") or {}

                if batch_vars:
                    args = resolve_batch_vars(args, batch_vars)

                t0 = time.perf_counter()
                result = tool_reg.execute(tool_name, ctx, **args)
                step_ms = round((time.perf_counter() - t0) * 1000, 1)
                step_ok = isinstance(result, dict) and result.get("status") != "error"
                results.append(
                    {
                        "step": i + 1,
                        "tool": tool_name,
                        "success": step_ok,
                        "elapsed_ms": step_ms,
                        "result": result,
                    }
                )
                last_result = result

                if step_ok:
                    pi, bm = extract_step_info(result)
                    if pi is not None:
                        batch_vars["$last"] = pi
                        batch_vars["$step.%d" % (i + 1)] = pi
                    if bm:
                        batch_vars["$last.bookmark"] = bm
                        batch_vars["$step.%d.bookmark" % (i + 1)] = bm

                if follow == "each" and step_ok:
                    _follow_result(ctx, result)

                if stop_on_error and not step_ok:
                    stopped = True
                    stop_reason = "Tool '%s' failed" % tool_name
                    break

                if i < len(operations) - 1:
                    time.sleep(0.01)

        finally:
            tool_reg.batch_mode = False
            doc_svc = ctx.services.get("document")
            if doc_svc:
                doc_svc.invalidate_cache(ctx.doc)

        if follow == "end" and last_result and not stopped:
            _follow_result(ctx, last_result)

        all_ok = all(r["success"] for r in results) and not stopped
        resp = {
            "status": "ok" if all_ok else "error",
            "completed": len(results),
            "total": len(operations),
            "stopped": stopped,
            "results": results,
        }
        if batch_vars:
            resp["batch_vars"] = batch_vars
        if stop_reason:
            resp["stop_reason"] = stop_reason
        return resp
