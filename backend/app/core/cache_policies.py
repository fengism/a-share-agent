"""Named cache policies for provider-facing data capabilities."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TtlPolicy:
    ttl_seconds: int


@dataclass(frozen=True)
class FreshStalePolicy:
    fresh_seconds: int
    stale_seconds: int
    maxsize: int


@dataclass(frozen=True)
class LiveStablePolicy:
    live_seconds: int
    stable_seconds: int


REALTIME_STOCK_QUOTES = FreshStalePolicy(
    fresh_seconds=10,
    stale_seconds=300,
    maxsize=10_000,
)
MARKET_INDICES = LiveStablePolicy(live_seconds=30, stable_seconds=24 * 60 * 60)
INDEX_INTRADAY = TtlPolicy(ttl_seconds=30)
STOCK_INTRADAY = TtlPolicy(ttl_seconds=30)
THS_HOT_RANK = TtlPolicy(ttl_seconds=5 * 60)
MARKET_LIMIT_HISTORY = TtlPolicy(ttl_seconds=24 * 60 * 60)
MARKET_SECTOR_STOCKS_HISTORY = TtlPolicy(ttl_seconds=24 * 60 * 60)
BASIC_INFO_FINAL = TtlPolicy(ttl_seconds=5 * 60)
BASIC_INFO_STATIC = TtlPolicy(ttl_seconds=24 * 60 * 60)

PRICE_ANOMALY = TtlPolicy(ttl_seconds=24 * 60 * 60)
VALUATION = TtlPolicy(ttl_seconds=24 * 60 * 60)
VALUATION_DETAIL = TtlPolicy(ttl_seconds=24 * 60 * 60)
SINA_STOCK_NAMES = TtlPolicy(ttl_seconds=24 * 60 * 60)
# 新浪全市场快照一次完整分页耗时可达 30-60 秒；此处是交易时段 TTL，
# 休市时由 SinaDataProvider 动态延长到 30 分钟。盘后归档仍显式绕过缓存。
SINA_SPOT_SNAPSHOT = TtlPolicy(ttl_seconds=3 * 60)
AGENT_WEB_FETCH = TtlPolicy(ttl_seconds=10 * 60)
# 搜索结果短缓存：Agent 改写一次查询重试、或并行搜相近关键词时会重复打同一引擎，
# 而百度单次搜索要传 1-2MB HTML 且命中反爬时最多重试三次，重复请求代价高。
AGENT_WEB_SEARCH = TtlPolicy(ttl_seconds=3 * 60)
# 概念：成分股行情 + 合成等权指数，日线数据日内缓存一次即可。
CONCEPT_LINKAGE = TtlPolicy(ttl_seconds=24 * 60 * 60)
