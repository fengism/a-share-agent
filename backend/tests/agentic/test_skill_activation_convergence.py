"""P4c: score-based active Skill ordering and initial tool convergence."""

from app.agentic.skills.contracts import Skill
from app.modules.chat.capability_plan import build_chat_capability_plan


def _skill(keywords: tuple[str, ...]) -> Skill:
    return Skill(
        name="score_skill",
        description="score test",
        triggers=("test",),
        activation_keywords=keywords,
        tool_names=("fake_tool",),
        rules=("rule",),
    )


def test_match_score_rewards_ascii_and_long_keywords():
    assert _skill(("pe", "估值")).match_score("pe 估值") == 3
    assert _skill(("pe",)).match_score("pe") == 2
    assert _skill(("估值",)).match_score("估值") == 1
    assert _skill(("复合增长率",)).match_score("复合增长率") == 2
    assert _skill(("pe",)).match_score("apple") == 0


def test_plan_keeps_all_active_but_limits_initial_skills():
    plan = build_chat_capability_plan(
        "搜索一下光伏行业新闻",
        max_initial_active_skills=2,
    )

    assert len(plan.active_skill_names) > len(plan.initial_skill_names)
    assert plan.initial_skill_names == plan.active_skill_names[:2]
    assert set(plan.tool_names) <= set(plan.active_tool_names)
    assert set(plan.active_tool_names) <= set(plan.enabled_tool_names)


def test_plan_zero_initial_skills_keeps_only_dynamic_loading():
    plan = build_chat_capability_plan(
        "分析茅台估值",
        max_initial_active_skills=0,
    )

    assert plan.initial_skill_names == ()
    assert plan.tool_names == ()
    assert plan.active_tool_names
    assert plan.enabled_tool_names


def test_plan_negative_initial_limit_keeps_all_active_skills():
    plan = build_chat_capability_plan(
        "搜索一下光伏行业新闻",
        max_initial_active_skills=-1,
    )

    assert plan.initial_skill_names == plan.active_skill_names


def test_stock_code_forces_stock_analysis_into_initial_tools():
    plan = build_chat_capability_plan(
        "600519 最新情况",
        max_initial_active_skills=1,
    )

    assert plan.initial_skill_names == ("stock_analysis",)
    assert plan.tool_names


def test_url_only_forces_url_content_into_initial_tools():
    plan = build_chat_capability_plan(
        "https://example.com/report",
        max_initial_active_skills=1,
    )

    assert "url_content" in plan.initial_skill_names
    assert plan.tool_names


def test_full_stock_name_still_activates_stock_analysis(monkeypatch):
    from app.financial_data.stock.profile import name_map

    monkeypatch.setattr(name_map, "_stock_name_detection_index", ("贵州茅台",))
    monkeypatch.setattr(name_map, "_stock_short_name_index", frozenset())
    monkeypatch.setattr(name_map, "_stock_pinyin_index", frozenset())
    plan = build_chat_capability_plan("贵州茅台新闻")

    assert "stock_analysis" in plan.active_skill_names


def test_short_alias_with_context_activates_stock_analysis(monkeypatch):
    from app.financial_data.stock.profile import name_map

    monkeypatch.setattr(name_map, "_stock_name_detection_index", ())
    monkeypatch.setattr(name_map, "_stock_short_name_index", frozenset({"茅台"}))
    monkeypatch.setattr(name_map, "_stock_pinyin_index", frozenset())

    plan = build_chat_capability_plan("茅台新闻", max_initial_active_skills=2)

    assert "stock_analysis" in plan.initial_skill_names


def test_short_alias_without_context_does_not_force_stock_analysis(monkeypatch):
    from app.financial_data.stock.profile import name_map

    monkeypatch.setattr(name_map, "_stock_name_detection_index", ())
    monkeypatch.setattr(name_map, "_stock_short_name_index", frozenset({"茅台"}))
    monkeypatch.setattr(name_map, "_stock_pinyin_index", frozenset())

    plan = build_chat_capability_plan("茅台", max_initial_active_skills=2)

    assert "stock_analysis" not in plan.active_skill_names


def test_stock_code_with_announcement_still_activates_stock_analysis():
    plan = build_chat_capability_plan("600519 公告")

    assert "stock_analysis" in plan.active_skill_names


def test_industry_news_excludes_stock_analysis_from_initial_tools():
    plan = build_chat_capability_plan(
        "搜索一下光伏行业新闻",
        max_initial_active_skills=2,
    )

    assert "stock_analysis" not in plan.initial_skill_names
    assert len(plan.tool_names) < 15


def test_market_sentiment_does_not_activate_stock_analysis():
    plan = build_chat_capability_plan("市场情绪怎么样")

    assert "stock_analysis" not in plan.active_skill_names


def test_news_query_activates_information_query():
    plan = build_chat_capability_plan(
        "茅台新闻",
        max_initial_active_skills=2,
    )

    assert "information_query" in plan.active_skill_names
    assert "information_query" in plan.initial_skill_names
    assert plan.tool_names


def test_stock_announcement_initial_keeps_stock_and_information_skills():
    plan = build_chat_capability_plan(
        "600519 公告",
        max_initial_active_skills=2,
    )

    assert plan.initial_skill_names[0] == "stock_analysis"
    assert "information_query" in plan.initial_skill_names
