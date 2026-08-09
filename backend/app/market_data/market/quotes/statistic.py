import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

import pandas as pd

from app.core.cache import cache, dated_cache_key
from app.core.concurrency.rate_limiter import call_blocking, eastmoney_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import safe_float
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider
from app.market_data.market.quotes.schemas import MarketStatistics

logger = logging.getLogger(__name__)
_statistics_singleflight: AsyncSingleFlight[MarketStatistics] = AsyncSingleFlight()
_ParsedSource = TypeVar("_ParsedSource")


@dataclass(frozen=True, slots=True)
class _SectorStatistics:
    top: list[dict]
    bottom: list[dict]


@dataclass(frozen=True, slots=True)
class _DistributionStatistics:
    rows: list[dict]
    up_count: int
    down_count: int
    flat_count: int

    @property
    def total_stocks(self) -> int:
        return self.up_count + self.down_count + self.flat_count


@dataclass(frozen=True, slots=True)
class _LimitPoolStatistics:
    stocks: list[dict]
    count: int


def _get_eastmoney_provider():
    """延迟获取东方财富 provider。"""
    return get_provider("eastmoney")


def _get_tencent_provider():
    """延迟获取腾讯 provider。"""
    return get_provider("tencent")


def get_sector_rankings() -> dict:
    """获取腾讯板块涨跌榜，拆分为 top/bottom 两份字段列表。

    Param:
        无
    Return:
        包含 top_sectors 和 bottom_sectors 列表的字典
    """
    top_df, bottom_df = _get_tencent_provider().fetch_industry_rankings()
    def to_items(frame: pd.DataFrame) -> list[dict]:
        """将板块 DataFrame 转换为字典列表。

        Param:
            frame: 板块 DataFrame
        Return:
            板块字段字典列表
        """
        result = []
        for _, row in frame.iterrows():
            result.append(
                {
                    "name": str(row.get("板块名称", "")),
                    "change_pct": safe_float(row.get("涨跌幅")),
                    "change_pct_5d": safe_float(row.get("5日涨跌幅")),
                    "change_pct_20d": safe_float(row.get("20日涨跌幅")),
                    "leading_stock": str(row.get("领涨跌股票名称", "")),
                    "leading_change_pct": safe_float(row.get("领涨股票-涨跌幅"))
                }
            )
        return result

    return {
        "top_sectors": to_items(top_df),
        "bottom_sectors": to_items(bottom_df),
    }


def _parse_sector_statistics(value: Any) -> _SectorStatistics:
    return _SectorStatistics(
        top=list(value.get("top_sectors", [])),
        bottom=list(value.get("bottom_sectors", [])),
    )


def _parse_distribution_statistics(value: Any) -> _DistributionStatistics:
    rows = []
    fenbu = value.get("fenbu", []) if isinstance(value, dict) else []
    for item in fenbu:
        for label, count in item.items():
            rows.append({"label": label, "count": int(count or 0)})
    return _DistributionStatistics(
        rows=rows,
        up_count=sum(item["count"] for item in rows if float(item["label"]) > 0),
        down_count=sum(item["count"] for item in rows if float(item["label"]) < 0),
        flat_count=sum(item["count"] for item in rows if float(item["label"]) == 0),
    )


def _parse_limit_pool_statistics(value: Any) -> _LimitPoolStatistics:
    data, count = value
    return _LimitPoolStatistics(stocks=list(data[:10]), count=int(count or 0))


def _resolve_source(
    value: Any,
    parser: Callable[[Any], _ParsedSource],
    *,
    label: str,
) -> _ParsedSource | None:
    if isinstance(value, Exception):
        logger.warning("获取%s失败: %s", label, value)
        return None
    try:
        return parser(value)
    except Exception as exc:
        logger.warning("解析%s失败: %s", label, exc)
        return None


async def _fetch_statistics_sources(date: str) -> tuple[Any, Any, Any, Any]:
    provider = _get_eastmoney_provider()
    values = await asyncio.gather(
        provider_gateway.call(
            "tencent",
            "market_sector_rankings",
            lambda: call_blocking(get_sector_rankings),
        ),
        provider_gateway.call(
            "eastmoney",
            "market_pct_distribution",
            lambda: call_blocking(
                provider.fetch_market_pct_distribution,
                date,
                semaphore=eastmoney_semaphore,
            ),
        ),
        provider_gateway.call(
            "eastmoney",
            "market_limit_up_pool",
            lambda: call_blocking(
                provider.fetch_market_limit_up_pool,
                date,
                semaphore=eastmoney_semaphore,
            ),
        ),
        provider_gateway.call(
            "eastmoney",
            "market_limit_down_pool",
            lambda: call_blocking(
                provider.fetch_market_limit_down_pool,
                date,
                semaphore=eastmoney_semaphore,
            ),
        ),
        return_exceptions=True,
    )
    return values[0], values[1], values[2], values[3]


def _build_market_statistics(
    date: str,
    sector_value: Any,
    distribution_value: Any,
    limit_up_value: Any,
    limit_down_value: Any,
) -> MarketStatistics:
    sectors = _resolve_source(
        sector_value,
        _parse_sector_statistics,
        label="板块涨跌榜",
    )
    distribution = _resolve_source(
        distribution_value,
        _parse_distribution_statistics,
        label="股票涨跌分布",
    )
    limit_up = _resolve_source(
        limit_up_value,
        _parse_limit_pool_statistics,
        label="涨停池",
    )
    limit_down = _resolve_source(
        limit_down_value,
        _parse_limit_pool_statistics,
        label="跌停池",
    )
    source = next(
        (
            source_name
            for source_name, parsed in (
                ("sector-rankings", sectors),
                ("stock-pct-distribution", distribution),
                ("limit-up-pool", limit_up),
                ("limit-down-pool", limit_down),
            )
            if parsed is not None
        ),
        "fallback",
    )
    return MarketStatistics(
        date=date,
        source=source,
        top_sectors=sectors.top if sectors else [],
        bottom_sectors=sectors.bottom if sectors else [],
        up_count=distribution.up_count if distribution else 0,
        down_count=distribution.down_count if distribution else 0,
        flat_count=distribution.flat_count if distribution else 0,
        limit_up_count=limit_up.count if limit_up else 0,
        limit_down_count=limit_down.count if limit_down else 0,
        total_stocks=distribution.total_stocks if distribution else 0,
        limit_up_stocks=limit_up.stocks if limit_up else [],
        limit_down_stocks=limit_down.stocks if limit_down else [],
        stock_pct_distribution=distribution.rows if distribution else [],
    )


async def _load_market_statistics(date: str, cache_key: str) -> MarketStatistics:
    """并行加载并组装大盘统计数据。"""
    result = _build_market_statistics(date, *await _fetch_statistics_sources(date))
    cache.set(cache_key, result, ttl=300)
    return result


async def get_market_statistics(date: str | None = None) -> MarketStatistics:
    """获取带缓存和并发去重的大盘统计数据。

    Param:
        date: 统计日期，格式 YYYY-MM-DD，默认当天
    Return:
        MarketStatistics 模型对象，包含各项市场统计指标
    """
    if date is None:
        date = time.strftime("%Y-%m-%d", time.localtime())

    cache_key = dated_cache_key("market_statistics", date)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    return await _statistics_singleflight.do(
        cache_key,
        lambda: _load_market_statistics(date, cache_key),
    )
