import asyncio
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeVar, cast

import pandas as pd

from app.configuration import get_settings
from app.core.cache import dated_cache_key
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import (
    baidu_semaphore,
    call_blocking,
    cls_semaphore,
    eastmoney_semaphore,
    kaipanhong_semaphore,
    tencent_semaphore,
)
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import market_today, safe_float
from app.financial_data.market.quotes.schemas import MarketStatistics
from app.financial_data.market.quotes.sources import (
    BAIDU_MARKET_SECTOR_API,
    BAIDU_MARKET_SECTOR_SOURCE_ID,
    CLS_MARKET_DISTRIBUTION_API,
    CLS_MARKET_DISTRIBUTION_SOURCE_ID,
    CLS_MARKET_SECTOR_API,
    CLS_MARKET_SECTOR_SOURCE_ID,
    EASTMONEY_LIMIT_DOWN_API,
    EASTMONEY_LIMIT_DOWN_SOURCE_ID,
    EASTMONEY_LIMIT_UP_API,
    EASTMONEY_LIMIT_UP_SOURCE_ID,
    EASTMONEY_MARKET_DISTRIBUTION_API,
    EASTMONEY_MARKET_DISTRIBUTION_SOURCE_ID,
    EASTMONEY_MARKET_SECTOR_API,
    EASTMONEY_MARKET_SECTOR_SOURCE_ID,
    KAIPANHONG_LIMIT_UP_API,
    KAIPANHONG_LIMIT_UP_SOURCE_ID,
    TENCENT_MARKET_SECTOR_API,
    TENCENT_MARKET_SECTOR_SOURCE_ID,
)
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)
_statistics_singleflight: AsyncSingleFlight[MarketStatistics] = AsyncSingleFlight()
_ParsedSource = TypeVar("_ParsedSource")


@dataclass(frozen=True, slots=True)
class _SectorStatistics:
    top: list[dict]
    bottom: list[dict]
    source_id: str
    source_api: str


@dataclass(frozen=True, slots=True)
class _DistributionStatistics:
    rows: list[dict]
    up_count: int
    down_count: int
    flat_count: int
    source_id: str
    source_api: str

    @property
    def total_stocks(self) -> int:
        return self.up_count + self.down_count + self.flat_count


@dataclass(frozen=True, slots=True)
class _LimitPoolStatistics:
    stocks: list[dict]
    count: int
    source_id: str
    source_api: str


@dataclass(frozen=True, slots=True)
class _StatisticsAttempt:
    provider: str
    operation: str
    loader: Callable[[], Any]
    parser: Callable[[Any, str, str], Any]
    source_id: str
    source_api: str
    semaphore: asyncio.Semaphore


def _get_provider(name: str):
    return get_provider(name)


def _get_eastmoney_provider():
    """Compatibility helper retained for existing tests and callers."""
    return _get_provider("eastmoney")


def _tencent_sector_rankings() -> tuple[pd.DataFrame, pd.DataFrame]:
    return cast(
        tuple[pd.DataFrame, pd.DataFrame],
        _get_provider("tencent").fetch_industry_rankings(),
    )


def _normalize_tencent_sector_frame(frame: pd.DataFrame) -> list[dict]:
    result = []
    for _, row in frame.iterrows():
        result.append(
            {
                "name": str(row.get("板块名称", "")),
                "change_pct": safe_float(row.get("涨跌幅")),
                "change_pct_5d": safe_float(row.get("5日涨跌幅")),
                "change_pct_20d": safe_float(row.get("20日涨跌幅")),
                "leading_stock": str(row.get("领涨跌股票名称", "")),
                "leading_change_pct": safe_float(row.get("领涨股票-涨跌幅")),
            }
        )
    return result


