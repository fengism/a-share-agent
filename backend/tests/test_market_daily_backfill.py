from datetime import date
from pathlib import Path

import pytest

from app.domain.market import KlineItem
from app.financial_data.stock.profile.exchange_master import ExchangeStockMaster, ExchangeStockRecord
from app.financial_data.stock.quotes.historical import (
    HistoricalBarCandidates,
    HistoricalBarSet,
    HistoricalSourceFailure,
)
from app.modules.market_daily import backfill
from app.modules.market_daily.backfill import (
    HistoricalSourceAvailabilityError,
    HistoricalSourceConsistencyError,
    MarketDailyBackfillService,
    _records_from_history,
    _select_validated_candidate,
)
from app.modules.market_daily.models import MarketDailyBackfillRequest
from app.modules.market_daily.repository import MarketDailyBarRepository


def _master() -> ExchangeStockMaster:
    return ExchangeStockMaster(
        records=[
            ExchangeStockRecord("600519", "贵州茅台", "SH", "主板", None, "2001-08-27", None, None, "test"),
            ExchangeStockRecord("301000", "测试新股", "SZ", "创业板", None, "2027-01-01", None, None, "test"),
        ],
        failed_exchanges={},
        stale_exchanges=[],
    )


def _history(volume: float = 1000, amount: float = 10_500, source: str = "test") -> HistoricalBarSet:
    return HistoricalBarSet(
        code="600519",
        period="daily",
        adjust="",
        source=source,
        adjustment_verified=True,
        data_hash="hash",
        items=[KlineItem(code="600519", date="2026-09-30", open=10, high=11, low=9, close=10.5, volume=volume, amount=amount)],
    )


def test_records_from_history_preserves_provider_share_volume() -> None:
    records = _records_from_history("600519", "贵州茅台", _history(volume=1000, amount=10_500))
    assert records[0].volume == 1000


def test_cross_source_validation_accepts_consistent_candidates() -> None:
    validated = _select_validated_candidate(
        HistoricalBarCandidates(candidates=[_history(source="tdxhub"), _history(volume=1001, amount=10_501, source="tencent")], failures=[])
    )
    assert validated.primary.source == "tdxhub"
    assert validated.score > 95


def test_cross_source_validation_rejects_price_conflict() -> None:
    base_conflict = _history()
    conflict = HistoricalBarSet(
        code=base_conflict.code,
        period=base_conflict.period,
        adjust=base_conflict.adjust,
        source="conflict",
        adjustment_verified=True,
        data_hash="conflict-hash",
        items=base_conflict.items,
    )
    conflict.items[0].close = 9.5
    conflict.items[0].low = 9.0
    with pytest.raises(HistoricalSourceConsistencyError, match="OHLC 偏差过大"):
        _select_validated_candidate(
            HistoricalBarCandidates(candidates=[_history(), conflict], failures=[])
        )


def test_cross_source_validation_preserves_source_priority() -> None:
    tdx = _history(volume=1000, amount=10_500, source="tdxhub")
    tencent = _history(volume=1002, amount=10_505, source="tencent")
    sina = _history(volume=1001, amount=10_501, source="akshare-sina")
    selected = _select_validated_candidate(
        HistoricalBarCandidates(candidates=[tdx, tencent, sina], failures=[])
    )
    assert selected.primary.source == "tdxhub"


def test_cross_source_validation_uses_consistent_pair_when_primary_conflicts() -> None:
    conflict = HistoricalBarSet(
        code="600519", period="daily", adjust="", source="conflict",
        adjustment_verified=True, data_hash="conflict",
        items=[KlineItem(code="600519", date="2026-09-30", open=8, high=9, low=7, close=8.5, volume=1000, amount=8500)],
    )
    secondary = _history()
    third = HistoricalBarSet(
        code="600519", period="daily", adjust="", source="third",
        adjustment_verified=True, data_hash="third",
        items=[KlineItem(code="600519", date="2026-09-30", open=10, high=11, low=9, close=10.5, volume=1001, amount=10501)],
    )
    selected = _select_validated_candidate(
        HistoricalBarCandidates(candidates=[conflict, secondary, third], failures=[])
    )
    assert selected.primary.source == "test"
    assert selected.secondary.source == "third"


