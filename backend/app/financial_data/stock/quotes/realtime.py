"""Realtime stock quote access independent of product use cases."""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime

from app.configuration import get_settings
from app.core.cache_policies import REALTIME_STOCK_QUOTES
from app.core.concurrency.rate_limiter import call_blocking, tdx_semaphore, tencent_semaphore
from app.core.exceptions import UpstreamUnavailableError
from app.core.market import normalize_code, safe_float
from app.core.metrics import metrics
from app.financial_data.stock.quotes.realtime_cache import (
    QuoteCacheEntry,
    build_quote_batch,
    expire_stale_quotes,
    missing_codes,
    normalized_codes,
    store_fetched_quotes,
)
from app.infrastructure.providers.provider_chain import BaseProviderChain, ProviderAttempt
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RealtimeQuoteSet:
    source: str
    quotes: dict[str, dict]
    quote_sources: dict[str, str]
    quoted_at: str = ""
    stale: bool = False


def _has_usable_price(quote: dict) -> bool:
    return any(
        price is not None and price > 0
        for price in (safe_float(quote.get("price")), safe_float(quote.get("last_close")))
    )


async def _load_quote_source(source: str, fetcher, codes: list[str], *, semaphore) -> RealtimeQuoteSet:
    quotes = await call_blocking(fetcher, codes, semaphore=semaphore)
    if not isinstance(quotes, dict):
        raise ValueError(f"{source} 实时行情响应结构无效")
    requested_codes = set(codes)
    usable_quotes = {
        code: quote
        for code, quote in quotes.items()
        if code in requested_codes and isinstance(quote, dict) and _has_usable_price(quote)
    }
    if not usable_quotes:
        raise ValueError(f"{source} 未返回有效实时行情")
    return RealtimeQuoteSet(
        source=source,
        quotes=usable_quotes,
        quote_sources={code: source for code in usable_quotes},
    )


def _summarize_sources(codes: list[str], quote_sources: dict[str, str]) -> str:
    ordered_sources = [quote_sources[code] for code in codes if code in quote_sources]
    return "+".join(dict.fromkeys(ordered_sources)) or "tencent"


async def _fetch_realtime_quote_set_uncached(codes: list[str]) -> RealtimeQuoteSet:
    """优先使用腾讯行情，并通过 TDX HTTP 补齐缺失代码。"""
    if not codes:
        return RealtimeQuoteSet(source="tencent", quotes={}, quote_sources={})
    normalized_codes = list(dict.fromkeys(normalize_code(code).raw for code in codes))
    tdx_http_enabled = get_settings().tdx_http_enabled
    attempts: list[ProviderAttempt[RealtimeQuoteSet]] = [
        ProviderAttempt(
            label="tencent",
            loader=lambda: _load_quote_source(
                "tencent",
                get_provider("tencent").fetch_stock_quotes,
                normalized_codes,
                semaphore=tencent_semaphore,
            ),
            on_error="腾讯实时行情不可用",
        )
    ]
    if tdx_http_enabled:
        attempts.append(
            ProviderAttempt(
                label="tdx_http",
                loader=lambda: _load_quote_source(
                    "tdx_http",
                    get_provider("tdx_http").fetch_stock_quotes,
                    normalized_codes,
                    semaphore=tdx_semaphore,
                ),
                on_error="TDX HTTP 实时行情不可用",
            )
        )
    try:
        primary = await BaseProviderChain(attempts, operation="stock_quotes").run()
    except Exception as error:
        raise UpstreamUnavailableError("个股实时行情上游暂时不可用") from error
    missing_codes = [code for code in normalized_codes if code not in primary.quotes]
    if primary.source != "tencent" or not tdx_http_enabled or not missing_codes:
        return primary

    try:
        fallback = await provider_gateway.call(
            "tdx_http",
            "stock_quotes",
            lambda: _load_quote_source(
                "tdx_http",
                get_provider("tdx_http").fetch_stock_quotes,
                missing_codes,
                semaphore=tdx_semaphore,
            ),
            is_fallback_attempt=True,
        )
    except Exception as exc:
        logger.info("TDX HTTP 未能补齐部分实时行情: codes=%s, error=%s", missing_codes, exc)
        return primary

    merged_quotes = {**primary.quotes, **fallback.quotes}
    quote_sources = {**primary.quote_sources, **fallback.quote_sources}
    return RealtimeQuoteSet(
        source=_summarize_sources(normalized_codes, quote_sources),
        quotes=merged_quotes,
        quote_sources=quote_sources,
    )