def _parse_sector_statistics(value: Any, source_id: str, source_api: str) -> _SectorStatistics:
    if isinstance(value, tuple) and len(value) == 2:
        top_frame, bottom_frame = value
        if not isinstance(top_frame, pd.DataFrame) or not isinstance(bottom_frame, pd.DataFrame):
            raise TypeError("板块排名返回类型无效")
        top = _normalize_tencent_sector_frame(top_frame)
        bottom = _normalize_tencent_sector_frame(bottom_frame)
    elif isinstance(value, Mapping):
        top = list(value.get("top") or value.get("top_sectors") or [])
        bottom = list(value.get("bottom") or value.get("bottom_sectors") or [])
    else:
        raise TypeError("板块排名返回类型无效")
    if not top and not bottom:
        raise ValueError("板块排名为空")
    return _SectorStatistics(top=top, bottom=bottom, source_id=source_id, source_api=source_api)


def _parse_eastmoney_distribution(
    value: Any,
    source_id: str,
    source_api: str,
) -> _DistributionStatistics:
    rows: list[dict[str, Any]] = []
    fenbu = value.get("fenbu", []) if isinstance(value, Mapping) else []
    for item in fenbu:
        if not isinstance(item, Mapping):
            continue
        for label, count in item.items():
            rows.append({"label": str(label), "count": int(count or 0)})
    if not rows:
        raise ValueError("东方财富涨跌分布为空")
    return _DistributionStatistics(
        rows=rows,
        up_count=sum(item["count"] for item in rows if float(item["label"]) > 0),
        down_count=sum(item["count"] for item in rows if float(item["label"]) < 0),
        flat_count=sum(item["count"] for item in rows if float(item["label"]) == 0),
        source_id=source_id,
        source_api=source_api,
    )


def _parse_cls_distribution(value: Any, source_id: str, source_api: str) -> _DistributionStatistics:
    distribution = value.get("up_down_dis") if isinstance(value, Mapping) else None
    if not isinstance(distribution, Mapping):
        raise TypeError("财联社涨跌分布返回类型无效")
    required_fields = {"rise_num", "fall_num", "flat_num"}
    if not required_fields.issubset(distribution):
        raise ValueError("财联社涨跌分布字段不完整")
    buckets = (
        ("-10", "down_10"),
        ("-8", "down_8"),
        ("-6", "down_6"),
        ("-4", "down_4"),
        ("-2", "down_2"),
        ("0", "flat_num"),
        ("2", "up_2"),
        ("4", "up_4"),
        ("6", "up_6"),
        ("8", "up_8"),
        ("10", "up_10"),
    )
    rows = [
        {"label": label, "count": int(distribution.get(field) or 0)}
        for label, field in buckets
    ]
    return _DistributionStatistics(
        rows=rows,
        up_count=int(distribution.get("rise_num") or 0),
        down_count=int(distribution.get("fall_num") or 0),
        flat_count=int(distribution.get("flat_num") or 0),
        source_id=source_id,
        source_api=source_api,
    )


def _parse_eastmoney_limit_pool(value: Any, source_id: str, source_api: str) -> _LimitPoolStatistics:
    if not isinstance(value, tuple) or len(value) != 2:
        raise TypeError("东方财富涨跌停池返回类型无效")
    data, count = value
    if not isinstance(data, list):
        raise TypeError("东方财富涨跌停股票列表无效")
    return _LimitPoolStatistics(
        stocks=list(data[:10]),
        count=int(count or 0),
        source_id=source_id,
        source_api=source_api,
    )


def _parse_kaipanhong_limit_pool(
    value: Any,
    source_id: str,
    source_api: str,
) -> _LimitPoolStatistics:
    stocks = value.get("stocks") if isinstance(value, Mapping) else None
    if not isinstance(stocks, list):
        raise TypeError("开盘红涨停池返回类型无效")
    return _LimitPoolStatistics(
        stocks=[dict(item) for item in stocks[:10] if isinstance(item, Mapping)],
        count=len(stocks),
        source_id=source_id,
        source_api=source_api,
    )


