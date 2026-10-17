"""个股分析核心链路测试。

覆盖此前完全没有后端测试的部分：结构化输出校验、证据缺口降级、
关键点位覆盖策略、估值情景契约、归档重试与聚合页分区降级。
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.core.cache import analysis_cache
from app.modules.analysis import result_service
from app.modules.analysis.key_levels import KeyLevels, apply_key_levels
from app.modules.analysis.models import AnalysisResult, ValuationScenario, ValuationScenarios
from app.modules.analysis.page_service import AnalysisPageLoaders, get_analysis_page_data
from app.modules.analysis.prompts import apply_evidence_gap_degradation, parse_analysis_output


def _framework() -> dict:
    return {
        "information_quality": {
            "grade": "A",
            "grade_rationale": "公开资料充分",
            "evidence_confidence": 0.8,
            "investment_certainty": 0.6,
            "coverage_summary": "覆盖财务、行业与估值",
            "limitations": [],
        },
        "business_model": {"economic_engine": "高端白酒品牌溢价"},
        "moat": {"overall_durability": "强"},
        "management": {"track_record": "长期稳定"},
        "industry_position": {"secular_context": "消费升级"},
        "inversion": {"bear_case": "需求下滑"},
        "actions": {"rationale": "估值合理"},
    }


def _payload(**overrides) -> dict:
    payload = {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "analysis_date": "20260820",
        "current_price": 1500.0,
        "fundamental": {"score": 8, "summary": "基本面稳健"},
        "technical": {"score": 6, "summary": "震荡"},
        "sentiment": {"score": 7, "summary": "偏暖"},
        "overall_rating": 8,
        "overall_summary": "长期看好",
        "estimated_price_range": [1400.0, 1700.0],
        "signal": "buy",
        "confidence": 0.8,
        "research_framework": _framework(),
    }
    payload.update(overrides)
    return payload


def _result() -> AnalysisResult:
    return AnalysisResult.model_validate(_payload())


# ---------------------------------------------------------------- 结构化输出校验


def test_parse_analysis_output_accepts_valid_payload() -> None:
    output = parse_analysis_output(json.dumps(_payload()))
    assert output.current_price == 1500.0
    assert output.confidence == 0.8


def test_parse_analysis_output_requires_confidence_to_match_evidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        parse_analysis_output(json.dumps(_payload(confidence=0.5)))


def test_parse_analysis_output_requires_meaningful_framework() -> None:
    framework = _framework()
    framework.update({"moat": {}, "management": {}, "industry_position": {}, "inversion": {}, "actions": {}})
    with pytest.raises(ValueError, match="投资研究框架"):
        parse_analysis_output(json.dumps(_payload(research_framework=framework)))


def test_missing_current_price_falls_back_to_zero() -> None:
    output = parse_analysis_output(json.dumps(_payload(current_price=None)))
    assert output.current_price == 0.0


def test_null_price_ranges_are_normalized() -> None:
    output = parse_analysis_output(json.dumps(_payload(
        estimated_price_range=[None, None],
        fair_value_range=[None, 1200.0],
    )))
    assert output.estimated_price_range == (0.0, 0.0)
    assert output.fair_value_range is None


def test_analysis_result_tolerates_legacy_null_prices() -> None:
    result = AnalysisResult.model_validate(_payload(current_price=None, estimated_price_range=[None, None]))
    assert result.current_price == 0.0
    assert result.estimated_price_range == (0.0, 0.0)


# ---------------------------------------------------------------- 证据缺口降级


def test_evidence_gap_degradation_caps_confidence_and_grade() -> None:
    output = parse_analysis_output(json.dumps(_payload()))
    degraded = apply_evidence_gap_degradation(output, ("护城河与反证公开资料", "行业与价值链公开资料"))

    quality = degraded.research_framework.information_quality
    assert degraded.confidence == quality.evidence_confidence
    assert quality.evidence_confidence == pytest.approx(0.45)  # 0.65 - 0.1 * 2
    assert quality.grade == "C"
    assert any("未满足正文证据门槛" in item for item in quality.limitations)
    topics = {gap.topic for gap in degraded.research_framework.data_gaps}
    assert {"护城河与反证公开资料", "行业与价值链公开资料"} <= topics


def test_evidence_gap_degradation_is_noop_without_gaps() -> None:
    output = parse_analysis_output(json.dumps(_payload()))
    assert apply_evidence_gap_degradation(output, ()) is output


def test_evidence_gap_degradation_does_not_duplicate_existing_gap_topics() -> None:
    payload = _payload()
    payload["research_framework"]["data_gaps"] = [
        {"topic": "护城河与反证公开资料", "missing_data": "x", "decision_impact": "y", "follow_up": "z"},
    ]
    output = parse_analysis_output(json.dumps(payload))
    degraded = apply_evidence_gap_degradation(output, ("护城河与反证公开资料",))
    assert [gap.topic for gap in degraded.research_framework.data_gaps] == ["护城河与反证公开资料"]


# ---------------------------------------------------------------- 关键点位覆盖


def test_apply_key_levels_overrides_when_levels_computed() -> None:
    updated = apply_key_levels(
        _result(),
        KeyLevels(current_price=1600.0, support=1400.0, resistance=1800.0),
    )
    assert updated.technical.support_level == 1400.0
    assert updated.technical.resistance_level == 1800.0
    assert updated.current_price == 1600.0


def test_apply_key_levels_keeps_model_values_when_computation_failed() -> None:
    """空 KeyLevels 表示 K 线拉取/计算失败，此时不能把模型给出的点位清空。"""
    result = _result()
    result = result.model_copy(update={
        "technical": result.technical.model_copy(update={"support_level": 1234.0, "resistance_level": 2345.0}),
    })
    updated = apply_key_levels(result, KeyLevels())
    assert updated.technical.support_level == 1234.0
    assert updated.technical.resistance_level == 2345.0


# ---------------------------------------------------------------- 估值情景契约


def test_valuation_scenarios_reject_mismatched_names() -> None:
    with pytest.raises(ValueError, match="估值情景名称"):
        ValuationScenarios(
            bull=ValuationScenario(scenario="bear"),
            base=ValuationScenario(scenario="base"),
            bear=ValuationScenario(scenario="bull"),
        )


def test_valuation_scenarios_accept_matching_names() -> None:
    scenarios = ValuationScenarios(
        bull=ValuationScenario(scenario="bull"),
        base=ValuationScenario(scenario="base"),
        bear=ValuationScenario(scenario="bear"),
    )
    assert scenarios.base.scenario == "base"


# ---------------------------------------------------------------- 归档重试


async def test_persist_analysis_result_retries_three_times_then_raises(monkeypatch) -> None:
    attempts = {"count": 0}

    def _boom(*args, **kwargs):
        attempts["count"] += 1
        raise OSError("disk full")

    monkeypatch.setattr(result_service.analysis_storage, "save_analysis", _boom)
    with pytest.raises(result_service.AnalysisArchiveError):
        await result_service.persist_analysis_result(
            _result(), user_id=1, cache_key="archive-fail", cache_ttl_seconds=60,
        )
    assert attempts["count"] == 3


async def test_persist_analysis_result_caches_only_after_success(monkeypatch) -> None:
    saved: list[AnalysisResult] = []
    monkeypatch.setattr(
        result_service.analysis_storage,
        "save_analysis",
        lambda result, user_id: saved.append(result),
    )
    analysis_cache.delete("archive-ok")
    await result_service.persist_analysis_result(
        _result(), user_id=1, cache_key="archive-ok", cache_ttl_seconds=60,
    )
    assert len(saved) == 1
    assert analysis_cache.get("archive-ok") is not None


async def test_persist_analysis_result_does_not_cache_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        result_service.analysis_storage,
        "save_analysis",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("nope")),
    )
    analysis_cache.delete("archive-never")
    with pytest.raises(result_service.AnalysisArchiveError):
        await result_service.persist_analysis_result(
            _result(), user_id=1, cache_key="archive-never", cache_ttl_seconds=60,
        )
    assert analysis_cache.get("archive-never") is None


# ---------------------------------------------------------------- 聚合页分区降级


async def _unexpected(*args, **kwargs):
    raise AssertionError("该分区不应被调用")


async def _raise(*args, **kwargs):
    raise RuntimeError("上游不可用")


async def _slow(*args, **kwargs):
    await asyncio.sleep(0.5)
    return None


async def _empty_cached(code: str, user_id: int, cache_ttl: int):
    return None


async def test_page_data_without_market_data_only_reads_cached_analysis() -> None:
    page = await get_analysis_page_data(
        "600519",
        user_id=1,
        cache_ttl=60,
        section_timeout_seconds=1.0,
        loaders=AnalysisPageLoaders(
            stock_info=_unexpected,
            kline=_unexpected,
            intraday=_unexpected,
            valuation=_unexpected,
            cached_analysis=_empty_cached,
        ),
        include_market_data=False,
    )
    assert page.cached_analysis is None
    assert page.partial is False


async def test_page_data_marks_failed_sections_unavailable() -> None:
    page = await get_analysis_page_data(
        "600519",
        user_id=1,
        cache_ttl=60,
        section_timeout_seconds=1.0,
        loaders=AnalysisPageLoaders(
            stock_info=_raise,
            kline=_raise,
            intraday=_raise,
            valuation=_raise,
            cached_analysis=_empty_cached,
        ),
    )
    assert {"stock_info", "kline", "intraday", "valuation"} <= set(page.unavailable_sections)
    assert page.partial is True


async def test_page_data_marks_timed_out_sections_unavailable() -> None:
    page = await get_analysis_page_data(
        "600519",
        user_id=1,
        cache_ttl=60,
        section_timeout_seconds=0.01,
        loaders=AnalysisPageLoaders(
            stock_info=_slow,
            kline=_slow,
            intraday=_slow,
            valuation=_slow,
            cached_analysis=_slow,
        ),
    )
    assert {"stock_info", "kline", "intraday", "valuation", "cached_analysis"} <= set(page.unavailable_sections)


async def test_page_data_skips_valuation_for_hk_and_flags_it() -> None:
    """港股没有 A 股口径估值接口：不发起请求，但必须显式标记不可用。"""
    page = await get_analysis_page_data(
        "00700",
        user_id=1,
        cache_ttl=60,
        section_timeout_seconds=1.0,
        loaders=AnalysisPageLoaders(
            stock_info=_raise,
            kline=_raise,
            intraday=_raise,
            valuation=_unexpected,
            cached_analysis=_empty_cached,
        ),
    )
    assert "valuation" in page.unavailable_sections
    assert page.valuation is None