def test_cross_source_validation_rejects_same_source_family() -> None:
    sina = HistoricalBarSet(
        code="600519", period="daily", adjust="", source="akshare-sina",
        adjustment_verified=True, data_hash="sina-a", items=_history().items,
    )
    sina_direct = HistoricalBarSet(
        code="600519", period="daily", adjust="", source="sina-direct-unadjusted",
        adjustment_verified=True, data_hash="sina-b", items=_history().items,
    )
    with pytest.raises(HistoricalSourceConsistencyError, match="非独立来源"):
        _select_validated_candidate(
            HistoricalBarCandidates(candidates=[sina, sina_direct], failures=[])
        )


def test_zero_volume_bars_can_cross_validate() -> None:
    first = _history(volume=0, amount=0, source="tdxhub")
    second = _history(volume=0, amount=0, source="tencent")
    selected = _select_validated_candidate(
        HistoricalBarCandidates(candidates=[first, second], failures=[])
    )
    assert selected.score == 100


def test_insufficient_sources_from_connection_failure_is_retryable() -> None:
    candidates = HistoricalBarCandidates(
        candidates=[_history(source="tdxhub")],
        failures=[HistoricalSourceFailure(
            source_label="腾讯财经", error_type="ConnectionError", error_message="connection refused",
        )],
    )
    with pytest.raises(HistoricalSourceAvailabilityError, match="上游暂时无法提供"):
        _select_validated_candidate(candidates)


def test_upsert_historical_bars_preserves_or_overwrites_existing(tmp_path: Path) -> None:
    repo = MarketDailyBarRepository(tmp_path / "market_daily.sqlite3")
    repo.initialize()
    original = _records_from_history("600519", "贵州茅台", _history())[0]
    assert repo.upsert_historical_bars([original]) == 1

    changed_history = _history(volume=1200, amount=12_600)
    changed_history.items[0].close = 10.6
    changed_history.items[0].high = 11.0
    changed = _records_from_history("600519", "贵州茅台", changed_history)[0]
    assert repo.upsert_historical_bars([changed], overwrite_existing=False) == 0
    assert repo.list_bars(
        market="cn", instrument_type="stock", code="600519",
        start_date=date(2026, 9, 30), end_date=date(2026, 9, 30),
    )[0].close == 10.5

    assert repo.upsert_historical_bars([changed], overwrite_existing=True) == 1
    updated = repo.list_bars(
        market="cn", instrument_type="stock", code="600519",
        start_date=date(2026, 9, 30), end_date=date(2026, 9, 30),
    )[0]
    assert updated.close == 10.6
    assert updated.revision == 2


def test_backfill_completion_is_failed_when_every_instrument_failed(tmp_path: Path) -> None:
    repo = MarketDailyBarRepository(tmp_path / "market_daily.sqlite3")
    service = MarketDailyBackfillService(repo)
    repo.initialize()
    request = MarketDailyBackfillRequest(start_date=date(2026, 9, 1), end_date=date(2026, 9, 30))
    job = service._create_job(request, _master().records[:1])
    claimed = service._claim_job()
    assert claimed is not None
    item = service._claim_item(job.job_id)
    assert item is not None
    service._finish_item(job.job_id, item["code"], stored=0, source=None, error="offline")
    service._complete_job(job.job_id)
    assert service._get(job.job_id).status == "failed"


@pytest.mark.asyncio
async def test_create_rejects_when_an_active_job_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = MarketDailyBarRepository(tmp_path / "market_daily.sqlite3")
    service = MarketDailyBackfillService(repo)
    repo.initialize()
    request = MarketDailyBackfillRequest(start_date=date(2026, 9, 1), end_date=date(2026, 9, 30))
    service._create_job(request, _master().records[:1])

    async def should_not_load_master():
        raise AssertionError("存在活跃任务时不应再访问股票主表")

    monkeypatch.setattr(backfill, "get_exchange_stock_master", should_not_load_master)
    with pytest.raises(Exception, match="已有历史回填任务正在执行"):
        await service.create(request)


