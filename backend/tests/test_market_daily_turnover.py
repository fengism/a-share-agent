from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

import app.financial_data.stock.quotes.kline as kline_module
from app.domain.market import KlineData, KlineItem
from app.modules.market_daily.models import MarketDailyBarRecord
from app.modules.market_daily.reader import load_local_daily_kline
from app.modules.market_daily.repository import MarketDailyBarRepository


def test_market_daily_bar_record_turnover_validation() -> None:
    # Valid turnover_pct
    record = MarketDailyBarRecord(
        market="cn",
        instrument_type="stock",
        code="600519",
        trade_date=date(2026, 9, 30),
        currency="CNY",
        open=10.0,
        high=11.0,
        low=9.0,
        close=10.5,
        turnover_pct=2.45,
        source="test",
    )
    assert record.turnover_pct == 2.45

    # None turnover_pct
    record_none = MarketDailyBarRecord(
        market="cn",
        instrument_type="stock",
        code="600519",
        trade_date=date(2026, 9, 30),
        currency="CNY",
        open=10.0,
        high=11.0,
        low=9.0,
        close=10.5,
        turnover_pct=None,
        source="test",
    )
    assert record_none.turnover_pct is None

    # Negative turnover_pct raises ValueError
    with pytest.raises(ValueError, match="turnover_pct 不能为负数"):
        MarketDailyBarRecord(
            market="cn",
            instrument_type="stock",
            code="600519",
            trade_date=date(2026, 9, 30),
            currency="CNY",
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.5,
            turnover_pct=-0.5,
            source="test",
        )


def _save_bars(
    repo: MarketDailyBarRepository,
    trade_date: date,
    checkpoint: str,
    segment: str,
    records: list[MarketDailyBarRecord],
) -> int:
    lease = repo.claim_attempt(trade_date, checkpoint, segment, worker_id="test")
    assert lease is not None
    return repo.persist_refresh(
        trade_date,
        checkpoint,
        segment,
        records,
        attempt_id=lease.attempt_id,
    )


def test_repository_store_and_list_turnover_pct(tmp_path: Path) -> None:
    db_path = tmp_path / "test_market_daily.sqlite3"
    repo = MarketDailyBarRepository(path=db_path)
    repo.initialize()

    records_day1 = [
        MarketDailyBarRecord(
            market="cn",
            instrument_type="stock",
            code="600519",
            trade_date=date(2026, 9, 29),
            currency="CNY",
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.5,
            turnover_pct=1.23,
            source="test",
        ),
    ]
    records_day2 = [
        MarketDailyBarRecord(
            market="cn",
            instrument_type="stock",
            code="600519",
            trade_date=date(2026, 9, 30),
            currency="CNY",
            open=10.5,
            high=12.0,
            low=10.0,
            close=11.5,
            turnover_pct=2.34,
            source="test",
        ),
    ]

    _save_bars(repo, date(2026, 9, 29), "initial", "cn_stock", records_day1)
    _save_bars(repo, date(2026, 9, 30), "initial", "cn_stock", records_day2)

    bars = repo.list_bars(
        market="cn",
        instrument_type="stock",
        code="600519",
        start_date=date(2026, 9, 29),
        end_date=date(2026, 9, 30),
    )
    assert len(bars) == 2
    assert bars[0].trade_date == date(2026, 9, 29)
    assert bars[0].turnover_pct == 1.23
    assert bars[1].trade_date == date(2026, 9, 30)
    assert bars[1].turnover_pct == 2.34