async def _run_attempts(
    attempts: list[_StatisticsAttempt],
    timeout_seconds: float,
) -> Any:
    last_error: Exception | None = None
    for index, attempt in enumerate(attempts):
        try:
            async def load_attempt() -> Any:
                return await call_blocking(
                    attempt.loader,
                    semaphore=attempt.semaphore,
                )

            value = await asyncio.wait_for(
                provider_gateway.call(
                    attempt.provider,
                    attempt.operation,
                    load_attempt,
                    is_fallback_attempt=index > 0,
                    max_attempts=1,
                ),
                timeout=timeout_seconds,
            )
            return attempt.parser(value, attempt.source_id, attempt.source_api)
        except Exception as error:
            last_error = error
            logger.info(
                "市场统计数据源失败: provider=%s operation=%s error=%s",
                attempt.provider,
                attempt.operation,
                error,
            )
    return last_error or RuntimeError("市场统计数据源为空")


def _sector_attempts() -> list[_StatisticsAttempt]:
    return [
        _StatisticsAttempt(
            "cls",
            "market_sector_rankings",
            lambda: _get_provider("cls").fetch_industry_rankings(50),
            _parse_sector_statistics,
            CLS_MARKET_SECTOR_SOURCE_ID,
            CLS_MARKET_SECTOR_API,
            cls_semaphore,
        ),
        _StatisticsAttempt(
            "eastmoney",
            "market_sector_rankings",
            lambda: _get_eastmoney_provider().fetch_industry_rankings(50),
            _parse_sector_statistics,
            EASTMONEY_MARKET_SECTOR_SOURCE_ID,
            EASTMONEY_MARKET_SECTOR_API,
            eastmoney_semaphore,
        ),
        _StatisticsAttempt(
            "baidu",
            "market_sector_rankings",
            lambda: _get_provider("baidu").fetch_industry_rankings(50),
            _parse_sector_statistics,
            BAIDU_MARKET_SECTOR_SOURCE_ID,
            BAIDU_MARKET_SECTOR_API,
            baidu_semaphore,
        ),
        _StatisticsAttempt(
            "tencent",
            "market_sector_rankings",
            _tencent_sector_rankings,
            _parse_sector_statistics,
            TENCENT_MARKET_SECTOR_SOURCE_ID,
            TENCENT_MARKET_SECTOR_API,
            tencent_semaphore,
        ),
    ]


def _distribution_attempts(date: str) -> list[_StatisticsAttempt]:
    attempts: list[_StatisticsAttempt] = []
    if date == market_today().isoformat():
        attempts.append(
            _StatisticsAttempt(
                "cls",
                "market_pct_distribution",
                lambda: _get_provider("cls").fetch_market_emotion(),
                _parse_cls_distribution,
                CLS_MARKET_DISTRIBUTION_SOURCE_ID,
                CLS_MARKET_DISTRIBUTION_API,
                cls_semaphore,
            )
        )
    attempts.append(
        _StatisticsAttempt(
            "eastmoney",
            "market_pct_distribution",
            lambda: _get_eastmoney_provider().fetch_market_pct_distribution(date),
            _parse_eastmoney_distribution,
            EASTMONEY_MARKET_DISTRIBUTION_SOURCE_ID,
            EASTMONEY_MARKET_DISTRIBUTION_API,
            eastmoney_semaphore,
        )
    )
    return attempts


def _limit_up_attempts(date: str) -> list[_StatisticsAttempt]:
    return [
        _StatisticsAttempt(
            "kaipanhong",
            "market_limit_up_pool",
            lambda: _get_provider("kaipanhong").fetch_limit_up_ladder(date),
            _parse_kaipanhong_limit_pool,
            KAIPANHONG_LIMIT_UP_SOURCE_ID,
            KAIPANHONG_LIMIT_UP_API,
            kaipanhong_semaphore,
        ),
        _StatisticsAttempt(
            "eastmoney",
            "market_limit_up_pool",
            lambda: _get_eastmoney_provider().fetch_market_limit_up_pool(date),
            _parse_eastmoney_limit_pool,
            EASTMONEY_LIMIT_UP_SOURCE_ID,
            EASTMONEY_LIMIT_UP_API,
            eastmoney_semaphore,
        ),
    ]


