import asyncio
import logging
import time
from datetime import datetime

import app.modules.portfolio.builder as portfolio_builder
import app.modules.portfolio.quote_cache as portfolio_quote_cache
from app.configuration import get_settings
from app.core.concurrency.rate_limiter import (
    call_blocking,
    database_semaphore,
)
from app.core.market import normalize_code
from app.core.metrics import metrics
from app.infrastructure.persistence import portfolio as portfolio_store
from app.market_data.stock.public import fetch_realtime_quotes, get_stock_name_map
from app.modules.portfolio.quote_cache import (
    QuoteBatch,
)
from app.modules.portfolio.quote_cache import (
    QuoteCacheEntry as _QuoteCacheEntry,
)
from app.modules.portfolio.schemas import (
    PortfolioPosition,
    PortfolioPositionCreate,
    PortfolioResponse,
)

logger = logging.getLogger(__name__)


_quote_cache: dict[str, _QuoteCacheEntry] = {}
_quote_cache_lock = asyncio.Lock()


def clear_quote_cache() -> None:
    _quote_cache.clear()
    metrics.record_cache_event("portfolio_quotes", "clear", size=0)


def _normalized_codes(codes: list[str]) -> list[str]:
    return portfolio_quote_cache.normalized_codes(codes, normalize_code)


def _build_quote_batch(
    codes: list[str],
    *,
    now: float,
    fresh_ttl: int,
    stale_ttl: int,
) -> QuoteBatch:
    return portfolio_quote_cache.build_quote_batch(
        _quote_cache,
        codes,
        now=now,
        fresh_ttl=fresh_ttl,
        stale_ttl=stale_ttl,
        fallback_quoted_at=datetime.now().isoformat(timespec="seconds"),
    )


async def fetch_quote_batch(codes: list[str]) -> QuoteBatch:
    normalized_codes = _normalized_codes(codes)
    if not normalized_codes:
        return QuoteBatch(quotes={}, quoted_at=datetime.now().isoformat(timespec="seconds"))

    settings = get_settings()
    fresh_ttl = max(0, settings.portfolio_quote_cache_ttl_seconds)
    stale_ttl = max(fresh_ttl, settings.portfolio_quote_stale_ttl_seconds)
    now = time.monotonic()
    batch = _build_quote_batch(
        normalized_codes,
        now=now,
        fresh_ttl=fresh_ttl,
        stale_ttl=stale_ttl,
    )
    if len(batch.quotes) == len(normalized_codes) and not batch.stale:
        metrics.record_cache_event("portfolio_quotes", "hit", size=len(_quote_cache))
        return batch
    metrics.record_cache_event("portfolio_quotes", "miss", size=len(_quote_cache))

    async with _quote_cache_lock:
        now = time.monotonic()
        batch = _build_quote_batch(
            normalized_codes,
            now=now,
            fresh_ttl=fresh_ttl,
            stale_ttl=stale_ttl,
        )
        missing_codes = portfolio_quote_cache.missing_codes(
            _quote_cache,
            normalized_codes,
            batch,
            now=now,
            fresh_ttl=fresh_ttl,
        )
        if not missing_codes:
            metrics.record_cache_event("portfolio_quotes", "hit", size=len(_quote_cache))
            return batch

        try:
            fetched = await fetch_realtime_quotes(missing_codes)
        except Exception:
            logger.warning("批量获取持仓实时行情失败，尝试使用陈旧缓存", exc_info=True)
            fetched = {}

        cached_at = time.monotonic()
        fallback_time = datetime.now().isoformat(timespec="seconds")
        portfolio_quote_cache.store_fetched_quotes(
            _quote_cache,
            fetched,
            normalized_codes,
            cached_at=cached_at,
            fallback_quoted_at=fallback_time,
            normalize_code_func=normalize_code,
            entry_factory=_QuoteCacheEntry,
            logger=logger,
        )

        remaining_sizes = portfolio_quote_cache.expire_stale_quotes(
            _quote_cache,
            now=cached_at,
            stale_ttl=stale_ttl,
        )
        for cache_size in remaining_sizes:
            metrics.record_cache_event("portfolio_quotes", "expiration", size=cache_size)

        result = _build_quote_batch(
            normalized_codes,
            now=cached_at,
            fresh_ttl=fresh_ttl,
            stale_ttl=stale_ttl,
        )
        metrics.record_cache_event("portfolio_quotes", "set", size=len(_quote_cache))
        if result.stale:
            metrics.record_cache_event("portfolio_quotes", "stale_fallback", size=len(_quote_cache))
        return result


async def fetch_quotes(codes: list[str]) -> dict[str, dict]:
    return (await fetch_quote_batch(codes)).quotes


def _current_price(quote: dict) -> float | None:
    return portfolio_builder.current_price(quote)


def position_from_row(row: dict, quote: dict) -> PortfolioPosition:
    return portfolio_builder.position_from_row(row, quote, _current_price)


def build_portfolio(
    rows: list[dict],
    quotes: dict[str, dict],
    *,
    quoted_at: str | None = None,
    quote_source: str = "tencent",
    quote_stale: bool = False,
) -> PortfolioResponse:
    return portfolio_builder.build_portfolio(
        rows,
        quotes,
        quoted_at=quoted_at or datetime.now().isoformat(timespec="seconds"),
        quote_source=quote_source,
        quote_stale=quote_stale,
        position_factory=position_from_row,
    )


async def get_portfolio(user_id: int) -> PortfolioResponse:
    rows = await call_blocking(
        portfolio_store.list_positions,
        user_id,
        semaphore=database_semaphore,
    )
    quote_batch = await fetch_quote_batch([row["stock_code"] for row in rows])
    return build_portfolio(
        rows,
        quote_batch.quotes,
        quoted_at=quote_batch.quoted_at,
        quote_source=quote_batch.source,
        quote_stale=quote_batch.stale,
    )


async def add_position(request: PortfolioPositionCreate, user_id: int) -> PortfolioPosition | None:
    quotes = await fetch_quotes([request.stock_code])
    quote = quotes.get(request.stock_code, {})
    stock_name = str(quote.get("name") or "").strip()
    if not stock_name:
        stock_name = (await get_stock_name_map()).get(request.stock_code, "")
    if not stock_name:
        return None

    row = await call_blocking(
        portfolio_store.create_position,
        user_id,
        request.stock_code,
        stock_name,
        request.buy_price,
        request.buy_time.isoformat(timespec="seconds"),
        request.shares,
        semaphore=database_semaphore,
    )
    return position_from_row(row, quote)


async def delete_position(position_id: int, user_id: int) -> bool:
    return await call_blocking(
        portfolio_store.delete_position,
        user_id,
        position_id,
        semaphore=database_semaphore,
    )
