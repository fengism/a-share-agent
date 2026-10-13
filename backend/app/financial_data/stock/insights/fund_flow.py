"""个股历史资金流向服务。"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import cast

from app.core.cache import dated_cache_key, dated_cache_key_no_day
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import eastmoney_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.core.market import is_hk_code, normalize_code
from app.financial_data.stock.insights.schemas import StockFundFlowItem
from app.financial_data.stock.insights.sources import (
    EASTMONEY_FUND_FLOW_API,
    EASTMONEY_FUND_FLOW_SOURCE_ID,
    TDXHUB_FUND_FLOW_API,
    TDXHUB_FUND_FLOW_SOURCE_ID,
)
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)
_tdxhub_fund_flow_semaphore = asyncio.Semaphore(1)
_fund_flow_singleflight: AsyncSingleFlight[list[StockFundFlowItem]] = AsyncSingleFlight()
_FUND_FLOW_FAILURE_TTL_SECONDS = 30
_FUND_FLOW_LAST_GOOD_TTL_SECONDS = 24 * 60 * 60
_FUND_FLOW_MAX_DAYS = 60
_FUND_FLOW_UNAVAILABLE = object()


@dataclass(frozen=True)
class _FundFlowAttempt:
    provider: str
    operation: str
    method: str
    source_id: str
    source_api: str
    semaphore: asyncio.Semaphore
    max_attempts: int | None = None


_FUND_FLOW_ATTEMPTS = (
    _FundFlowAttempt(
        provider="eastmoney",
        operation="stock_fund_flow",
        method="fetch_stock_fund_flow",
        source_id=EASTMONEY_FUND_FLOW_SOURCE_ID,
        source_api=EASTMONEY_FUND_FLOW_API,
        semaphore=eastmoney_semaphore,
    ),
    _FundFlowAttempt(
        provider="tdxhub",
        operation="stock_fund_flow_history",
        method="fetch_stock_fund_flow_history",
        source_id=TDXHUB_FUND_FLOW_SOURCE_ID,
        source_api=TDXHUB_FUND_FLOW_API,
        semaphore=_tdxhub_fund_flow_semaphore,
        max_attempts=1,
    ),
    # 百度资金流接口目前因 WAF 风控拦截，暂不参与调度；代码与接口逻辑予以保留
    # _FundFlowAttempt(
    #     provider="baidu",
    #     operation="stock_fund_flow_history",
    #     method="fetch_stock_fund_flow_history",
    #     source_id=BAIDU_FUND_FLOW_SOURCE_ID,
    #     source_api=BAIDU_FUND_FLOW_API,
    #     semaphore=baidu_semaphore,
    # ),
)


def _parse_fund_flow_date(value: str) -> date | None:
    text = value.strip()
    for date_format in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _normalize_fund_flow(items: object) -> list[StockFundFlowItem]:
    result = [StockFundFlowItem.model_validate(item) for item in cast(list[object], items)]
    decorated = [
        (item, index, _parse_fund_flow_date(item.date))
        for index, item in enumerate(result)
    ]
    decorated.sort(
        key=lambda entry: (
            0 if entry[2] is not None else 1,
            -entry[2].toordinal() if entry[2] is not None else 0,
            entry[1],
        )
    )
    unique_result: list[StockFundFlowItem] = []
    seen_dates: set[str] = set()
    for item, _, parsed_date in decorated:
        date_identity = parsed_date.isoformat() if parsed_date is not None else item.date.strip()
        if date_identity in seen_dates:
            continue
        seen_dates.add(date_identity)
        unique_result.append(item)
        if len(unique_result) == _FUND_FLOW_MAX_DAYS:
            break
    return unique_result


async def _fetch_remote_stock_fund_flow(code: str) -> list[StockFundFlowItem]:
    last_error: Exception | None = None
    for index, attempt in enumerate(_FUND_FLOW_ATTEMPTS):
        try:
            provider = get_provider(attempt.provider)
            rows = await provider_gateway.call_blocking(
                attempt.provider,
                attempt.operation,
                getattr(provider, attempt.method),
                code,
                semaphore=attempt.semaphore,
                is_fallback_attempt=index > 0,
                max_attempts=attempt.max_attempts,
            )
            result = [
                StockFundFlowItem.model_validate(row).model_copy(
                    update={"source": attempt.source_id, "source_api": attempt.source_api}
                )
                for row in rows
            ]
            if not result:
                raise ValueError(f"{attempt.provider} 个股历史资金流为空")
            return _normalize_fund_flow(result)
        except Exception as error:
            last_error = error
            logger.info(
                "个股历史资金流数据源失败: provider=%s code=%s error=%s",
                attempt.provider,
                code,
                error,
            )
    if last_error is not None:
        raise last_error
    raise RuntimeError("个股历史资金流数据源为空")


async def _load_stock_fund_flow(
    code: str,
    cache_key: str,
    last_good_key: str,
) -> list[StockFundFlowItem]:
    try:
        result = await _fetch_remote_stock_fund_flow(code)
    except Exception as error:
        stale = cache.get(last_good_key)
        if stale is not None:
            result = _normalize_fund_flow([
                StockFundFlowItem.model_validate(item).model_copy(update={"is_stale": True})
                for item in stale
            ])
            cache.set(cache_key, result, ttl=_FUND_FLOW_FAILURE_TTL_SECONDS)
            logger.warning(
                "个股资金流上游不可用，使用最近成功缓存: code=%s error_type=%s",
                code,
                type(error).__name__,
            )
            return result
        cache.set(cache_key, _FUND_FLOW_UNAVAILABLE, ttl=_FUND_FLOW_FAILURE_TTL_SECONDS)
        raise UpstreamUnavailableError("个股资金流上游暂时不可用，请稍后重试") from error

    cache.set(cache_key, result, ttl=300)
    cache.set(last_good_key, result, ttl=_FUND_FLOW_LAST_GOOD_TTL_SECONDS)
    return result


async def get_stock_fund_flow(code: str) -> list[StockFundFlowItem]:
    """获取股票最近最多 60 个交易日的分级资金净流入。"""
    if is_hk_code(code):
        return []

    sym = normalize_code(code)
    cache_key = dated_cache_key("stock_fund_flow", sym.raw)
    last_good_key = dated_cache_key_no_day("stock_fund_flow_last_good", sym.raw)
    cached = cache.get(cache_key)
    if cached is _FUND_FLOW_UNAVAILABLE:
        raise UpstreamUnavailableError("个股资金流上游暂时不可用，请稍后重试")
    if cached is not None:
        return _normalize_fund_flow(cached)
    return cast(
        list[StockFundFlowItem],
        await _fund_flow_singleflight.do(
            cache_key,
            lambda: _load_stock_fund_flow(sym.raw, cache_key, last_good_key),
        ),
    )
