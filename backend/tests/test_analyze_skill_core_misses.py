"""core_tools miss analysis script."""

from scripts.analyze_skill_core_misses import (
    build_core_usage,
    build_report,
    collect_prefixed,
    extract_events,
    render_text,
)


def _payload() -> dict:
    return {
        "metrics": {
            "agentic": {
                "events": {
                    "skill_load_success": 5,
                    "skill_initial_tools_expanded": 2,
                    "skill_tools_expanded": 2,
                    "skill_core_tool_missed:get_stock_documents": 3,
                    "skill_core_tool_missed:get_stock_sentiment": 1,
                    "skill_load_after_initial:stock_analysis": 4,
                    "tool_called:get_stock_info": 9,
                }
            }
        }
    }


def test_extract_events_accepts_wrapped_and_raw_payloads():
    events = extract_events(_payload())
    assert events["skill_load_success"] == 5
    assert extract_events({"agentic": {"events": {"x": 1}}}) == {"x": 1}
    assert extract_events({}) == {}


def test_collect_prefixed_counts_tools():
    assert collect_prefixed(extract_events(_payload()), "skill_core_tool_missed:") == {
        "get_stock_documents": 3,
        "get_stock_sentiment": 1,
    }


def test_build_report_flags_promotion_candidates():
    report = build_report(extract_events(_payload()), min_misses=2)

    rows = {row["tool"]: row for row in report["core_tool_misses"]}
    assert rows["get_stock_documents"]["misses"] == 3
    assert rows["get_stock_documents"]["skill"] == "stock_analysis"
    assert rows["get_stock_documents"]["in_core"] is False
    assert rows["get_stock_documents"]["promote"] is True
    assert rows["get_stock_sentiment"]["promote"] is False
    assert report["load_after_initial"] == {"stock_analysis": 4}


def test_render_text_mentions_misses_and_after_initial():
    text = render_text(build_report(extract_events(_payload())))

    assert "get_stock_documents" in text
    assert "stock_analysis" in text


def test_build_report_flags_unused_core_tools():
    events = extract_events(_payload())
    report = build_report(events)

    assert report["tool_calls"] == {"get_stock_info": 9}
    usage = {row["tool"]: row for row in report["core_tool_usage"]}
    assert usage["get_stock_info"]["calls"] == 9
    assert usage["get_stock_info"]["unused"] is False
    assert any(row["unused"] for row in usage.values())


def test_core_usage_requires_a_skill_with_declared_core_tools():
    assert build_core_usage({"get_stock_info": 1}, {"no_core": frozenset()}) == []
    rows = build_core_usage({"a": 3}, {"s": frozenset({"a", "b"})})
    assert rows == [
        {"tool": "a", "skill": "s", "calls": 3, "unused": False},
        {"tool": "b", "skill": "s", "calls": 0, "unused": True},
    ]


def test_demotion_candidates_need_a_minimum_sample():
    """样本很小时「从未调用」几乎必然成立，不能据此建议降级。"""
    from scripts.analyze_skill_core_misses import render_text as render

    events = extract_events(_payload())  # 只有 9 次工具调用
    small = build_report(events, min_samples=200)
    assert small["tool_call_samples"] == 9
    assert small["demotion_sample_ready"] is False
    assert not any(row["unused"] for row in small["core_tool_usage"])
    assert "only 9 tool calls observed" in render(small)

    enough = build_report(events, min_samples=5)
    assert enough["demotion_sample_ready"] is True
    assert any(row["unused"] for row in enough["core_tool_usage"])
