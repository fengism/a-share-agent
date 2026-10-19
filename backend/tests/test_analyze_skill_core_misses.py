"""core_tools miss analysis script."""

from scripts.analyze_skill_core_misses import (
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