def _limit_down_attempts(date: str) -> list[_StatisticsAttempt]:
    return [
        _StatisticsAttempt(
            "eastmoney",
            "market_limit_down_pool",
            lambda: _get_eastmoney_provider().fetch_market_limit_down_pool(date),
            _parse_eastmoney_limit_pool,
            EASTMONEY_LIMIT_DOWN_SOURCE_ID,
            EASTMONEY_LIMIT_DOWN_API,
            eastmoney_semaphore,
        )
    ]


async def _fetch_statistics_sources(
    date: str,
    section_timeout_seconds: float,
) -> tuple[Any, Any, Any, Any]:
    results = await asyncio.gather(
        _run_attempts(_sector_attempts(), section_timeout_seconds),
        _run_attempts(_distribution_attempts(date), section_timeout_seconds),
        _run_attempts(_limit_up_attempts(date), section_timeout_seconds),
        _run_attempts(_limit_down_attempts(date), section_timeout_seconds),
    )
    return results[0], results[1], results[2], results[3]


def _resolved_source(value: Any, expected_type: type[_ParsedSource], label: str) -> _ParsedSource | None:
    if isinstance(value, expected_type):
        return value
    logger.warning("获取%s失败: %s", label, value)
    return None


def _build_market_statistics(
    date: str,
    sector_value: Any,
    distribution_value: Any,
    limit_up_value: Any,
    limit_down_value: Any,
) -> MarketStatistics:
    sectors = _resolved_source(sector_value, _SectorStatistics, "板块涨跌榜")
    distribution = _resolved_source(distribution_value, _DistributionStatistics, "股票涨跌分布")
    limit_up = _resolved_source(limit_up_value, _LimitPoolStatistics, "涨停池")
    limit_down = _resolved_source(limit_down_value, _LimitPoolStatistics, "跌停池")
    parsed_sections = {
        "sector_rankings": sectors,
        "pct_distribution": distribution,
        "limit_up_pool": limit_up,
        "limit_down_pool": limit_down,
    }
    unavailable_sections = [section for section, parsed in parsed_sections.items() if parsed is None]
    available = [parsed for parsed in parsed_sections.values() if parsed is not None]
    field_sources: dict[str, str] = {}
    if sectors is not None:
        field_sources.update({"top_sectors": sectors.source_id, "bottom_sectors": sectors.source_id})
    if distribution is not None:
        field_sources.update({
            field: distribution.source_id
            for field in ("up_count", "down_count", "flat_count", "total_stocks", "stock_pct_distribution")
        })
    if limit_up is not None:
        field_sources.update({
            "limit_up_count": limit_up.source_id,
            "limit_up_stocks": limit_up.source_id,
        })
    if limit_down is not None:
        field_sources.update({
            "limit_down_count": limit_down.source_id,
            "limit_down_stocks": limit_down.source_id,
        })
    return MarketStatistics(
        date=date,
        source="+".join(dict.fromkeys(parsed.source_id for parsed in available)) or "fallback",
        partial=bool(unavailable_sections),
        unavailable_sections=unavailable_sections,
        field_sources=field_sources,
        source_apis={parsed.source_id: parsed.source_api for parsed in available},
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


async def _load_market_statistics(
    date: str,
    cache_key: str,
    section_timeout_seconds: float,
) -> MarketStatistics:
    result = _build_market_statistics(
        date,
        *await _fetch_statistics_sources(date, section_timeout_seconds),
    )
    cache.set(cache_key, result, ttl=30 if result.partial else 300)
    return result


async def get_market_statistics(
    date: str | None = None,
    *,
    section_timeout_seconds: float | None = None,
) -> MarketStatistics:
    if date is None:
        date = time.strftime("%Y-%m-%d", time.localtime())
    cache_key = dated_cache_key("market_statistics", date)
    cached = cache.get(cache_key)
    if cached is not None:
        return MarketStatistics.model_validate(cached)
    timeout_seconds = (
        section_timeout_seconds
        if section_timeout_seconds is not None
        else get_settings().market_statistics_section_timeout_seconds
    )
    return await _statistics_singleflight.do(
        cache_key,
        lambda: _load_market_statistics(date, cache_key, timeout_seconds),
    )
