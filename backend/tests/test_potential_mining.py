"""潜力股挖掘的信号聚合、质量叠加、行业分散与市场环境测试。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from app.financial_data.market.trading_session import SHANGHAI_TIMEZONE
from app.financial_data.stock.fundamentals.schemas import FinancialMetrics
from app.modules.potential import fundamentals, regime, screening, service, signals, themes
from app.modules.potential.schemas import PotentialDailyResult, PotentialStockItem
from app.modules.quant.public import CURATED_STRATEGY_KEYS


def _master(code: str, industry: str = "测试行业", board: str = "主板", listing_date: str = "2020-01-01"):
    return SimpleNamespace(code=code, industry=industry, board=board, listing_date=listing_date)


def _spot_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _bar(
    close: float,
    *,
    high: float | None = None,
    low: float | None = None,
    open_: float | None = None,
    volume: float = 1_000_000,
    date: str = "2026-10-16",
    change_pct: float | None = None,
):
    return SimpleNamespace(
        close=close,
        high=high if high is not None else close * 1.01,
        low=low if low is not None else close * 0.99,
        open=open_ if open_ is not None else close * 0.995,
        volume=volume,
        date=date,
        change_pct=change_pct,
    )


def test_select_candidates_includes_industry_and_quality_pool() -> None:
    """候选池应同时覆盖头部、活跃中盘和质量中盘，并带上行业/估值字段。"""
    frame = _spot_frame(
        [
            {
                "代码": "600001",
                "名称": "头部龙头",
                "最新价": 10.0,
                "涨跌幅": 1.0,
                "成交额": 100e8,
                "换手率": 1.0,
                "市盈率-动态": 15.0,
                "市净率": 2.0,
                "总市值": 2000e8,
                "流通市值": 4000e8,
                "今开": 9.9,
                "最高": 10.2,
                "最低": 9.8,
                "昨收": 9.9,
                "成交量": 1e8,
            },
            {
                "代码": "600002",
                "名称": "质量中盘",
                "最新价": 20.0,
                "涨跌幅": 2.0,
                "成交额": 5e8,
                "换手率": 3.0,
                "市盈率-动态": 25.0,
                "市净率": 3.0,
                "总市值": 200e8,
                "流通市值": 180e8,
                "今开": 19.5,
                "最高": 20.5,
                "最低": 19.4,
                "昨收": 19.6,
                "成交量": 2e7,
            },
            {
                "代码": "600003",
                "名称": "活跃中盘",
                "最新价": 15.0,
                "涨跌幅": 5.0,
                "成交额": 8e8,
                "换手率": 10.0,
                "市盈率-动态": 200.0,
                "市净率": 12.0,
                "总市值": 100e8,
                "流通市值": 90e8,
                "今开": 14.5,
                "最高": 15.2,
                "最低": 14.4,
                "昨收": 14.3,
                "成交量": 5e7,
            },
            {
                "代码": "600004",
                "名称": "ST风险",
                "最新价": 5.0,
                "涨跌幅": 1.0,
                "成交额": 50e8,
                "换手率": 5.0,
                "市盈率-动态": 10.0,
                "市净率": 1.0,
                "总市值": 50e8,
                "流通市值": 40e8,
                "今开": 5.0,
                "最高": 5.1,
                "最低": 4.9,
                "昨收": 5.0,
                "成交量": 1e8,
            },
            {
                "代码": "600005",
                "名称": "次新股",
                "最新价": 30.0,
                "涨跌幅": 3.0,
                "成交额": 20e8,
                "换手率": 6.0,
                "市盈率-动态": 30.0,
                "市净率": 4.0,
                "总市值": 100e8,
                "流通市值": 80e8,
                "今开": 29.0,
                "最高": 30.5,
                "最低": 28.8,
                "昨收": 29.1,
                "成交量": 3e7,
            },
            {
                "代码": "600006",
                "名称": "低流动性",
                "最新价": 8.0,
                "涨跌幅": 1.0,
                "成交额": 0.2e8,
                "换手率": 1.0,
                "市盈率-动态": 20.0,
                "市净率": 2.0,
                "总市值": 60e8,
                "流通市值": 50e8,
                "今开": 8.0,
                "最高": 8.1,
                "最低": 7.9,
                "昨收": 7.9,
                "成交量": 1e6,
            },
        ]
    )
    masters = [
        _master("600001"),
        _master("600002"),
        _master("600003"),
        _master("600004"),
        _master("600005", listing_date="2026-07-01"),
        _master("600006"),
    ]

    candidates = screening.select_candidates(frame, masters)
    by_code = {candidate["code"]: candidate for candidate in candidates}

    assert {"600001", "600002", "600003"} <= set(by_code)
    assert "600004" not in by_code  # ST
    assert "600005" not in by_code  # 次新
    assert "600006" not in by_code  # 低流动性
    assert by_code["600002"]["industry"] == "测试行业"
    assert by_code["600002"]["pe"] == pytest.approx(25.0)
    assert by_code["600002"]["pb"] == pytest.approx(3.0)
    assert by_code["600002"]["market_cap"] == pytest.approx(200.0)


def test_annualized_roe_handles_interim_reports() -> None:
    assert fundamentals._annualized_roe(0.05, "2026-06-30") == pytest.approx(0.10)
    assert fundamentals._annualized_roe(0.05, "2026-03-31") == pytest.approx(0.20)
    assert fundamentals._annualized_roe(0.05, "2026-12-31") == pytest.approx(0.05)
    assert fundamentals._annualized_roe(None, "2026-06-30") is None


def test_fundamental_score_rewards_quality_and_penalizes_risk() -> None:
    good_metrics = {
        "净资产收益率": 0.06,
        "净利润同比": 35.0,
        "营收同比": 22.0,
        "资产负债率": 0.30,
        "现净比": 1.2,
    }
    bad_metrics = {
        "净资产收益率": -0.02,
        "净利润同比": -40.0,
        "营收同比": -10.0,
        "资产负债率": 0.75,
        "现净比": -1.0,
    }

    good_score, good_flags, good_summary = fundamentals._fundamental_score(good_metrics, "2026-06-30")
    bad_score, bad_flags, _ = fundamentals._fundamental_score(bad_metrics, "2026-06-30")

    assert good_score > 1.0
    assert good_flags == []
    assert "ROE" in good_summary
    assert bad_score <= -1.0
    assert "ROE为负" in bad_flags
    assert "净利大幅下滑" in bad_flags
    assert "经营现金流为负" in bad_flags


@pytest.mark.asyncio
async def test_fundamental_overlay_updates_score_and_handles_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [
        {
            "code": "600001",
            "score": 4.0,
            "signal_score": 3.0,
            "quality_score": 1.0,
            "fundamental_score": 0.0,
            "theme_score": 0.4,
            "risk_flags": [],
            "reason": "命中多头趋势",
            "amount": 10.0,
        },
        {
            "code": "600002",
            "score": 3.0,
            "signal_score": 2.0,
            "quality_score": 1.0,
            "fundamental_score": 0.0,
            "risk_flags": [],
            "reason": "命中底部放量",
            "amount": 5.0,
        },
    ]

    async def fake_metrics(code: str):
        if code == "600002":
            raise RuntimeError("upstream timeout")
        return FinancialMetrics(
            code=code,
            latest_report_date="2026-06-30",
            metrics={
                "净资产收益率": 0.06,
                "净利润同比": 35.0,
                "营收同比": 22.0,
                "资产负债率": 0.30,
                "现净比": 1.2,
            },
        )

    monkeypatch.setattr(fundamentals, "get_financial_metrics", fake_metrics)
    succeeded, failed = await fundamentals._apply_fundamental_overlay(items, service.date(2026, 10, 16), limit=10)

    assert (succeeded, failed) == (1, 1)
    assert items[0]["fundamental_score"] > 1.0
    assert items[0]["score"] == pytest.approx(
        items[0]["signal_score"]
        + items[0]["quality_score"]
        + items[0]["theme_score"]
        + items[0]["fundamental_score"]
    )
    assert "ROE" in items[0]["reason"]
    assert items[1]["fundamental_score"] == 0.0
    assert "财务数据缺失" in items[1]["risk_flags"]


@pytest.mark.asyncio
async def test_fundamental_overlay_rejects_future_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    """历史回填时，报告期晚于挖掘日的财务数据不能使用。"""
    items = [
        {
            "code": "600001",
            "score": 4.0,
            "signal_score": 3.0,
            "quality_score": 1.0,
            "fundamental_score": 0.0,
            "risk_flags": [],
            "reason": "命中多头趋势",
            "amount": 10.0,
        }
    ]

    async def future_metrics(code: str):
        return FinancialMetrics(
            code=code,
            latest_report_date="2027-03-31",
            metrics={"净资产收益率": 0.10, "净利润同比": 30.0},
        )

    monkeypatch.setattr(fundamentals, "get_financial_metrics", future_metrics)
    succeeded, failed = await fundamentals._apply_fundamental_overlay(items, service.date(2026, 10, 16))

    assert (succeeded, failed) == (0, 1)
    assert items[0]["fundamental_score"] == 0.0
    assert "财务数据滞后" in items[0]["risk_flags"]


@pytest.fixture
def reset_manual_run_state():
    service._manual_run_task = None
    service._manual_run_state.update(
        status="idle", date=None, started_at=None, finished_at=None, error=None
    )
    yield
    service._manual_run_task = None


def test_mining_run_status_starts_idle(reset_manual_run_state) -> None:
    status = service.mining_run_status()
    assert status.running is False
    assert status.status == "idle"


@pytest.mark.asyncio
async def test_background_mining_run_dedupes_and_reports_completed(
    monkeypatch: pytest.MonkeyPatch, reset_manual_run_state
) -> None:
    async def fake_run(force: bool = False, now=None):
        await asyncio.sleep(0.05)
        return PotentialDailyResult(date="2026-10-16", generated_at="2026-10-16T16:00:00")

    monkeypatch.setattr(service, "run_daily_mining", fake_run)

    first = await service.start_daily_mining_background()
    second = await service.start_daily_mining_background()

    assert first.running is True and first.status == "running"
    assert second.running is True
    task = service._manual_run_task
    assert task is not None
    await task

    status = service.mining_run_status()
    assert status.running is False
    assert status.status == "completed"
    assert status.date == "2026-10-16"


@pytest.mark.asyncio
async def test_background_mining_run_reports_failure(
    monkeypatch: pytest.MonkeyPatch, reset_manual_run_state
) -> None:
    async def fake_run(force: bool = False, now=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "run_daily_mining", fake_run)

    await service.start_daily_mining_background()
    task = service._manual_run_task
    assert task is not None
    await task

    status = service.mining_run_status()
    assert status.running is False
    assert status.status == "failed"
    assert status.error == "RuntimeError"


@pytest.mark.asyncio
async def test_run_daily_mining_dedupes_concurrent_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """同一交易日的并发触发只跑一次全量挖掘。"""
    async def fake_resolve(now):
        return service.date(2026, 10, 16)

    monkeypatch.setattr(service, "resolve_potential_market_date", fake_resolve)
    monkeypatch.setattr(service.repository, "has_potential_result", lambda date: False)
    monkeypatch.setattr(service.repository, "load_potential_result", lambda date: None)
    calls = {"count": 0}

    async def fake_mine(market_date):
        calls["count"] += 1
        await asyncio.sleep(0.05)
        return PotentialDailyResult(date=market_date.isoformat(), generated_at="2026-10-16T16:00:00")

    monkeypatch.setattr(service, "_mine_and_save", fake_mine)

    # Fix the clock after the 15:10 Shanghai cutoff so the test is independent of
    # the machine's local time/UTC offset.
    fixed_now = datetime(2026, 10, 16, 16, 0)
    results = await asyncio.gather(
        service.run_daily_mining(now=fixed_now),
        service.run_daily_mining(now=fixed_now),
        service.run_daily_mining(now=fixed_now),
    )

    assert calls["count"] == 1
    assert all(result is results[0] for result in results)


def test_market_emotion_computes_breadth_and_limits() -> None:
    frame = pd.DataFrame(
        [
            {"代码": "600001", "涨跌幅": 10.0},
            {"代码": "600002", "涨跌幅": 5.0},
            {"代码": "600003", "涨跌幅": -10.0},
            {"代码": "600004", "涨跌幅": -2.0},
            {"代码": "600005", "涨跌幅": 0.0},
            {"代码": "300001", "涨跌幅": 20.0},
        ]
    )
    masters = [
        _master("600001"),
        _master("600002"),
        _master("600003"),
        _master("600004"),
        _master("600005"),
        _master("300001", board="创业板"),
    ]

    emotion = regime._market_emotion(frame, masters)

    assert emotion["limit_up_count"] == 2
    assert emotion["limit_down_count"] == 1
    assert emotion["advance_ratio"] == pytest.approx(0.6)
    assert emotion["median_change_pct"] == pytest.approx(2.5)
    assert emotion["label"] == "strong"


def test_combine_regime_uses_emotion_to_break_ties() -> None:
    assert regime._combine_regime("bull", "strong") == "bull"
    assert regime._combine_regime("bull", "weak") == "neutral"
    assert regime._combine_regime("bear", "weak") == "bear"
    assert regime._combine_regime("bear", "strong") == "neutral"
    assert regime._combine_regime("neutral", "strong") == "bull"
    assert regime._combine_regime("neutral", "weak") == "bear"
    assert regime._combine_regime("neutral", "neutral") == "neutral"


def test_theme_score_is_capped() -> None:
    assert themes._theme_score(None) == 0.0
    assert themes._theme_score(0.5) == pytest.approx(0.3)
    assert themes._theme_score(1.0) == pytest.approx(0.6)
    assert themes._theme_score(3.0) == pytest.approx(0.6)


@pytest.mark.asyncio
async def test_load_theme_map_maps_hot_concepts_to_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_concepts():
        return [
            {"rank": 1, "name": "低空经济", "change_pct": 4.0},
            {"rank": 2, "name": "军工", "change_pct": 2.0},
        ]

    async def fake_industries():
        return [{"rank": 1, "name": "银行", "change_pct": 1.0}]

    async def fake_constituents(name, quote_codes=None):
        mapping = {
            "低空经济": ["600001", "600002"],
            "军工": ["600002"],
            "银行": ["600003"],
        }
        return {"items": [{"code": code} for code in mapping.get(name, [])]}

    monkeypatch.setattr(themes, "get_ths_hot_concept", fake_concepts)
    monkeypatch.setattr(themes, "get_ths_hot_industry", fake_industries)
    monkeypatch.setattr(themes, "get_concept_constituents", fake_constituents)

    theme_map, display_themes = await themes._load_theme_map({"600001", "600002", "600003", "600004"})

    assert display_themes[:2] == ["低空经济", "军工"]
    assert theme_map["600001"]["themes"] == ["低空经济"]
    assert set(theme_map["600002"]["themes"]) == {"低空经济", "军工"}
    assert theme_map["600002"]["strength"] > theme_map["600003"]["strength"]
    assert "600004" not in theme_map


def test_evaluate_candidate_includes_theme_score(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = [_bar(10.0, date="2026-10-15"), _bar(10.5, date="2026-10-16", change_pct=5.0)]
    candidate = {
        "code": "600002",
        "name": "测试股票",
        "industry": "制造业",
        "board": "主板",
        "change_pct": 5.0,
        "pe": 20.0,
        "pb": 2.0,
        "market_cap": 100.0,
        "theme_strength": 1.0,
        "themes": ["低空经济"],
        "amount": 5.0,
    }
    monkeypatch.setattr(
        signals,
        "_evaluate_strategies",
        lambda bars, snapshots, regime: (["多头趋势"], "2026-10-16", 0, 2.0, ["trend"]),
    )
    monkeypatch.setattr(
        signals,
        "_technical_profile",
        lambda bars, candidate: {"quality_score": 0.8, "risk_flags": [], "hard_skip": False},
    )

    item = signals._evaluate_candidate(bars, {}, candidate, "bull")

    assert item is not None
    assert item["theme_score"] == pytest.approx(0.6)
    assert item["themes"] == ["低空经济"]
    assert item["score"] == pytest.approx(3.4)
    assert "题材" in item["reason"]


def test_every_curated_strategy_has_a_signal_family() -> None:
    """新增精选策略时必须显式归类，不能静默落进 other 族。"""
    assert sorted(CURATED_STRATEGY_KEYS - set(signals._STRATEGY_FAMILIES)) == []


def test_signal_decay_is_continuous() -> None:
    assert signals._signal_decay(0) == pytest.approx(1.5)
    assert signals._signal_decay(2) == pytest.approx(1.3)
    assert signals._signal_decay(5) == pytest.approx(1.0)


def test_evaluate_strategies_caps_correlated_families(monkeypatch: pytest.MonkeyPatch) -> None:
    """同族策略不应无限叠加，跨族命中才拿一致性奖励。"""
    snapshots = {
        "bull_trend": SimpleNamespace(definition=SimpleNamespace(name="多头趋势")),
        "ma_golden_cross": SimpleNamespace(definition=SimpleNamespace(name="均线金叉")),
        "volume_breakout": SimpleNamespace(definition=SimpleNamespace(name="放量突破")),
        "bottom_volume": SimpleNamespace(definition=SimpleNamespace(name="底部放量")),
    }
    monkeypatch.setattr(signals, "build_target_positions", lambda bars, snapshot: [0, 0, 1, 1])
    bars = [_bar(10.0, date=f"2026-10-{day:02d}") for day in range(10, 14)]

    hits, signal_date, signal_age, score, signal_types = signals._evaluate_strategies(
        bars, snapshots, "neutral"
    )

    assert signal_age == 1
    assert signal_date == "2026-10-12"
    assert len(hits) == 4
    assert signal_types == ["breakout", "reversal", "trend"]
    # trend 族封顶 2.0 + reversal 封顶 2.0 + breakout 1.5 + 两族一致性奖励 0.7
    assert score == pytest.approx(6.2)


def test_technical_profile_penalizes_overextension() -> None:
    """短期涨幅过大、偏离 MA20 过多应被硬风控剔除。"""
    closes = [10.0 * (1.02**index) for index in range(80)]
    bars = [
        _bar(
            close,
            high=close * 1.01,
            low=close * 0.99,
            open_=close * 0.995,
            volume=1_000_000 + index * 10_000,
            date=f"2026-{1 + index // 28:02d}-{1 + index % 28:02d}",
        )
        for index, close in enumerate(closes)
    ]
    candidate = {
        "code": "600002",
        "board": "主板",
        "change_pct": 2.0,
        "pe": 20.0,
        "pb": 2.0,
        "market_cap": 100.0,
        "sector_strength": 0.5,
    }

    profile = signals._technical_profile(bars, candidate)

    assert profile["hard_skip"] is True
    assert "偏离MA20过大" in profile["risk_flags"]


def test_technical_profile_flags_one_word_limit_board() -> None:
    """一字涨停无法买入，应直接剔除。"""
    bars = [_bar(10.0, high=10.0, low=10.0, open_=10.0, date=f"2026-10-{day:02d}") for day in range(1, 31)]
    bars[-1] = _bar(11.0, high=11.0, low=11.0, open_=11.0, date="2026-10-31", change_pct=10.0)
    candidate = {
        "code": "600002",
        "board": "主板",
        "change_pct": 10.0,
        "pe": 20.0,
        "pb": 2.0,
        "market_cap": 100.0,
        "sector_strength": 0.5,
    }

    profile = signals._technical_profile(bars, candidate)

    assert profile["hard_skip"] is True
    assert "一字板" in profile["risk_flags"]


def test_diversify_items_caps_single_industry() -> None:
    items = [
        {"code": f"60000{index}", "industry": "半导体", "score": 10 - index}
        for index in range(8)
    ]
    items.append({"code": "600100", "industry": "银行", "score": 1})

    selected = service._diversify_items(items, max_output=10, max_per_industry=4)

    assert [item["code"] for item in selected[:4]] == ["600000", "600001", "600002", "600003"]
    assert "600004" not in {item["code"] for item in selected}
    assert "600100" in {item["code"] for item in selected}


@pytest.mark.asyncio
async def test_resolve_market_regime_detects_bull_and_bear(monkeypatch: pytest.MonkeyPatch) -> None:
    async def rising(symbol, period, start_date, end_date):
        return SimpleNamespace(items=[SimpleNamespace(close=100 + index) for index in range(80)])

    async def falling(symbol, period, start_date, end_date):
        return SimpleNamespace(items=[SimpleNamespace(close=200 - index) for index in range(80)])

    monkeypatch.setattr(regime, "get_index_kline", rising)
    bull, bull_note = await regime._resolve_market_regime(service.date(2026, 10, 16))
    assert bull == "bull"
    assert "沪深300" in bull_note

    monkeypatch.setattr(regime, "get_index_kline", falling)
    bear, bear_note = await regime._resolve_market_regime(service.date(2026, 10, 16))
    assert bear == "bear"
    assert "沪深300" in bear_note


def test_evaluate_candidate_combines_signal_and_quality(monkeypatch: pytest.MonkeyPatch) -> None:
    """最终评分应为信号分 + 质量分，并带上入选理由。"""
    bars = [_bar(10.0, date="2026-10-15"), _bar(10.5, date="2026-10-16", change_pct=5.0)]
    candidate = {
        "code": "600002",
        "name": "测试股票",
        "industry": "半导体",
        "board": "主板",
        "change_pct": 5.0,
        "pe": 20.0,
        "pb": 2.0,
        "market_cap": 100.0,
        "sector_strength": 1.5,
        "amount": 5.0,
        "turnover_pct": 3.0,
    }
    monkeypatch.setattr(
        signals,
        "_evaluate_strategies",
        lambda bars, snapshots, regime: (["多头趋势"], "2026-10-16", 0, 2.0, ["trend"]),
    )
    monkeypatch.setattr(
        signals,
        "_technical_profile",
        lambda bars, candidate: {"quality_score": 0.8, "risk_flags": [], "hard_skip": False},
    )

    item = signals._evaluate_candidate(bars, {}, candidate, "bull")

    assert item is not None
    assert item["score"] == pytest.approx(2.8)
    assert item["signal_score"] == pytest.approx(2.0)
    assert item["quality_score"] == pytest.approx(0.8)
    assert item["fundamental_score"] == pytest.approx(0.0)
    assert item["industry"] == "半导体"
    assert "多头趋势" in item["reason"]


@pytest.mark.asyncio
async def test_run_daily_mining_blocks_weekday_pre_close(monkeypatch: pytest.MonkeyPatch) -> None:
    """工作日收盘前不能拿当日盘中快照回挖上一交易日。"""
    existing = PotentialDailyResult(
        date="2026-10-15",
        generated_at="2026-10-15T16:00:00",
        items=[PotentialStockItem(code="600001", name="已有结果")],
    )
    async def fake_resolve(now):
        return service.date(2026, 10, 15)

    monkeypatch.setattr(service, "resolve_potential_market_date", fake_resolve)
    monkeypatch.setattr(service.repository, "has_potential_result", lambda date: False)
    monkeypatch.setattr(service.repository, "load_potential_result", lambda date: existing)
    called = {"mine": False}

    async def fake_mine(*args, **kwargs):
        called["mine"] = True
        return existing

    monkeypatch.setattr(service, "mine_potential_stocks", fake_mine)
    result = await service.run_daily_mining(
        force=True,
        now=datetime(2026, 10, 16, 10, 0, tzinfo=SHANGHAI_TIMEZONE),
    )

    assert result is existing
    assert called["mine"] is False
