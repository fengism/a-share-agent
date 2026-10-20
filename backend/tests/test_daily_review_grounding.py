"""深度输出的确定性校验：情绪周期 / 关键点位 / 情景预案。

prompt 已要求「情绪周期必须收敛到明确结论」「关键点位必须带具体数值」，但此前这些
字段完全没有校验——模型写「冰点」而数据是主升共振也没人拦。这里的规则是
「锚点信号强时按锚点修正，信号弱时保留模型判断并记 warning」，不静默篡改。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.daily_review import review_builder
from app.modules.daily_review.models import (
    DailyReviewDataSnapshot,
    DailyReviewScenario,
    DailyReviewSentimentCycle,
)


def _snapshot(
    *,
    ladder: list[dict[str, Any]] | None = None,
    break_items: list[dict[str, Any]] | None = None,
    limit_up: int | None = None,
    limit_down: int | None = None,
) -> DailyReviewDataSnapshot:
    statistics: dict[str, Any] = {}
    if limit_up is not None:
        statistics["limit_up_count"] = limit_up
    if limit_down is not None:
        statistics["limit_down_count"] = limit_down
    return DailyReviewDataSnapshot(
        limit_up_ladder={"stocks": ladder} if ladder is not None else {},
        limit_break_pool={"items": break_items} if break_items is not None else {},
        market_statistics=statistics,
    )


def _ladder(max_board: int, *, extra: int = 0) -> list[dict[str, Any]]:
    """构造 1..max_board 各有一家的天梯。"""
    stocks: list[dict[str, Any]] = []
    for board in range(1, max_board + 1):
        stocks.append({"name": f"{board}板股", "board_count": board})
    stocks.extend({"name": f"首板{index}", "board_count": 1} for index in range(extra))
    return stocks


def _cycle(stage: str, evidence: list[str] | None = None) -> DailyReviewSentimentCycle:
    return DailyReviewSentimentCycle(
        stage=stage, ladder_health="梯队健康", evidence=evidence or [],
    )


# --- 情绪周期 --------------------------------------------------------------


def test_derivation_matches_the_anchor_thresholds():
    assert review_builder.derive_sentiment_stage(_snapshot(limit_down=25)) == ("退潮杀跌", "strong")
    assert review_builder.derive_sentiment_stage(
        _snapshot(ladder=_ladder(2), limit_up=20, limit_down=2)
    ) == ("冰点", "strong")
    assert review_builder.derive_sentiment_stage(
        _snapshot(ladder=_ladder(6), limit_up=80, break_items=[], limit_down=1)
    ) == ("主升共振", "strong")
    assert review_builder.derive_sentiment_stage(
        _snapshot(ladder=_ladder(6), break_items=[{}] * 4, limit_up=80)
    ) == ("高位分化", "strong")
    assert review_builder.derive_sentiment_stage(_snapshot(ladder=_ladder(3))) == ("修复回暖", "weak")
    assert review_builder.derive_sentiment_stage(_snapshot()) == (None, "none")


def test_strong_anchor_signal_corrects_the_model_stage():
    snapshot = _snapshot(limit_down=30)
    cycle, warnings = review_builder.ground_sentiment_cycle(snapshot, _cycle("主升共振"))

    assert cycle is not None and cycle.stage == "退潮杀跌"
    assert any("已按锚点修正" in warning for warning in warnings)


def test_weak_anchor_signal_keeps_the_model_stage_but_warns():
    snapshot = _snapshot(ladder=_ladder(3))
    cycle, warnings = review_builder.ground_sentiment_cycle(snapshot, _cycle("冰点"))

    assert cycle is not None and cycle.stage == "冰点", "弱信号不得覆盖模型判断"
    assert any("保留模型判断" in warning for warning in warnings)


def test_missing_cycle_is_filled_from_anchors():
    snapshot = _snapshot(limit_down=30)
    cycle, warnings = review_builder.ground_sentiment_cycle(snapshot, None)

    assert cycle is not None and cycle.stage == "退潮杀跌"
    assert cycle.evidence, "补出来的定位必须带可核验证据"
    assert any("未给出情绪周期定位" in warning for warning in warnings)


def test_missing_cycle_without_anchors_stays_missing():
    cycle, warnings = review_builder.ground_sentiment_cycle(_snapshot(), None)
    assert cycle is None
    assert warnings == []


def test_quantified_evidence_is_supplemented_to_at_least_two_items():
    snapshot = _snapshot(ladder=_ladder(6), limit_up=80, limit_down=1)
    cycle, warnings = review_builder.ground_sentiment_cycle(
        snapshot, _cycle("主升共振", evidence=["感觉很强"]),
    )

    assert cycle is not None
    assert len([item for item in cycle.evidence if any(ch.isdigit() for ch in item)]) >= 2
    assert any("量化证据不足" in warning for warning in warnings)


def test_evidence_already_quantified_is_left_alone():
    snapshot = _snapshot(ladder=_ladder(6), limit_up=80, limit_down=1)
    evidence = ["空间板 6 板", "涨停 80 家", "炸板率 0%"]
    cycle, warnings = review_builder.ground_sentiment_cycle(
        snapshot, _cycle("主升共振", evidence=evidence),
    )

    assert cycle is not None and cycle.evidence == evidence
    assert warnings == []


# --- 关键点位 --------------------------------------------------------------


def test_key_levels_without_numbers_are_dropped():
    kept, warnings = review_builder.ground_key_levels(
        _snapshot(), ["关注关键点位", "上证 3250 支撑", "", "成交额重回 1.5 万亿"],
    )

    assert kept == ["上证 3250 支撑", "成交额重回 1.5 万亿"]
    assert any("不含具体数值" in warning for warning in warnings)


def test_key_levels_are_deduped_and_capped():
    levels = [f"上证 {3200 + index} 支撑" for index in range(12)]
    kept, _ = review_builder.ground_key_levels(_snapshot(), [*levels, levels[0]])

    assert len(kept) == 8
    assert len(set(kept)) == 8


def test_clean_key_levels_produce_no_warning():
    kept, warnings = review_builder.ground_key_levels(_snapshot(), ["上证 3250 支撑"])
    assert kept == ["上证 3250 支撑"]
    assert warnings == []


# --- 情景预案 --------------------------------------------------------------


def _plan(name: str, trigger: str) -> DailyReviewScenario:
    return DailyReviewScenario(name=name, trigger=trigger, playbook="减仓", watch_levels=[])


def test_scenarios_without_trigger_are_dropped():
    kept, _ = review_builder.ground_scenario_plans(
        _snapshot(),
        [_plan("超预期", ""), _plan("符合预期", "上证站上 3250")],
    )

    assert [plan.name for plan in kept] == ["符合预期"]


def test_vague_trigger_is_kept_but_warned():
    """缺数字不该删掉整条预案——playbook 本身仍有价值。"""
    kept, warnings = review_builder.ground_scenario_plans(
        _snapshot(), [_plan("超预期", "指数放量上涨")],
    )

    assert [plan.name for plan in kept] == ["超预期"]
    assert any("缺少具体数值" in warning for warning in warnings)


def test_missing_scenario_names_are_reported_not_invented():
    kept, warnings = review_builder.ground_scenario_plans(
        _snapshot(), [_plan("超预期", "上证站上 3250")],
    )

    assert [plan.name for plan in kept] == ["超预期"]
    assert any("缺少符合预期、低于预期" in warning for warning in warnings)


def test_complete_scenarios_produce_no_warning():
    plans = [
        _plan("超预期", "上证站上 3250"),
        _plan("符合预期", "上证 3150-3250 震荡"),
        _plan("低于预期", "上证跌破 3150"),
    ]
    kept, warnings = review_builder.ground_scenario_plans(_snapshot(), plans)

    assert kept == plans
    assert warnings == []


@pytest.mark.parametrize("stage", ["冰点", "修复回暖", "主升共振", "高位分化", "退潮杀跌"])
def test_every_documented_stage_is_reachable(stage):
    """阈值表必须能推出全部五档，否则某个阶段永远不可达。"""
    cases = {
        "冰点": _snapshot(ladder=_ladder(2), limit_up=20, limit_down=2),
        "修复回暖": _snapshot(ladder=_ladder(3)),
        "主升共振": _snapshot(ladder=_ladder(6), limit_up=80, break_items=[], limit_down=1),
        "高位分化": _snapshot(ladder=_ladder(6), break_items=[{}] * 4, limit_up=80),
        "退潮杀跌": _snapshot(limit_down=25),
    }
    assert review_builder.derive_sentiment_stage(cases[stage])[0] == stage


# --- 市场情绪分布（财联社） ------------------------------------------------


def _emotion(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "source": "财联社",
        "fetched_at": "2026-10-15T15:00:00",
        "market_degree": 42,
        "profit_ratio": "38%",
        "up_ratio": "45%",
        "up_down_dis": {"up_num": 2100, "down_num": 2800, "down_6": 40, "down_8": 12, "down_10": 5},
    }
    base.update(overrides)
    return base


def test_emotion_summary_exposes_verifiable_numbers():
    snapshot = DailyReviewDataSnapshot(market_emotion=_emotion())
    summary = review_builder._emotion_summary(snapshot)

    assert "涨跌家数 2100:2800" in summary
    assert "跌幅超 6% 的个股 57 家" in summary
    assert "赚钱效应 38%" in summary
    assert "情绪温度 42" in summary


def test_emotion_summary_is_empty_without_data():
    assert review_builder._emotion_summary(DailyReviewDataSnapshot()) == ""


def test_emotion_appears_in_the_prompt_anchors():
    snapshot = DailyReviewDataSnapshot(market_emotion=_emotion())
    anchors = review_builder._quant_anchors(snapshot)

    assert "- 市场情绪分布：涨跌家数 2100:2800" in anchors


def test_missing_emotion_is_declared_not_guessed():
    anchors = review_builder._quant_anchors(DailyReviewDataSnapshot())
    assert "情绪分布数据缺失" in anchors


def test_emotion_feeds_sentiment_evidence():
    snapshot = DailyReviewDataSnapshot(
        limit_up_ladder={"stocks": _ladder(6)},
        market_statistics={"limit_up_count": 80, "limit_down_count": 1},
        market_emotion=_emotion(),
    )
    evidence = review_builder.sentiment_anchor_evidence(snapshot)

    assert any("情绪温度 42" in item for item in evidence)
    assert any("空间板高度 6 板" in item for item in evidence)
