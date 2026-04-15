import pytest

from plugin.framework.tool_base import ToolBase
from plugin.framework.tool_registry import ToolRegistry
from plugin.framework.tool_context import ToolContext
from plugin.framework.service_registry import ServiceRegistry
from plugin.framework.event_bus import EventBus
from plugin.modules.batch.batch_vars import (
    resolve_batch_vars,
    extract_step_info,
    _VAR_RE,
    _resolve_var,
)
from plugin.modules.batch.tools.batch import ExecuteBatch


class FakeReadTool(ToolBase):
    name = "fake_read"
    description = "Fake read tool for batch testing."
    parameters = {"type": "object", "properties": {}, "required": []}
    is_mutation = False

    def execute(self, ctx, **kwargs):
        return {"status": "ok", "paragraph_index": 5}


class FakeWriteTool(ToolBase):
    name = "fake_write"
    description = "Fake write tool for batch testing."
    parameters = {
        "type": "object",
        "properties": {
            "locator": {"type": "string"},
            "paragraph_index": {"type": "integer"},
        },
        "required": [],
    }
    is_mutation = True

    def execute(self, ctx, **kwargs):
        pi = kwargs.get("paragraph_index")
        loc = kwargs.get("locator", "")
        bm = "_mcp_7" if pi == 5 else None
        return {
            "status": "ok",
            "paragraph_index": pi or 7,
            "bookmark": bm,
            "locator": loc,
        }


class FakeWriteNoBookmarkTool(ToolBase):
    name = "fake_write_nb"
    description = "Fake write tool without bookmark."
    parameters = {
        "type": "object",
        "properties": {"paragraph_index": {"type": "integer"}},
        "required": ["paragraph_index"],
    }
    is_mutation = True

    def execute(self, ctx, **kwargs):
        return {"status": "ok", "paragraph_index": kwargs["paragraph_index"] + 1}


class FakeFailTool(ToolBase):
    name = "fake_fail"
    description = "Fake tool that fails."
    parameters = {"type": "object", "properties": {}, "required": []}

    def execute(self, ctx, **kwargs):
        return {"status": "error", "message": "boom"}


class FakeStopConditionsTool(ToolBase):
    name = "check_stop_conditions"
    description = "Fake stop conditions."
    parameters = {"type": "object", "properties": {}, "required": []}
    doc_types = ["writer"]

    def __init__(self, should_stop=False):
        self._should_stop = should_stop

    def execute(self, ctx, **kwargs):
        return {"status": "ok", "should_stop": self._should_stop}


class MockDocService:
    name = "document"

    def __init__(self):
        self.invalidate_count = 0

    def invalidate_cache(self, doc):
        self.invalidate_count += 1

    def get_paragraph_ranges(self, model):
        return []


def _make_ctx(services, doc=None, doc_type="writer"):
    return ToolContext(
        doc=doc, ctx=None, doc_type=doc_type, services=services, caller="test"
    )


def _make_registry(services, extra_tools=None):
    reg = ToolRegistry(services)
    reg.register(FakeReadTool())
    reg.register(FakeWriteTool())
    reg.register(FakeWriteNoBookmarkTool())
    reg.register(FakeFailTool())
    if extra_tools:
        for t in extra_tools:
            reg.register(t)
    return reg


class TestBatchVarsResolution:
    def test_last_alone(self):
        r = resolve_batch_vars({"idx": "$last"}, {"$last": 5})
        assert r["idx"] == 5

    def test_last_plus_offset(self):
        r = resolve_batch_vars({"idx": "$last+1"}, {"$last": 5})
        assert r["idx"] == 6

    def test_last_minus_offset(self):
        r = resolve_batch_vars({"idx": "$last-2"}, {"$last": 10})
        assert r["idx"] == 8

    def test_step_n(self):
        r = resolve_batch_vars({"idx": "$step.1"}, {"$step.1": 3})
        assert r["idx"] == 3

    def test_step_n_plus_offset(self):
        r = resolve_batch_vars({"idx": "$step.2+3"}, {"$step.2": 4})
        assert r["idx"] == 7

    def test_last_bookmark(self):
        r = resolve_batch_vars({"loc": "$last.bookmark"}, {"$last.bookmark": "_mcp_7"})
        assert r["loc"] == "bookmark:_mcp_7"

    def test_step_n_bookmark(self):
        r = resolve_batch_vars(
            {"loc": "$step.1.bookmark"}, {"$step.1.bookmark": "_mcp_3"}
        )
        assert r["loc"] == "bookmark:_mcp_3"

    def test_embedded_variable(self):
        r = resolve_batch_vars({"loc": "paragraph:$last"}, {"$last": 5})
        assert r["loc"] == "paragraph:5"

    def test_embedded_variable_with_offset(self):
        r = resolve_batch_vars({"loc": "paragraph:$last+1"}, {"$last": 5})
        assert r["loc"] == "paragraph:6"

    def test_unknown_variable_left_as_is(self):
        r = resolve_batch_vars({"idx": "$unknown"}, {})
        assert r["idx"] == "$unknown"

    def test_no_batch_vars_returns_unchanged(self):
        args = {"key": "value"}
        assert resolve_batch_vars(args, {}) == args
        assert resolve_batch_vars(args, None) == args

    def test_nested_dict_resolution(self):
        r = resolve_batch_vars({"outer": {"inner": "$last"}}, {"$last": 5})
        assert r["outer"]["inner"] == 5

    def test_list_resolution(self):
        r = resolve_batch_vars(["$last", "$last+1"], {"$last": 5})
        assert r == [5, 6]

    def test_non_string_passthrough(self):
        r = resolve_batch_vars({"n": 42, "b": True}, {"$last": 5})
        assert r == {"n": 42, "b": True}


