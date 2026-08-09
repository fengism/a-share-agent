import logging

from app.core.cache import cache, dated_cache_key_no_day
from app.core.concurrency.rate_limiter import call_blocking
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider
from app.market_data.market.macro import collector as macro_collector
from app.market_data.market.macro import normalizer as macro_normalizer

logger = logging.getLogger(__name__)
_macro_singleflight: AsyncSingleFlight[dict] = AsyncSingleFlight()
_macro_metric_singleflight: AsyncSingleFlight[object] = AsyncSingleFlight()
_eastmoney_provider = None
MACRO_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
_MACRO_DATA_FLIGHT_KEY = "macro_data"
_MACRO_ALL_DATA_FLIGHT_KEY = "macro_all_data"


def _macro_metric_cache_key(operation: str) -> str:
    return dated_cache_key_no_day("macro_metric", operation)


async def _load_macro_metric(operation: str, fetcher) -> object:
    result = await provider_gateway.call(
        "eastmoney",
        f"macro_{operation}",
        lambda: call_blocking(fetcher),
    )
    if isinstance(result, list) and result:
        cache.set(
            _macro_metric_cache_key(operation),
            result,
            ttl=MACRO_CACHE_TTL_SECONDS,
        )
    return result


async def _fetch_macro_metric(operation: str, fetcher, *, force_refresh: bool = False):
    cache_key = _macro_metric_cache_key(operation)
    if not force_refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    return await _macro_metric_singleflight.do(
        cache_key,
        lambda: _load_macro_metric(operation, fetcher),
    )


def _get_eastmoney_provider():
    global _eastmoney_provider
    if _eastmoney_provider is None:
        _eastmoney_provider = get_provider("eastmoney")
    return _eastmoney_provider


def _extract_latest(data: list[dict], keys: list[str]) -> dict | None:
    return macro_normalizer.extract_latest(data, keys)


def _extract_recent(data: list[dict], keys: list[str], n: int = 3) -> list[dict]:
    return macro_normalizer.extract_recent(data, keys, n)


async def get_macro_data() -> dict:
    """获取 CPI、PPI、PMI 和货币供应量摘要。"""
    return await _macro_singleflight.do(
        _MACRO_DATA_FLIGHT_KEY,
        _load_macro_data,
    )


async def _load_macro_data() -> dict:
    collected = await macro_collector.collect_basic(
        _get_eastmoney_provider(),
        _fetch_macro_metric,
    )
    result = macro_normalizer.normalize_basic(
        collected,
        logger,
        _extract_latest,
        _extract_recent,
    )
    return result


async def get_macro_all_data(force_refresh: bool = False) -> dict:
    """获取物价、景气、货币、利率、增速和外贸全量宏观数据。"""
    return await _macro_singleflight.do(
        (_MACRO_ALL_DATA_FLIGHT_KEY, force_refresh),
        lambda: _load_macro_all_data(force_refresh=force_refresh),
    )


async def _load_macro_all_data(*, force_refresh: bool = False) -> dict:
    fetch_metric = _fetch_macro_metric
    if force_refresh:
        async def force_fetch_metric(operation: str, fetcher):
            return await _fetch_macro_metric(operation, fetcher, force_refresh=True)

        fetch_metric = force_fetch_metric

    collected = await macro_collector.collect_full(
        _get_eastmoney_provider(),
        fetch_metric,
    )
    result = macro_normalizer.normalize_full(
        collected,
        logger,
        _extract_latest,
        _extract_recent,
    )
    return result
