"""On-demand 20-day batches. A cursor pins the source and trading dates.

Only complete batches are published; an older-batch failure never replaces the
first batch or splices another provider into the same series.
"""

from dataclasses import dataclass, field
from uuid import uuid4

from app.core.cache import TTLCache, dated_cache_key, dated_cache_key_no_day
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import ResourceNotFoundError, UpstreamUnavailableError
from app.core.market import normalize_code
from app.financial_data.stock.insights import fund_flow as legacy
from app.financial_data.stock.insights.schemas import StockFundFlowItem, StockFundFlowPage
from app.infrastructure.providers.registry import get_provider

_BATCH_SIZE = 20
_SESSION_TTL = 60 * 60
_sessions = TTLCache(maxsize=256, name="fund_flow_page_sessions")
_first_pages = TTLCache(maxsize=256, name="fund_flow_first_pages")
_flight: AsyncSingleFlight[StockFundFlowPage] = AsyncSingleFlight()


@dataclass
class _Session:
    code: str
    source: str
    source_api: str
    dates: list[str]
    # Non-TDX providers return their whole series cheaply; serve its slices.
    snapshot: list[StockFundFlowItem] | None = None
    batches: dict[int, list[StockFundFlowItem]] = field(default_factory=dict)


def _page(token: str, session: _Session, offset: int) -> StockFundFlowPage:
    rows = session.batches[offset]
    next_offset = offset + len(rows)
    return StockFundFlowPage(
        items=rows, total=len(session.dates), source=session.source, source_api=session.source_api,
        next_cursor=f"{token}:{next_offset}" if next_offset < len(session.dates) else None,
    )


def _store_session(session: _Session) -> StockFundFlowPage:
    token = uuid4().hex
    _sessions.set(token, session, ttl=_SESSION_TTL)
    return _page(token, session, 0)


def _rows(raw, attempt) -> list[StockFundFlowItem]:
    rows = legacy._normalize_fund_flow(raw)
    if not rows:
        raise ValueError("资金流批次为空")
    return [row.model_copy(update={"source": attempt.source_id, "source_api": attempt.source_api}) for row in rows]


async def _first_page(code: str, key: str) -> StockFundFlowPage:
    # A fresh cached whole series is safe to slice; a partial TDX batch never
    # enters the legacy whole-series cache.
    full_key = dated_cache_key("stock_fund_flow", code)
    full = legacy.cache.get(full_key)
    if full is not None and full is not legacy._FUND_FLOW_UNAVAILABLE:
        rows = legacy._normalize_fund_flow(full)
        if rows and not any(row.is_stale for row in rows):
            page = _store_session(_Session(
                code, rows[0].source, rows[0].source_api, [r.date for r in rows], rows, {0: rows[:_BATCH_SIZE]},
            ))
            _first_pages.set(key, page, ttl=300)
            return page
    for index, attempt in enumerate(legacy._FUND_FLOW_ATTEMPTS):
        try:
            provider = get_provider(attempt.provider)
            is_tdx = attempt.provider == "tdxhub"
            raw = await legacy.provider_gateway.call_blocking(
                attempt.provider, attempt.operation,
                getattr(provider, "fetch_stock_fund_flow_page" if is_tdx else attempt.method), code,
                semaphore=attempt.semaphore, is_fallback_attempt=index > 0, max_attempts=attempt.max_attempts,
            )
            rows = _rows(raw["items"] if is_tdx else raw, attempt)
            dates = raw["dates"] if is_tdx else [row.date for row in rows]
            if is_tdx and (not dates or len(dates) > 60 or [r.date for r in rows] != dates[:_BATCH_SIZE]):
                raise ValueError("TDX 资金流批次不完整")
            session = _Session(
                code, attempt.source_id, attempt.source_api, dates,
                None if is_tdx else rows, {0: rows[:_BATCH_SIZE]},
            )
            if session.snapshot is not None or len(rows) == len(dates):
                legacy.cache.set(full_key, rows, ttl=300)
                legacy.cache.set(dated_cache_key_no_day("stock_fund_flow_last_good", code), rows, ttl=86400)
            page = _store_session(session)
            _first_pages.set(key, page, ttl=300)
            return page
        except Exception as error:
            legacy.logger.info("资金流首批数据源失败: provider=%s code=%s error=%s", attempt.provider, code, error)
    stale = legacy.cache.get(dated_cache_key_no_day("stock_fund_flow_last_good", code))
    if stale:
        rows = [r.model_copy(update={"is_stale": True}) for r in legacy._normalize_fund_flow(stale)]
        page = _store_session(_Session(
            code, rows[0].source, rows[0].source_api, [r.date for r in rows], rows, {0: rows[:_BATCH_SIZE]},
        ))
        _first_pages.set(key, page, ttl=30)
        return page
    _first_pages.set(key, legacy._FUND_FLOW_UNAVAILABLE, ttl=30)
    raise UpstreamUnavailableError("个股资金流首批加载失败，请稍后重试")


