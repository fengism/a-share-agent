"""Layer C: 「在问某只股票，但看不出是哪只」时先消歧，而不是猜标的。

精度优先：`_STOCK_CONTEXT_KEYWORDS` 里的“分析/怎么样”等泛化动词不能作为触发
条件，否则“分析一下光伏行业估值”会被强制调 search_stocks。

名称索引必须打补丁：``data/`` 在 .gitignore 里，CI 上没有 ``stock_names.json``，
依赖真实快照的断言会在 CI 静默变成“任何名称都认不出”。
"""

from __future__ import annotations

import pytest

from app.financial_data.hk import name_reference as hk
from app.financial_data.stock.profile import name_map
from app.financial_data.stock.profile.short_names import (
    build_first_char_index,
    build_short_name_index,
    has_specific_stock_context,
)
from app.modules.chat.capability_plan import build_chat_capability_plan
from app.modules.chat.stock_reference import needs_stock_resolution

_REFERENCE_NAMES: tuple[str, ...] = ("贵州茅台", "海康威视")


@pytest.fixture(autouse=True)
def _fixed_reference_indexes(monkeypatch):
    """锁定名称索引，不读 data/ 下的真实快照（CI 没有这个文件）。"""
    monkeypatch.setattr(name_map, "_stock_name_file_signature", lambda: None)
    monkeypatch.setattr(name_map, "_stock_source_key", None)
    monkeypatch.setattr(
        name_map,
        "_stock_name_detection_index",
        name_map._build_stock_name_detection_index(
            name_map.StockNameMapSnapshot(
                mapping={str(i): n for i, n in enumerate(_REFERENCE_NAMES)},
                default_source_id="cache.legacy_stock_names",
            )
        ),
    )
    monkeypatch.setattr(
        name_map,
        "_stock_short_name_index",
        build_first_char_index(build_short_name_index(_REFERENCE_NAMES)),
    )
    monkeypatch.setattr(name_map, "_stock_pinyin_index", frozenset())
    monkeypatch.setattr(name_map, "_stock_reference_names", _REFERENCE_NAMES)
    # 港股索引同样不读 data/hk_stock_search_index.json。
    monkeypatch.setattr(hk, "_ensure_hk_reference_indexes", lambda: None)
    monkeypatch.setattr(hk, "_hk_name_index", build_first_char_index(frozenset()))
    monkeypatch.setattr(hk, "_hk_short_name_index", build_first_char_index(frozenset()))
    monkeypatch.setattr(hk, "_hk_pinyin_index", frozenset())
    monkeypatch.setattr(hk, "_hk_names", ())


def test_specific_stock_context_ignores_generic_analysis_verbs():
    assert has_specific_stock_context("这只股票怎么样") is True
    assert has_specific_stock_context("帮我看看该股的压力位") is True
    assert has_specific_stock_context("这个标的能买吗") is True
    # 泛化分析动词不算“具体标的”语境。
    assert has_specific_stock_context("分析一下光伏行业估值") is False
    assert has_specific_stock_context("看看今天的新闻") is False


def test_needs_resolution_only_without_a_recognized_target():
    # 认不出标的 + 具体标的语境 -> 需要消歧
    assert needs_stock_resolution("这只票还能拿吗") is True
    # 认得出的标的 -> 不需要消歧
    assert needs_stock_resolution("这只茅台还能拿吗") is False


def test_unknown_specific_target_activates_stock_analysis_with_search_tool():
    plan = build_chat_capability_plan("这家做光伏的公司股票能买入吗", max_initial_active_skills=3)

    assert plan.needs_stock_resolution is True
    assert "stock_analysis" in plan.initial_skill_names
    assert "search_stocks" in plan.tool_names


def test_vague_company_description_also_asks_for_resolution():
    plan = build_chat_capability_plan("字节跳动能买入吗", max_initial_active_skills=3)

    assert plan.needs_stock_resolution is True
    assert "search_stocks" in plan.tool_names


def test_known_target_does_not_request_resolution():
    plan = build_chat_capability_plan("茅台股票能买吗", max_initial_active_skills=3)

    assert plan.needs_stock_resolution is False
    assert "stock_analysis" in plan.initial_skill_names


def test_explicit_code_does_not_request_resolution():
    plan = build_chat_capability_plan("600519 这只股票能买吗", max_initial_active_skills=3)

    assert plan.needs_stock_resolution is False


def test_industry_question_does_not_request_resolution():
    plan = build_chat_capability_plan("分析一下光伏行业估值", max_initial_active_skills=3)

    assert plan.needs_stock_resolution is False


def test_generic_market_question_does_not_request_resolution():
    plan = build_chat_capability_plan("今天大盘怎么样", max_initial_active_skills=3)

    assert plan.needs_stock_resolution is False


def test_disabled_stock_analysis_skill_does_not_request_resolution():
    plan = build_chat_capability_plan(
        "这只票还能拿吗",
        enabled_skill_names=("information_query",),
        max_initial_active_skills=3,
    )

    assert plan.needs_stock_resolution is False


def test_resolution_request_always_implies_the_active_skill():
    """消歧请求不能与最终激活的 Skill 脱节。

    判定必须看**合并候选 Agent 之后**的 active_skills：旧实现用的是合并前的快照，
    于是 stock_analysis 经候选 Agent 补入时会出现「不下发指令」或「指令指向未激活
    Skill」的不一致。
    """
    messages = (
        "这只票还能拿吗",
        "这家做光伏的公司股票能买入吗",
        "字节跳动能买入吗",
        "茅台股票能买吗",
        "分析一下光伏行业估值",
        "今天大盘怎么样",
    )
    for message in messages:
        plan = build_chat_capability_plan(message, max_initial_active_skills=3)
        if plan.needs_stock_resolution:
            assert "stock_analysis" in plan.active_skill_names, message