def test_repository_auto_migration_for_missing_turnover_pct(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_market_daily.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE market_daily_bars (
            market                  TEXT NOT NULL CHECK (market IN ('cn', 'hk')),
            instrument_type         TEXT NOT NULL CHECK (instrument_type IN ('stock', 'index')),
            code                    TEXT NOT NULL,
            name                    TEXT NOT NULL DEFAULT '',
            trade_date              TEXT NOT NULL,
            currency                TEXT NOT NULL CHECK (currency IN ('CNY', 'HKD')),
            open                    REAL,
            high                    REAL,
            low                     REAL,
            close                   REAL NOT NULL CHECK (close > 0),
            pre_close               REAL,
            change_amount           REAL,
            change_pct              REAL,
            volume                  REAL,
            amount                  REAL,
            adjustment              TEXT NOT NULL DEFAULT 'none' CHECK (adjustment = 'none'),
            source                  TEXT NOT NULL,
            source_quote_time       TEXT,
            verification_status     TEXT NOT NULL CHECK (verification_status IN ('provisional', 'confirmed')),
            first_refreshed_at       TEXT NOT NULL,
            last_refreshed_at        TEXT NOT NULL,
            revision                INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
            is_deleted              INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
            created_at              TEXT NOT NULL,
            updated_at              TEXT NOT NULL,
            PRIMARY KEY (market, instrument_type, code, trade_date, adjustment)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE market_daily_bar_observations (
            refresh_id              TEXT NOT NULL,
            checkpoint              TEXT NOT NULL CHECK (checkpoint IN ('initial', 'recheck')),
            refreshed_at            TEXT NOT NULL,
            market                  TEXT NOT NULL,
            instrument_type         TEXT NOT NULL,
            code                    TEXT NOT NULL,
            name                    TEXT NOT NULL DEFAULT '',
            trade_date              TEXT NOT NULL,
            currency                TEXT NOT NULL,
            open                    REAL,
            high                    REAL,
            low                     REAL,
            close                   REAL NOT NULL,
            pre_close               REAL,
            change_amount           REAL,
            change_pct              REAL,
            volume                  REAL,
            amount                  REAL,
            adjustment              TEXT NOT NULL,
            source                  TEXT NOT NULL,
            source_quote_time       TEXT,
            data_hash               TEXT NOT NULL,
            content_hash            TEXT,
            provenance_hash         TEXT,
            PRIMARY KEY (refresh_id, market, instrument_type, code, trade_date)
        )
        """
    )
    conn.commit()
    conn.close()

    repo = MarketDailyBarRepository(path=db_path)
    repo.initialize()

    conn = sqlite3.connect(db_path)
    bars_cols = [row[1] for row in conn.execute("PRAGMA table_info(market_daily_bars)").fetchall()]
    obs_cols = [row[1] for row in conn.execute("PRAGMA table_info(market_daily_bar_observations)").fetchall()]
    conn.close()
    assert "turnover_pct" in bars_cols
    assert "turnover_pct" in obs_cols


@pytest.mark.asyncio
async def test_load_local_daily_kline_propagates_turnover_pct(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "test_reader.sqlite3"
    repo = MarketDailyBarRepository(path=db_path)
    repo.initialize()

    _save_bars(
        repo,
        date(2026, 9, 30),
        "initial",
        "cn_stock",
        [
            MarketDailyBarRecord(
                market="cn",
                instrument_type="stock",
                code="600519",
                trade_date=date(2026, 9, 30),
                currency="CNY",
                open=10.0,
                high=11.0,
                low=9.0,
                close=10.5,
                turnover_pct=3.14,
                source="test",
            )
        ]
    )

    monkeypatch.setattr("app.modules.market_daily.reader._market_daily_repository", repo)

    kline = await load_local_daily_kline(
        market="cn",
        instrument_type="stock",
        code="600519",
        start_date=date(2026, 9, 30),
        end_date=date(2026, 9, 30),
    )
    assert kline is not None
    assert len(kline.items) == 1
    assert kline.items[0].turnover_pct == 3.14


@pytest.mark.asyncio
async def test_get_kline_require_turnover_with_local_data(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. When local data has turnover_pct, require_turnover=True returns local directly without upstream fetch
    local_with_turnover = KlineData(
        code="600519",
        period="daily",
        adjust="qfq",
        source="market_daily:confirmed",
        items=[
            KlineItem(
                code="600519",
                date="2026-09-30",
                open=10.0,
                high=11.0,
                low=9.0,
                close=10.5,
                volume=1000,
                amount=10000,
                turnover_pct=1.5,
            )
        ],
    )

    async def mock_load_adjusted(*args, **kwargs):
        return local_with_turnover

    upstream_called = False
    async def mock_get_historical(*args, **kwargs):
        nonlocal upstream_called
        upstream_called = True
        return local_with_turnover

    monkeypatch.setattr(kline_module, "load_local_adjusted_daily_kline", mock_load_adjusted)
    monkeypatch.setattr(kline_module, "get_historical_bars", mock_get_historical)

    result = await kline_module.get_kline(
        code="600519",
        period="daily",
        start_date="2026-09-30",
        end_date="2026-09-30",
        adjust="qfq",
        require_turnover=True,
    )
    assert result == local_with_turnover
    assert not upstream_called, "Should not hit upstream when local bars have complete turnover_pct"

    # 2. When local data has turnover_pct=None, require_turnover=True must fallback to upstream
    local_without_turnover = KlineData(
        code="600519",
        period="daily",
        adjust="qfq",
        source="market_daily:confirmed",
        items=[
            KlineItem(
                code="600519",
                date="2026-09-30",
                open=10.0,
                high=11.0,
                low=9.0,
                close=10.5,
                volume=1000,
                amount=10000,
                turnover_pct=None,
            )
        ],
    )

    async def mock_load_adjusted_no_turnover(*args, **kwargs):
        return local_without_turnover

    upstream_called = False

    async def mock_get_historical(*args, **kwargs):
        nonlocal upstream_called
        upstream_called = True
        return local_without_turnover

    monkeypatch.setattr(kline_module, "load_local_adjusted_daily_kline", mock_load_adjusted_no_turnover)
    monkeypatch.setattr(kline_module, "get_historical_bars", mock_get_historical)

    await kline_module.get_kline(
        code="600519",
        period="daily",
        start_date="2026-09-30",
        end_date="2026-09-30",
        adjust="qfq",
        require_turnover=True,
    )
    assert upstream_called, "Must hit upstream when local bars lack turnover_pct and require_turnover=True"