@pytest.mark.asyncio
async def test_backfill_job_persists_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = MarketDailyBarRepository(tmp_path / "market_daily.sqlite3")
    service = MarketDailyBackfillService(repo)
    monkeypatch.setattr(backfill, "get_exchange_stock_master", lambda: _async_value(_master()))
    monkeypatch.setattr(
        backfill,
        "get_historical_bar_candidates",
        lambda *args, **kwargs: _async_value(
            HistoricalBarCandidates(candidates=[_history(source="tdxhub"), _history(source="tencent")], failures=[])
        ),
    )

    job = await service.create(MarketDailyBackfillRequest(start_date=date(2026, 9, 1), end_date=date(2026, 9, 30)))
    assert job.total_instruments == 1
    claimed = service._claim_job()
    assert claimed is not None
    await service._process_job(claimed)

    completed = await service.get(job.job_id)
    assert completed.status == "succeeded"
    assert completed.completed_instruments == 1
    assert completed.succeeded_instruments == 1
    assert completed.retryable_failed_instruments == 0
    assert completed.average_quality_score is not None
    assert completed.average_quality_score > 95
    assert completed.stored_bars == 1
    bars = repo.list_bars(market="cn", instrument_type="stock", code="600519", start_date=date(2026, 9, 1), end_date=date(2026, 9, 30))
    assert len(bars) == 1
    assert bars[0].verification_status == "confirmed"


async def _async_value(value):
    return value


def test_retry_failed_requeues_only_failed_instruments(tmp_path: Path) -> None:
    repo = MarketDailyBarRepository(tmp_path / "market_daily.sqlite3")
    service = MarketDailyBackfillService(repo)
    repo.initialize()
    request = MarketDailyBackfillRequest(start_date=date(2026, 9, 1), end_date=date(2026, 9, 30))
    job = service._create_job(request, _master().records)
    claimed = service._claim_job()
    assert claimed is not None

    first = service._claim_item(job.job_id)
    second = service._claim_item(job.job_id)
    assert first is not None and second is not None
    service._finish_item(job.job_id, first["code"], stored=1, source="test", error=None)
    service._finish_item(
        job.job_id,
        second["code"],
        stored=0,
        source=None,
        failure_kind="upstream_unavailable",
        error="offline",
    )
    service._complete_job(job.job_id)
    failed_job = service._get(job.job_id)
    assert failed_job.status == "failed"
    assert failed_job.retryable_failed_instruments == 1
    assert failed_job.failure_details[0]["kind"] == "upstream_unavailable"
    assert failed_job.failure_details[0]["retryable"] is True

    service._retry_failed(job.job_id)
    retried = service._get(job.job_id)
    assert retried.status == "pending"
    assert retried.completed_instruments == 1
    assert retried.succeeded_instruments == 1
    assert retried.failed_instruments == 0
    assert retried.stored_bars == 1
    assert retried.failure_details == []

    reclaimed = service._claim_job()
    assert reclaimed is not None
    pending = service._claim_item(job.job_id)
    assert pending is not None
    assert pending["code"] == second["code"]


def test_source_inconsistency_is_not_retryable(tmp_path: Path) -> None:
    repo = MarketDailyBarRepository(tmp_path / "market_daily.sqlite3")
    service = MarketDailyBackfillService(repo)
    repo.initialize()
    request = MarketDailyBackfillRequest(start_date=date(2026, 9, 1), end_date=date(2026, 9, 30))
    job = service._create_job(request, _master().records[:1])
    assert service._claim_job() is not None
    item = service._claim_item(job.job_id)
    assert item is not None
    service._finish_item(
        job.job_id, item["code"], stored=0, source=None,
        failure_kind="source_inconsistent", error="OHLC conflict",
    )
    service._complete_job(job.job_id)
    failed = service._get(job.job_id)
    assert failed.status == "failed"
    assert failed.retryable_failed_instruments == 0
    assert failed.failure_details[0]["kind"] == "source_inconsistent"
    with pytest.raises(Exception, match="没有失败股票需要重试"):
        service._retry_failed(job.job_id)
