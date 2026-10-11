import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import app.financial_data.stock.quotes.spot_snapshot as spot_snapshot
import app.modules.market_daily.collectors as collectors
from app.financial_data.stock.profile.exchange_master import ExchangeStockMaster, ExchangeStockRecord
from app.infrastructure.providers.sina.provider import (
    SinaDataProvider,
    SinaSnapshotIncompleteError,
    sina_snapshot_health_snapshot,
)
from app.modules.market_daily.models import MarketDailyBarRecord


class _Response:
    def __init__(self, payload, *, status_code: int = 200, text: str | None = None):
        self._payload = payload
        self.status_code = status_code
        self.text = text if text is not None else json.dumps(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _row(code: str, *, ticktime: str = "15:30:00") -> dict:
    return {
        "code": code,
        "name": f"股票{code}",
        "trade": "10.50",
        "settlement": "10.00",
        "open": "10.10",
        "high": "10.80",
        "low": "9.90",
        "volume": 10_000,
        "amount": 104_000,
        "ticktime": ticktime,
    }


def _provider_with_pages(monkeypatch: pytest.MonkeyPatch, pages: dict[int, list[dict] | Exception]) -> SinaDataProvider:
    provider = SinaDataProvider()
    provider.HQ_PAGE_SIZE = 2
    provider.HQ_MAX_PAGES = 5
    provider.HQ_PAGE_MAX_ATTEMPTS = 2
    provider.HQ_RETRY_DELAY_SECONDS = 0
    provider.HQ_MIN_RECORDS = 3

    def get(url, *, params, timeout):
        if "getHQNodeStockCount" in url:
            expected = max(3, sum(len(value) for value in pages.values() if isinstance(value, list)))
            return _Response(str(expected))
        result = pages[int(params["page"])]
        if isinstance(result, Exception):
            raise result
        return _Response(result)

    monkeypatch.setattr(provider._session, "get", get)
    return provider


def test_sina_snapshot_completes_only_on_terminal_short_page(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_pages(
        monkeypatch,
        {1: [_row("600000"), _row("600001")], 2: [_row("600002")]},
    )
    records = provider._load_market_hq_records()
    assert [row["code"] for row in records] == ["600000", "600001", "600002"]
    health = sina_snapshot_health_snapshot()
    assert health["status"] == "healthy"
    assert health["rows"] == 3
    assert health["pages"] == 2


def test_sina_snapshot_rejects_middle_page_failure_without_partial_result(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_pages(
        monkeypatch,
        {1: [_row("600000"), _row("600001")], 2: ConnectionError("offline")},
    )
    with pytest.raises(SinaSnapshotIncompleteError, match="第 2 页连续失败"):
        provider._load_market_hq_records()
    health = sina_snapshot_health_snapshot()
    assert health["status"] == "error"
    assert health["error_type"] == "SinaSnapshotIncompleteError"


def test_sina_snapshot_rejects_duplicate_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_pages(
        monkeypatch,
        {1: [_row("600000"), _row("600001")], 2: [_row("600001")]},
    )
    with pytest.raises(SinaSnapshotIncompleteError, match="重复代码"):
        provider._load_market_hq_records()


def test_sina_snapshot_preserves_ticktime_for_archive() -> None:
    frame = SinaDataProvider()._records_to_snapshot_df([_row("600000", ticktime="15:30:01")])
    assert frame.iloc[0]["时间"] == "15:30:01"
    records = collectors.normalize_cn_stocks(frame, date(2026, 10, 9), "sina.spot_snapshot")
    assert records[0].source_quote_time == datetime.fromisoformat("2026-10-09T15:30:01+08:00")


def test_spot_snapshot_file_marks_stale_and_rejects_expired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "stock_spot_snapshot.json"
    monkeypatch.setattr(spot_snapshot, "_SPOT_SNAPSHOT_FILE", path)
    rows = [{"代码": str(600000 + index), "名称": "测试", "最新价": 10} for index in range(3000)]

    path.write_text(json.dumps({
        "updated_at": (datetime.now() - timedelta(minutes=10)).isoformat(),
        "source_id": "sina.spot_snapshot",
        "rows": rows,
    }), encoding="utf-8")
    stale = spot_snapshot.load_spot_snapshot_file()
    assert stale is not None
    assert stale.attrs[spot_snapshot._SPOT_IS_STALE_ATTR] is True

    path.write_text(json.dumps({
        "updated_at": (datetime.now() - timedelta(days=2)).isoformat(),
        "source_id": "sina.spot_snapshot",
        "rows": rows,
    }), encoding="utf-8")
    assert spot_snapshot.load_spot_snapshot_file() is None


def _master_record(code: str, exchange: str) -> ExchangeStockRecord:
    return ExchangeStockRecord(code, code, exchange, None, None, "2000-01-01", None, None, "test")


def _bar(code: str) -> MarketDailyBarRecord:
    return MarketDailyBarRecord(
        market="cn", instrument_type="stock", code=code, trade_date=date(2026, 10, 9),
        currency="CNY", open=10, high=11, low=9, close=10.5, source="test",
    )


@pytest.mark.asyncio
async def test_cn_master_coverage_requires_each_exchange(monkeypatch: pytest.MonkeyPatch) -> None:
    master = ExchangeStockMaster(
        records=[
            _master_record("600000", "SH"),
            _master_record("000001", "SZ"),
            _master_record("920000", "BJ"),
        ],
        failed_exchanges={}, stale_exchanges=[],
    )

    async def get_master():
        return master

    monkeypatch.setattr(collectors, "get_exchange_stock_master", get_master)
    coverage = await collectors._validate_cn_master_coverage(
        [_bar("600000"), _bar("000001"), _bar("920000")], date(2026, 10, 9)
    )
    assert coverage == {"SH": 1.0, "SZ": 1.0, "BJ": 1.0}

    with pytest.raises(RuntimeError, match="BJ:0.00%"):
        await collectors._validate_cn_master_coverage(
            [_bar("600000"), _bar("000001")], date(2026, 10, 9)
        )


@pytest.mark.asyncio
async def test_cn_snapshot_crosscheck_normalizes_tdx_lots(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [
        MarketDailyBarRecord(
            market="cn", instrument_type="stock", code=code,
            trade_date=date(2026, 10, 9), currency="CNY",
            open=10, high=11, low=9, close=10.5,
            volume=10_000, amount=104_000, source="sina",
        )
        for code in ("600519", "000001", "920000")
    ]

    class Provider:
        def fetch_stock_quotes(self, codes):
            return {
                code: {"price": 10.5, "volume": 100, "amount": 104_000}
                for code in codes if code in {"600519", "000001", "920000"}
            }

    monkeypatch.setattr(collectors, "get_provider", lambda name: Provider())
    result = await collectors._crosscheck_cn_snapshot(records)
    assert result["samples"] == 3
    assert result["max_price_error"] == 0
    assert result["max_volume_error"] == 0


@pytest.mark.asyncio
async def test_cn_snapshot_crosscheck_rejects_price_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [
        MarketDailyBarRecord(
            market="cn", instrument_type="stock", code=code,
            trade_date=date(2026, 10, 9), currency="CNY",
            open=10, high=11, low=9, close=10.5,
            volume=10_000, amount=104_000, source="sina",
        )
        for code in ("600519", "000001", "920000")
    ]

    class Provider:
        def fetch_stock_quotes(self, codes):
            return {
                code: {"price": 9.5, "volume": 100, "amount": 104_000}
                for code in codes if code in {"600519", "000001", "920000"}
            }

    monkeypatch.setattr(collectors, "get_provider", lambda name: Provider())
    with pytest.raises(RuntimeError, match="抽样数据不一致"):
        await collectors._crosscheck_cn_snapshot(records)


@pytest.mark.asyncio
async def test_cn_snapshot_crosscheck_reports_unavailable_source(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [_bar(code) for code in ("600519", "000001", "920000")]

    class Provider:
        def fetch_stock_quotes(self, codes):
            raise ConnectionError("offline")

    monkeypatch.setattr(collectors, "get_provider", lambda name: Provider())
    with pytest.raises(collectors.SnapshotCrosscheckUnavailableError, match="暂时不可用"):
        await collectors._crosscheck_cn_snapshot(records)