_quote_cache: dict[str, QuoteCacheEntry] = {}
_quote_cache_lock = asyncio.Lock()


def clear_realtime_quote_cache() -> None:
    _quote_cache.clear()
    metrics.record_cache_event("realtime_quotes", "clear", size=0)




def _quote_cache_ttls() -> tuple[int, int]:
    settings = get_settings()
    fresh = max(0, int(getattr(settings, "portfolio_quote_cache_ttl_seconds", REALTIME_STOCK_QUOTES.fresh_seconds)))
    stale = max(fresh, int(getattr(settings, "portfolio_quote_stale_ttl_seconds", REALTIME_STOCK_QUOTES.stale_seconds)))
    return fresh, stale

def _cached_quote_set(codes: list[str], *, now: float) -> RealtimeQuoteSet:
    fallback_time = datetime.now().isoformat(timespec="seconds")
    fresh_ttl, stale_ttl = _quote_cache_ttls()
    batch = build_quote_batch(
        _quote_cache,
        codes,
        now=now,
        fresh_ttl=fresh_ttl,
        stale_ttl=stale_ttl,
        fallback_quoted_at=fallback_time,
    )
    return RealtimeQuoteSet(
        source=batch.source,
        quotes=batch.quotes,
        quote_sources=batch.quote_sources,
        quoted_at=batch.quoted_at,
        stale=batch.stale,
    )


async def fetch_realtime_quote_set(codes: list[str]) -> RealtimeQuoteSet:
    normalized = normalized_codes(codes, normalize_code)
    if not normalized:
        return RealtimeQuoteSet(source="tencent", quotes={}, quote_sources={})
    now = time.monotonic()
    cached = _cached_quote_set(normalized, now=now)
    if len(cached.quotes) == len(normalized) and not cached.stale:
        metrics.record_cache_event("realtime_quotes", "hit", size=len(_quote_cache))
        return cached

    async with _quote_cache_lock:
        now = time.monotonic()
        cached = _cached_quote_set(normalized, now=now)
        fresh_ttl, stale_ttl = _quote_cache_ttls()
        missing = missing_codes(
            _quote_cache,
            normalized,
            build_quote_batch(
                _quote_cache,
                normalized,
                now=now,
                fresh_ttl=fresh_ttl,
                stale_ttl=stale_ttl,
                fallback_quoted_at=datetime.now().isoformat(timespec="seconds"),
            ),
            now=now,
            fresh_ttl=fresh_ttl,
        )
        if not missing:
            return cached
        try:
            fetched = await _fetch_realtime_quote_set_uncached(missing)
        except Exception:
            if cached.quotes:
                metrics.record_cache_event("realtime_quotes", "stale_fallback", size=len(_quote_cache))
                return cached
            raise

        cached_at = time.monotonic()
        fallback_time = datetime.now().isoformat(timespec="seconds")
        store_fetched_quotes(
            _quote_cache,
            fetched.quotes,
            normalized,
            cached_at=cached_at,
            fallback_quoted_at=fallback_time,
            source=fetched.source,
            quote_sources=fetched.quote_sources,
            normalize_code_func=normalize_code,
            entry_factory=QuoteCacheEntry,
            logger=logger,
        )
        for cache_size in expire_stale_quotes(
            _quote_cache,
            now=cached_at,
            stale_ttl=stale_ttl,
        ):
            metrics.record_cache_event("realtime_quotes", "expiration", size=cache_size)
        result = _cached_quote_set(normalized, now=cached_at)
        metrics.record_cache_event("realtime_quotes", "set", size=len(_quote_cache))
        return result


async def fetch_realtime_quotes(codes: list[str]) -> dict[str, dict]:
    """批量获取标准化实时行情。"""
    return (await fetch_realtime_quote_set(codes)).quotes
