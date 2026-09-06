import asyncio
import logging

from app.core.cache import cache_date, dated_cache_key_no_day, one_year_ago_date
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import call_blocking, ths_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.domain.market import MarketVolume
from app.financial_data.dates import parse_market_date
from app.financial_data.market.quotes.index_kline import get_index_kline
from app.financial_data.market.quotes.schemas import MarketVolumeResponse, MarketVolumeSeriesItem
from app.financial_data.market.quotes.sources import INDEX_KLINE_SOURCE_APIS
from app.financial_data.market.trading_session import resolve_market_data_cache_policy
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

# 上证指数 + 深证成指
_INDEX_SYMBOLS = ("000001", "399001")
_INDEX_MARKETS = {"000001": "shanghai", "399001": "shenzhen"}
_market_volume_singleflight: AsyncSingleFlight[MarketVolumeResponse] = AsyncSingleFlight()


async def _load_market_volume(
    start_date: str,
    end_date: str,
    cache_key: str,
    cache_ttl: int | None,
) -> MarketVolumeResponse:
    kline_results = await asyncio.gather(
        *[
            get_index_kline(symbol=symbol, period="daily", start_date=start_date, end_date=end_date)
            for symbol in _INDEX_SYMBOLS
        ],
        return_exceptions=True,
    )

    aggregated: dict[str, MarketVolumeSeriesItem] = {}
    unavailable_markets = []
    market_sources = {}
    source_apis = {}
    for symbol, kline_result in zip(_INDEX_SYMBOLS, kline_results, strict=True):
        market = _INDEX_MARKETS[symbol]
        if isinstance(kline_result, Exception):
            unavailable_markets.append(market)
            logger.warning("%s 指数K线获取失败，跳过: %s", market, kline_result)
            continue
        if kline_result.source:
            market_sources[market] = kline_result.source
            source_api = INDEX_KLINE_SOURCE_APIS.get(kline_result.source)
            if source_api:
                source_apis[market] = source_api
        for item in kline_result.items:
            raw = item.date.replace("-", "")
            date_str = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}" if len(raw) == 8 else raw
            point = aggregated.setdefault(date_str, MarketVolumeSeriesItem(date=date_str))
            point.volume += item.volume or 0.0
            point.amount += item.amount or 0.0

    result = MarketVolumeResponse(
        items=sorted(aggregated.values(), key=lambda item: item.date),
        partial=bool(unavailable_markets),
        unavailable_markets=unavailable_markets,
        market_sources=market_sources,
        source_apis=source_apis,
    )
    if cache_ttl is not None:
        cache.set(cache_key, result, ttl=min(cache_ttl, 30) if result.partial else cache_ttl)
    return result


async def get_market_volume(start_date: str = "", end_date: str = "") -> MarketVolumeResponse:
    """获取沪深两市合计成交量，并显式标记缺失市场。

    通过 get_index_kline 分别获取上证指数和深证成指的日K数据，
    按日期聚合两市的成交量和成交额总和。

    Param:
        start_date: 起始日期，留空默认一年前
        end_date: 结束日期，留空默认当天
    Return:
        MarketVolumeResponse 模型
    """
    if not end_date:
        end_date = cache_date()
    if not start_date:
        start_date = one_year_ago_date()

    parsed_end_date = parse_market_date(end_date, "end_date")
    policy = await resolve_market_data_cache_policy("daily", parsed_end_date)
    cache_key = dated_cache_key_no_day("market_volume", start_date, end_date)
    if policy.read_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return MarketVolumeResponse.model_validate(cached)
    return await _market_volume_singleflight.do(
        cache_key,
        lambda: _load_market_volume(
            start_date,
            end_date,
            cache_key,
            policy.ttl_seconds if policy.write_cache else None,
        ),
    )


async def get_realtime_market_volume() -> MarketVolume:
    """获取同花顺市场成交额实时数据。

    Param:
        无
    Return:
        MarketVolume 模型对象
    """
    return await provider_gateway.call(
        "ths",
        "market_volume",
        lambda: call_blocking(
            get_provider("ths").fetch_market_volume,
            semaphore=ths_semaphore,
        ),
    )
