"""Named cache policies for provider-facing data capabilities."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TtlPolicy:
    ttl_seconds: int


@dataclass(frozen=True)
class FreshStalePolicy:
    fresh_seconds: int
    stale_seconds: int


@dataclass(frozen=True)
class LiveStablePolicy:
    live_seconds: int
    stable_seconds: int


REALTIME_STOCK_QUOTES = FreshStalePolicy(fresh_seconds=10, stale_seconds=300)
MARKET_INDICES = LiveStablePolicy(live_seconds=30, stable_seconds=24 * 60 * 60)
INDEX_INTRADAY = TtlPolicy(ttl_seconds=30)
STOCK_INTRADAY = TtlPolicy(ttl_seconds=30)
THS_HOT_RANK = TtlPolicy(ttl_seconds=5 * 60)
MARKET_LIMIT_HISTORY = TtlPolicy(ttl_seconds=24 * 60 * 60)
MARKET_SECTOR_STOCKS_HISTORY = TtlPolicy(ttl_seconds=24 * 60 * 60)
BASIC_INFO_FINAL = TtlPolicy(ttl_seconds=5 * 60)
BASIC_INFO_STATIC = TtlPolicy(ttl_seconds=24 * 60 * 60)
