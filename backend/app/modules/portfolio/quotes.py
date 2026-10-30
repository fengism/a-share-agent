"""Portfolio adapters over the shared realtime quote capability cache."""

import asyncio
import logging

from app.domain.timezones import market_now
from app.financial_data.hk.schemas import HKStockQuotePage
from app.financial_data.hk.service import hk_market_service
from app.financial_data.stock.public import fetch_realtime_quote_set
from app.financial_data.stock.quotes.realtime import RealtimeQuoteSet, clear_realtime_quote_cache
from app.financial_data.stock.quotes.realtime_cache import QuoteBatch
from app.modules.portfolio.schemas import is_hk_stock_code, normalize_portfolio_stock_code

logger = logging.getLogger(__name__)


def clear_quote_cache() -> None:
    clear_realtime_quote_cache()


async def fetch_quote_batch(codes: list[str]) -> QuoteBatch:
    if not codes:
        return QuoteBatch(
            quotes={},
            quoted_at=market_now().isoformat(timespec="seconds"),
            source="none",
            stale=False,
            quote_sources={},
        )

    normalized_codes = list(dict.fromkeys(normalize_portfolio_stock_code(c) for c in codes if str(c).strip()))
    cn_codes = [c for c in normalized_codes if not is_hk_stock_code(c)]
    hk_codes = [c for c in normalized_codes if is_hk_stock_code(c)]

    cn_quote_task = fetch_realtime_quote_set(cn_codes) if cn_codes else None
    hk_quote_task = (
        hk_market_service.get_stock_quotes(
            codes=hk_codes,
            page=1,
            page_size=max(len(hk_codes), 1),
        )
        if hk_codes
        else None
    )

    quote_set: RealtimeQuoteSet | None = None
    hk_quote_page: HKStockQuotePage | None = None

    if cn_quote_task is not None and hk_quote_task is not None:
        cn_res, hk_res = await asyncio.gather(cn_quote_task, hk_quote_task, return_exceptions=True)
        if isinstance(cn_res, BaseException):
            logger.warning("获取 A 股实时行情失败: %s", cn_res)
        else:
            quote_set = cn_res

        if isinstance(hk_res, BaseException):
            logger.warning("获取港股实时行情失败: %s", hk_res)
        else:
            hk_quote_page = hk_res

        if isinstance(cn_res, BaseException) and isinstance(hk_res, BaseException):
            raise cn_res
    elif cn_quote_task is not None:
        quote_set = await cn_quote_task
    elif hk_quote_task is not None:
        hk_quote_page = await hk_quote_task

    quotes: dict[str, dict] = {}
    quote_sources: dict[str, str] = {}

    if quote_set is not None:
        quotes.update(quote_set.quotes)
        quote_sources.update(quote_set.quote_sources)

    if hk_quote_page is not None:
        for quote in hk_quote_page.items:
            quote_dict = quote.model_dump()
            quote_dict["last_close"] = quote.pre_close
            quotes[quote.code] = quote_dict
            quote_sources[quote.code] = hk_quote_page.source

    if cn_codes and hk_codes:
        source = "mixed"
        quoted_at = market_now().isoformat(timespec="seconds")
        stale = bool(quote_set and quote_set.stale)
    elif quote_set is not None:
        source = quote_set.source
        quoted_at = quote_set.quoted_at or market_now().isoformat(timespec="seconds")
        stale = quote_set.stale
    elif hk_quote_page is not None:
        source = hk_quote_page.source
        quoted_at = hk_quote_page.updated_at or market_now().isoformat(timespec="seconds")
        stale = False
    else:
        source = "none"
        quoted_at = market_now().isoformat(timespec="seconds")
        stale = False

    return QuoteBatch(
        quotes=quotes,
        quoted_at=quoted_at,
        source=source,
        stale=stale,
        quote_sources=quote_sources,
    )


async def fetch_quotes(codes: list[str]) -> dict[str, dict]:
    return (await fetch_quote_batch(codes)).quotes


__all__ = ["clear_quote_cache", "fetch_quote_batch", "fetch_quotes"]
