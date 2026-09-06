"""Current-session market-index intraday quotes."""

from typing import cast

import pandas as pd

from app.constants.market import INDEX_FALLBACKS
from app.core.cache import dated_cache_key
from app.core.cache import market_cache as cache
from app.core.cache_policies import INDEX_INTRADAY
from app.core.concurrency.rate_limiter import sina_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.core.market import normalize_index_code, safe_float
from app.financial_data.market.quotes.schemas import IndexIntradayData, IndexIntradayItem
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

_ALLOWED_INDEX_CODES = frozenset(item[0] for item in INDEX_FALLBACKS)
_index_intraday_singleflight = AsyncSingleFlight[IndexIntradayData]()


def _get_sina_provider():
    return get_provider("sina")


def _validate_index_code(symbol: str) -> str:
    code = normalize_index_code(symbol.strip().lower())
    if code not in _ALLOWED_INDEX_CODES:
        raise ValueError(f"不支持的指数代码: {symbol}")
    return code


async def _load_index_intraday(code: str) -> IndexIntradayData:
    try:
        frame = await provider_gateway.call_blocking(
            "sina",
            "index_intraday",
            _get_sina_provider().fetch_index_intraday,
            code,
            semaphore=sina_semaphore,
        )
    except Exception as error:
        raise UpstreamUnavailableError(f"指数 {code} 分时上游暂时不可用") from error

    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return IndexIntradayData(code=code, source="sina_direct", items=[])

    items: list[IndexIntradayItem] = []
    for _, row in frame.iterrows():
        price = safe_float(row.get("price"))
        time_text = str(row.get("time") or "").strip()
        if price is None or not time_text:
            continue
        items.append(
            IndexIntradayItem(
                time=time_text,
                price=price,
                avg_price=safe_float(row.get("avg_price")),
                volume=safe_float(row.get("volume")),
                amount=None,
                change_pct=None,
            )
        )
    return IndexIntradayData(code=code, source="sina_direct", prev_close=None, items=items)


async def get_index_intraday(symbol: str) -> IndexIntradayData:
    code = _validate_index_code(symbol)
    cache_key = dated_cache_key("index_intraday", code)
    cached = cache.get(cache_key)
    if isinstance(cached, IndexIntradayData):
        return cached

    async def load_and_cache() -> IndexIntradayData:
        result = await _load_index_intraday(code)
        cache.set(cache_key, result, ttl=INDEX_INTRADAY.ttl_seconds)
        return result

    return cast(
        IndexIntradayData,
        await _index_intraday_singleflight.do(cache_key, load_and_cache),
    )
