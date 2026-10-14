"""个股估值分级缓存与预热机制的单元测试。"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.financial_data.stock.valuation import detail
from app.financial_data.stock.valuation.schemas import (
    ValuationDetail,
    ValuationFundamentals,
    ValuationMultiples,
    ValuationPeerSummary,
    ValuationPercentiles,
)


def _build_dummy_valuation_detail(code: str = "600519") -> ValuationDetail:
    return ValuationDetail(
        code=code,
        report_date="2026-06-30",
        current_price=1600.0,
        market_cap=2000000000000.0,
        total_shares=1250000000.0,
        industry="白酒",
        multiples=ValuationMultiples(pe_ttm=25.0, pb=8.0, ps_ttm=12.0, peg=1.2),
        percentiles=ValuationPercentiles(pe_3y=30.0, pb_3y=40.0, ps_3y=35.0),
        fundamentals=ValuationFundamentals(),
        peer_summary=ValuationPeerSummary(),
        fair_values={},
        blended_fair_value=1700.0,
        fair_value_range=(1500.0, 1900.0),
        valuation_view="估值合理",
        valuation_summary="各方法综合处于合理区间",
    )


@pytest.mark.asyncio
async def test_valuation_l2_disk_cache_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    """当 L1 内存缓存未命中但 L2 磁盘快照存在时，应直接命中磁盘快照并写入 L1，避免网络开销。"""
    dummy = _build_dummy_valuation_detail("600519")
    monkeypatch.setattr(detail.cache, "get", lambda key: None)
    set_calls = []
    monkeypatch.setattr(detail.cache, "set", lambda k, v, ttl=None: set_calls.append((k, v)))

    # Mock L2 磁盘快照读取命中
    monkeypatch.setattr(detail, "_read_disk_snapshot", lambda code, ignore_date=False: dummy)

    # 确保不触发真正的上游网络请求
    fetch_mock = AsyncMock()
    monkeypatch.setattr(detail, "_fetch_valuation_detail_inputs", fetch_mock)

    res = await detail.get_valuation_detail("600519")
    assert res.code == "600519"
    assert res.blended_fair_value == 1700.0
    fetch_mock.assert_not_called()
    assert len(set_calls) > 0


@pytest.mark.asyncio
async def test_valuation_fallback_to_stale_l2_on_upstream_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """当上游网络抓取全部失败时，应优雅回退历史 L2 磁盘快照而不是 500 报错。"""
    dummy = _build_dummy_valuation_detail("600519")
    monkeypatch.setattr(detail.cache, "get", lambda key: None)

    # 当天快照不存在，但历史快照存在
    def mock_read(code, ignore_date=False):
        if ignore_date:
            return dummy
        return None

    monkeypatch.setattr(detail, "_read_disk_snapshot", mock_read)
    monkeypatch.setattr(
        detail,
        "_fetch_valuation_detail_inputs",
        AsyncMock(side_effect=RuntimeError("上游服务宕机")),
    )

    res = await detail.get_valuation_detail("600519")
    assert res.code == "600519"
    assert res.valuation_view == "估值合理"


@pytest.mark.asyncio
async def test_warm_up_valuation_details(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证批量预热逻辑能够按标的并发预热并统计成功/失败状态。"""
    requested = []

    async def mock_get(code: str):
        requested.append(code)
        if code == "FAIL_CODE":
            raise RuntimeError("upstream timeout")
        return _build_dummy_valuation_detail(code)

    monkeypatch.setattr(detail, "get_valuation_detail", mock_get)

    stats = await detail.warm_up_valuation_details(["600519", "000001", "FAIL_CODE"])
    assert stats == {"succeeded": 2, "failed": 1}
    assert requested == ["600519", "000001", "FAIL_CODE"]


def test_lifecycle_registers_stock_valuation_snapshot_refresh() -> None:
    """生命周期注册表中必须包含自选/持仓估值快照预热任务。"""
    from app.runtime import lifecycle

    sig = inspect.signature(lifecycle.build_background_task_specs)
    assert "stock_valuation_snapshot_refresh" in sig.parameters

    specs = lifecycle.build_background_task_specs(
        settings_provider=MagicMock(),
        supervised_once=MagicMock(),
        industry_mapping_prewarm=MagicMock(),
        stock_name_map_prewarm=MagicMock(),
        hk_stock_search_prewarm=MagicMock(),
        us_macro_prewarm=MagicMock(),
        national_team_price_prewarm=MagicMock(),
        industry_mapping_refresh=MagicMock(),
        wal_checkpoint=MagicMock(),
        database_backup=MagicMock(),
        twitter_feed_refresh=MagicMock(),
        potential_stock_daily=MagicMock(),
        market_daily_bar_refresh=MagicMock(),
        market_daily_backfill_worker=MagicMock(),
        sge_gold_snapshot_refresh=MagicMock(),
        tdxhub_bestip_refresh=MagicMock(),
        stock_valuation_snapshot_refresh=MagicMock(),
        bot_job_worker=MagicMock(),
        quant_strategy_reload=MagicMock(),
        quant_job_worker=MagicMock(),
        workflow_job_worker=MagicMock(),
    )
    names = {s.name for s in specs}
    assert "stock_valuation_snapshot_refresh" in names
