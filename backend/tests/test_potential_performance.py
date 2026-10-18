"""潜力股历史表现复盘的收益、超额与缓存测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.potential import performance
from app.modules.potential.schemas import PotentialDailyResult, PotentialStockItem


def _bar(date_text: str, close: float):
    return SimpleNamespace(date=date_text, close=close)


def _result() -> PotentialDailyResult:
    return PotentialDailyResult(
        date="2026-10-16",
        generated_at="2026-10-16T16:00:00",
        universe_size=300,
        evaluated=280,
        failed_count=2,
        items=[
            PotentialStockItem(code="600001", name="强势股", industry="制造业", price=10.0),
            PotentialStockItem(code="600002", name="普通股", industry="采矿业", price=20.0),
        ],
    )


@pytest.mark.asyncio
async def test_compute_performance_returns_returns_and_excess(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(performance, "_PERFORMANCE_DIR", tmp_path)
    monkeypatch.setattr(performance.repository, "load_potential_result", lambda date: _result())
    dates = ["2026-10-15", "2026-10-16", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"]
    stock_closes = {
        "600001": [10.0, 10.0, 11.0, 12.0, 11.0, 13.0, 14.0],
        "600002": [20.0, 20.0, 19.0, 18.0, 19.0, 20.0, 21.0],
    }
    calls = {"bars": 0}

    async def fake_bars(code, start_date, end_date, period, adjust):
        calls["bars"] += 1
        return SimpleNamespace(items=[_bar(day, close) for day, close in zip(dates, stock_closes[code])])

    async def fake_index(symbol, period, start_date, end_date):
        return SimpleNamespace(items=[_bar(day, close) for day, close in zip(dates, [100.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0])])

    monkeypatch.setattr(performance, "get_historical_bars", fake_bars)
    monkeypatch.setattr(performance, "get_index_kline", fake_index)

    summary = await performance.compute_potential_performance("2026-10-16", 5)

    assert summary is not None
    assert summary.item_count == 2
    assert summary.evaluated_count == 2
    assert summary.benchmark_return_pct == pytest.approx(5.0)
    assert summary.win_rate == pytest.approx(1.0)
    assert summary.average_return_pct == pytest.approx(22.5)
    assert summary.median_return_pct == pytest.approx(22.5)
    assert summary.average_excess_pct == pytest.approx(17.5)
    by_code = {item.code: item for item in summary.items}
    assert by_code["600001"].return_pct == pytest.approx(40.0)
    assert by_code["600001"].excess_return_pct == pytest.approx(35.0)
    assert by_code["600002"].max_drawdown_pct == pytest.approx(-10.0)

    cached = await performance.compute_potential_performance("2026-10-16", 5)
    assert cached is not None
    assert calls["bars"] == 2  # 第二次命中缓存，不再请求行情


@pytest.mark.asyncio
async def test_compute_performance_reports_insufficient_forward_data(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(performance, "_PERFORMANCE_DIR", tmp_path)
    monkeypatch.setattr(performance.repository, "load_potential_result", lambda date: _result())

    async def short_bars(code, start_date, end_date, period, adjust):
        return SimpleNamespace(items=[_bar("2026-10-16", 10.0), _bar("2026-10-19", 11.0)])

    async def fake_index(symbol, period, start_date, end_date):
        return SimpleNamespace(items=[_bar("2026-10-16", 100.0)])

    monkeypatch.setattr(performance, "get_historical_bars", short_bars)
    monkeypatch.setattr(performance, "get_index_kline", fake_index)

    summary = await performance.compute_potential_performance("2026-10-16", 5)

    assert summary is not None
    assert summary.evaluated_count == 0
    assert summary.win_rate is None
    assert summary.message is not None and "前瞻数据" in summary.message


@pytest.mark.asyncio
async def test_compute_performance_returns_none_for_missing_result(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(performance, "_PERFORMANCE_DIR", tmp_path)
    monkeypatch.setattr(performance.repository, "load_potential_result", lambda date: None)

    assert await performance.compute_potential_performance("2026-10-16", 5) is None
    assert await performance.compute_potential_performance("not-a-date", 5) is None
