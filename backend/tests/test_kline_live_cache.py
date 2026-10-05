"""交易时段内 K 线短 TTL 缓存的行为测试。

背景：交易时段内 K 线原本完全禁用缓存（read_cache/write_cache=False），
single-flight 只能合并并发请求，挡不住秒级先后到达的重复回源。这里锁定
"盘中写入短 TTL 缓存并读取" 以及 "显式区分 is_live" 的行为，避免为了
省缓存而牺牲实时性，或误伤仍依赖 `not write_cache` 判定 live 的调用方。
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from app.domain.market import KlineData, KlineItem
from app.financial_data.market.trading_session import (
    LIVE_MARKET_DATA_CACHE_TTL_SECONDS,
    MarketDataCachePolicy,
    build_market_data_cache_policy,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _sample_kline() -> KlineData:
    return KlineData(
        code="600519",
        period="daily",
        adjust="qfq",
        source="tdxhub",
        adjustment_verified=True,
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
            )
        ],
    )


class _RecordingCache:
    def __init__(self) -> None:
        self.store: dict[str, object] = {}
        self.set_calls: list[tuple[str, int]] = []
        self.get_calls = 0

    def get(self, key: str):
        self.get_calls += 1
        return self.store.get(key)

    def set(self, key: str, value: object, *, ttl: int) -> None:
        self.set_calls.append((key, ttl))
        self.store[key] = value


def test_live_policy_is_flagged_explicitly() -> None:
    trading_day = date(2026, 10, 12)  # 周一
    live_now = datetime(2026, 10, 12, 10, 30, tzinfo=SHANGHAI)
    policy = build_market_data_cache_policy(
        period="daily",
        end_date=trading_day,
        now=live_now,
        trading_dates={trading_day},
    )
    assert policy.is_live is True
    # 仍保留 write_cache=False 语义，兼容 indices 等按此判定 live 的调用方。
    assert policy.write_cache is False
    assert policy.read_cache is False


def test_closed_session_policy_is_not_live() -> None:
    trading_day = date(2026, 10, 12)
    after_close = datetime(2026, 10, 12, 16, 0, tzinfo=SHANGHAI)
    policy = build_market_data_cache_policy(
        period="daily",
        end_date=trading_day,
        now=after_close,
        trading_dates={trading_day},
    )
    assert policy.is_live is False
    assert policy.write_cache is True


@pytest.mark.asyncio
async def test_get_kline_caches_with_short_ttl_during_trading_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.financial_data.stock.quotes.kline as kline_module

    recording = _RecordingCache()
    monkeypatch.setattr(kline_module, "series_cache", recording)
    monkeypatch.setattr(
        kline_module,
        "load_local_adjusted_daily_kline",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        kline_module,
        "resolve_market_data_cache_policy",
        AsyncMock(
            return_value=MarketDataCachePolicy(
                read_cache=False, write_cache=False, ttl_seconds=None, is_live=True
            )
        ),
    )
    monkeypatch.setattr(
        kline_module,
        "_load_kline",
        AsyncMock(return_value=_sample_kline()),
    )

    result = await kline_module.get_kline(
        "600519",
        period="daily",
        start_date="2026-09-01",
        end_date="2026-09-30",
        adjust="qfq",
    )

    assert result.items and result.items[0].close == 10.5
    assert recording.get_calls >= 1, "盘中应先查短 TTL 缓存"
    assert recording.set_calls, "盘中应写入短 TTL 缓存"
    assert recording.set_calls[0][1] == LIVE_MARKET_DATA_CACHE_TTL_SECONDS


@pytest.mark.asyncio
async def test_get_kline_reuses_short_ttl_cache_on_second_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.financial_data.stock.quotes.kline as kline_module

    recording = _RecordingCache()
    monkeypatch.setattr(kline_module, "series_cache", recording)
    monkeypatch.setattr(
        kline_module,
        "load_local_adjusted_daily_kline",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        kline_module,
        "resolve_market_data_cache_policy",
        AsyncMock(
            return_value=MarketDataCachePolicy(
                read_cache=False, write_cache=False, ttl_seconds=None, is_live=True
            )
        ),
    )
    upstream = AsyncMock(return_value=_sample_kline())
    monkeypatch.setattr(kline_module, "_load_kline", upstream)

    await kline_module.get_kline(
        "600519", period="daily", start_date="2026-09-01", end_date="2026-09-30", adjust="qfq"
    )
    await kline_module.get_kline(
        "600519", period="daily", start_date="2026-09-01", end_date="2026-09-30", adjust="qfq"
    )

    assert upstream.await_count == 1, "第二次请求应命中短 TTL 缓存，不再回源"