async def _next_page(token: str, session: _Session, offset: int) -> StockFundFlowPage:
    loaded = offset not in session.batches
    if loaded:
        if session.snapshot is not None:
            rows = session.snapshot[offset:offset + _BATCH_SIZE]
        else:
            attempt = next(item for item in legacy._FUND_FLOW_ATTEMPTS if item.provider == "tdxhub")
            dates = session.dates[offset:offset + _BATCH_SIZE]
            try:
                raw = await legacy.provider_gateway.call_blocking(
                    "tdxhub", attempt.operation, get_provider("tdxhub").fetch_stock_fund_flow_history,
                    session.code, dates=dates, semaphore=attempt.semaphore,
                    is_fallback_attempt=True, max_attempts=1,
                )
                rows = _rows(raw, attempt)
                if [r.date for r in rows] != dates:
                    raise ValueError("TDX 资金流批次缺少交易日")
            except Exception as error:
                raise UpstreamUnavailableError("更早资金流批次加载失败，已加载数据保留，请重试该批") from error
        session.batches[offset] = rows
    # Only a complete source-consistent snapshot may serve as last-good fallback.
    if loaded and sum(len(rows) for rows in session.batches.values()) == len(session.dates):
        full = [row for start in sorted(session.batches) for row in session.batches[start]]
        if not any(row.is_stale for row in full):
            # A pinned older session must not populate a later day's fresh cache.
            last_key = dated_cache_key_no_day("stock_fund_flow_last_good", session.code)
            previous = legacy.cache.get(last_key)
            previous_date = legacy._parse_fund_flow_date(previous[0].date) if previous else None
            completed_date = legacy._parse_fund_flow_date(full[0].date)
            if previous_date is None or (completed_date is not None and completed_date >= previous_date):
                legacy.cache.set(last_key, full, ttl=86400)
    return _page(token, session, offset)


async def get_stock_fund_flow_page(code: str, cursor: str | None = None) -> StockFundFlowPage:
    code = normalize_code(code).raw
    if cursor is None:
        key = dated_cache_key("stock_fund_flow_page", code)
        cached = _first_pages.get(key)
        if cached is legacy._FUND_FLOW_UNAVAILABLE:
            raise UpstreamUnavailableError("个股资金流首批加载失败，请稍后重试")
        if cached is not None:
            # The cursor session can be evicted before the first-page cache.
            if not cached.next_cursor or _sessions.get(cached.next_cursor.split(":")[0]) is not None:
                return cached
        return await _flight.do(key, lambda: _first_page(code, key))
    try:
        token, offset_text = cursor.split(":")
        offset = int(offset_text)
    except (ValueError, TypeError):
        raise ResourceNotFoundError("资金流分页已失效，请重新加载最新数据") from None
    session = _sessions.get(token)
    if (session is None or session.code != code or offset <= 0 or offset % _BATCH_SIZE
            or offset >= len(session.dates) or offset - _BATCH_SIZE not in session.batches):
        raise ResourceNotFoundError("资金流分页已失效，请重新加载最新数据")
    return await _flight.do(f"{token}:{offset}", lambda: _next_page(token, session, offset))