class TestExtractStepInfo:
    def test_paragraph_index(self):
        pi, bm = extract_step_info({"paragraph_index": 5})
        assert pi == 5
        assert bm is None

    def test_para_index_alias(self):
        pi, bm = extract_step_info({"para_index": 3})
        assert pi == 3
        assert bm is None

    def test_with_bookmark(self):
        pi, bm = extract_step_info({"paragraph_index": 5, "bookmark": "_mcp_5"})
        assert pi == 5
        assert bm == "_mcp_5"

    def test_none_values(self):
        pi, bm = extract_step_info({"other": "data"})
        assert pi is None
        assert bm is None

    def test_non_dict(self):
        pi, bm = extract_step_info("not a dict")
        assert pi is None
        assert bm is None


class TestExecuteBatchIntegration:
    def _make_services_and_ctx(self, extra_tools=None):
        bus = EventBus()
        doc_svc = MockDocService()
        services = ServiceRegistry()
        services.register_instance("document", doc_svc)
        services.register_instance("events", bus)
        reg = _make_registry(services, extra_tools)
        services.register_instance("tools", reg)
        ctx = _make_ctx(services)
        return services, ctx, doc_svc, reg

    def test_simple_two_step_batch(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "fake_read"},
                {"tool": "fake_write"},
            ],
        )
        assert result["status"] == "ok"
        assert result["completed"] == 2
        assert result["total"] == 2
        assert result["stopped"] is False
        assert all(r["success"] for r in result["results"])

    def test_variable_chaining_last(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "fake_read"},
                {"tool": "fake_write", "args": {"paragraph_index": "$last"}},
            ],
        )
        assert result["status"] == "ok"
        step1_result = result["results"][0]["result"]
        assert step1_result["paragraph_index"] == 5
        step2_result = result["results"][1]["result"]
        assert step2_result["paragraph_index"] == 5
        assert result["batch_vars"]["$last"] == 5

    def test_variable_chaining_with_offset(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "fake_read"},
                {"tool": "fake_write", "args": {"paragraph_index": "$last+1"}},
            ],
        )
        step2 = result["results"][1]["result"]
        assert step2["paragraph_index"] == 6

    def test_bookmark_chaining(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "fake_read"},
                {"tool": "fake_write", "args": {"paragraph_index": "$last"}},
            ],
        )
        assert result["batch_vars"]["$last.bookmark"] == "_mcp_7"

    def test_step_n_reference(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "fake_read"},
                {"tool": "fake_write", "args": {"paragraph_index": "$last"}},
                {"tool": "fake_write_nb", "args": {"paragraph_index": "$step.1"}},
            ],
        )
        step3 = result["results"][2]["result"]
        assert step3["paragraph_index"] == 6
        assert result["batch_vars"]["$step.1"] == 5

    def test_stop_on_error(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "fake_read"},
                {"tool": "fake_fail"},
                {"tool": "fake_read"},
            ],
            stop_on_error=True,
        )
        assert result["status"] == "error"
        assert result["completed"] == 2
        assert result["stopped"] is True
        assert "failed" in result["stop_reason"].lower()

    def test_continue_on_error(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "fake_read"},
                {"tool": "fake_fail"},
                {"tool": "fake_read"},
            ],
            stop_on_error=False,
        )
        assert result["completed"] == 3
        assert result["stopped"] is False
        assert result["results"][1]["success"] is False
        assert result["results"][0]["success"] is True
        assert result["results"][2]["success"] is True

    def test_batch_mode_flag_during_execution(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch_mode_snapshots = []

        class SpyTool(ToolBase):
            name = "spy_tool"
            description = "Records batch mode."
            parameters = {"type": "object", "properties": {}, "required": []}

            def execute(self, ctx, **kwargs):
                tool_reg = ctx.services.tools
                batch_mode_snapshots.append(tool_reg.batch_mode)
                return {"status": "ok", "paragraph_index": 1}

        reg.register(SpyTool())
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "spy_tool"},
                {"tool": "spy_tool"},
            ],
        )
        assert batch_mode_snapshots == [True, True]
        assert reg.batch_mode is False

    def test_batch_mode_reset_on_error(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "fake_fail"},
            ],
        )
        assert reg.batch_mode is False

    def test_cache_invalidation_at_end(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "fake_read"},
                {"tool": "fake_write"},
            ],
        )
        assert doc_svc.invalidate_count >= 1

    def test_empty_operations(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        result = batch.execute(ctx, operations=[])
        assert result["status"] == "error"

    def test_too_many_operations(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        ops = [{"tool": "fake_read"} for _ in range(51)]
        result = batch.execute(ctx, operations=ops)
        assert result["status"] == "error"
        assert "Maximum" in result["error"]

    def test_recursive_batch_rejected(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {
                    "tool": "execute_batch",
                    "args": {"operations": [{"tool": "fake_read"}]},
                },
            ],
        )
        assert result["status"] == "error"
        assert any("Recursive" in e["error"] for e in result["validation_errors"])

    def test_unknown_tool_rejected(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "nonexistent_tool"},
            ],
        )
        assert result["status"] == "error"
        assert "validation_errors" in result

    def test_preflight_validation_prevents_execution(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "fake_write_nb"},
            ],
        )
        assert result["status"] == "error"
        assert "validation_errors" in result

    def test_preflight_with_vars_skips_validation(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "fake_read"},
                {"tool": "fake_write", "args": {"locator": "paragraph:$last"}},
            ],
        )
        assert result["status"] == "ok"

    def test_stop_conditions_checked(self):
        stop_tool = FakeStopConditionsTool(should_stop=True)
        services, ctx, doc_svc, reg = self._make_services_and_ctx(
            extra_tools=[stop_tool]
        )
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "fake_read"},
                {"tool": "fake_read"},
            ],
            check_conditions=True,
        )
        assert result["stopped"] is True
        assert "Stop signal" in result["stop_reason"]

    def test_stop_conditions_not_checked_by_default(self):
        stop_tool = FakeStopConditionsTool(should_stop=True)
        services, ctx, doc_svc, reg = self._make_services_and_ctx(
            extra_tools=[stop_tool]
        )
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "fake_read"},
                {"tool": "fake_read"},
            ],
        )
        assert result["stopped"] is False
        assert result["completed"] == 2

    def test_elapsed_ms_in_results(self):
        services, ctx, doc_svc, reg = self._make_services_and_ctx()
        batch = ExecuteBatch()
        result = batch.execute(
            ctx,
            operations=[
                {"tool": "fake_read"},
            ],
        )
        assert "elapsed_ms" in result["results"][0]
        assert isinstance(result["results"][0]["elapsed_ms"], (int, float))


class TestVarRegex:
    def test_matches_last(self):
        m = _VAR_RE.fullmatch("$last")
        assert m is not None

    def test_matches_last_plus(self):
        m = _VAR_RE.fullmatch("$last+3")
        assert m is not None
        assert m.group(1) == "+"
        assert m.group(2) == "3"

    def test_matches_last_minus(self):
        m = _VAR_RE.fullmatch("$last-2")
        assert m is not None
        assert m.group(1) == "-"
        assert m.group(2) == "2"

    def test_matches_last_bookmark(self):
        m = _VAR_RE.fullmatch("$last.bookmark")
        assert m is not None

    def test_matches_step_n(self):
        m = _VAR_RE.fullmatch("$step.3")
        assert m is not None
        assert m.group(4) == "3"

    def test_matches_step_n_bookmark(self):
        m = _VAR_RE.fullmatch("$step.2.bookmark")
        assert m is not None
        assert m.group(3) == "2"

    def test_no_match_random_text(self):
        m = _VAR_RE.fullmatch("hello")
        assert m is None

    def test_embedded_match(self):
        found = _VAR_RE.findall("paragraph:$last+1")
        assert len(found) >= 1
