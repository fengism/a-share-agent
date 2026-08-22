"""Portfolio adapters over the shared realtime quote capability cache."""

from datetime import datetime

from app.financial_data.stock.public import fetch_realtime_quote_set
from app.financial_data.stock.quotes.realtime import clear_realtime_quote_cache
from app.financial_data.stock.quotes.realtime_cache import QuoteBatch


def clear_quote_cache() -> None:
    clear_realtime_quote_cache()


async def fetch_quote_batch(codes: list[str]) -> QuoteBatch:
    quote_set = await fetch_realtime_quote_set(codes)
    return QuoteBatch(
        quotes=quote_set.quotes,
        quoted_at=quote_set.quoted_at or datetime.now().isoformat(timespec="seconds"),
        source=quote_set.source,
        stale=quote_set.stale,
        quote_sources=quote_set.quote_sources,
    )


async def fetch_quotes(codes: list[str]) -> dict[str, dict]:
    return (await fetch_quote_batch(codes)).quotes


__all__ = ["clear_quote_cache", "fetch_quote_batch", "fetch_quotes"]
