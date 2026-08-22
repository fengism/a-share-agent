"""Shared realtime quote cache data structures and pure helpers."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class QuoteBatch:
    quotes: dict[str, dict]
    quoted_at: str
    source: str = "tencent"
    stale: bool = False
    quote_sources: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class QuoteCacheEntry:
    quote: dict
    cached_at: float
    quoted_at: str
    source: str = "tencent"


def normalized_codes(codes: list[str], normalize_code_func: Callable) -> list[str]:
    return list(dict.fromkeys(normalize_code_func(code).raw for code in codes if code))


def build_quote_batch(
    cache: dict[str, QuoteCacheEntry],
    codes: list[str],
    *,
    now: float,
    fresh_ttl: int,
    stale_ttl: int,
    fallback_quoted_at: str,
) -> QuoteBatch:
    quotes: dict[str, dict] = {}
    quote_times: list[str] = []
    quote_sources: list[str] = []
    stale = False
    for code in codes:
        entry = cache.get(code)
        if entry is None:
            continue
        age = now - entry.cached_at
        if age > stale_ttl:
            continue
        quotes[code] = dict(entry.quote)
        quote_times.append(entry.quoted_at)
        quote_sources.append(entry.source)
        stale = stale or age > fresh_ttl
    return QuoteBatch(
        quotes=quotes,
        quoted_at=max(quote_times, default=fallback_quoted_at),
        source="+".join(dict.fromkeys(quote_sources)) or "tencent",
        stale=stale,
        quote_sources={code: cache[code].source for code in quotes},
    )


def missing_codes(
    cache: dict[str, QuoteCacheEntry],
    codes: list[str],
    batch: QuoteBatch,
    *,
    now: float,
    fresh_ttl: int,
) -> list[str]:
    return [
        code
        for code in codes
        if code not in batch.quotes or now - cache[code].cached_at > fresh_ttl
    ]


def store_fetched_quotes(
    cache: dict[str, QuoteCacheEntry],
    fetched: dict[str, dict],
    requested_codes: list[str],
    *,
    cached_at: float,
    fallback_quoted_at: str,
    source: str,
    quote_sources: dict[str, str] | None,
    normalize_code_func: Callable,
    entry_factory: Callable[..., QuoteCacheEntry],
    logger: logging.Logger,
) -> None:
    for code, quote in fetched.items():
        try:
            normalized_code = normalize_code_func(code).raw
        except ValueError:
            logger.warning("忽略无法识别的行情代码: %s", code)
            continue
        if normalized_code not in requested_codes or not quote:
            continue
        quoted_at = str(quote.get("quoted_at") or fallback_quoted_at)
        cache[normalized_code] = entry_factory(
            quote=dict(quote),
            cached_at=cached_at,
            quoted_at=quoted_at,
            source=(quote_sources or {}).get(normalized_code, source),
        )


def expire_stale_quotes(
    cache: dict[str, QuoteCacheEntry],
    *,
    now: float,
    stale_ttl: int,
) -> list[int]:
    expired_codes = [
        code
        for code, entry in cache.items()
        if now - entry.cached_at > stale_ttl
    ]
    remaining_sizes = []
    for code in expired_codes:
        cache.pop(code, None)
        remaining_sizes.append(len(cache))
    return remaining_sizes
