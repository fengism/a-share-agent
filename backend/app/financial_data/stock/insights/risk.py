"""Provider-backed stock risk datasets."""

import asyncio

from app.core.cache import cache, dated_cache_key
from app.core.concurrency.rate_limiter import call_blocking, eastmoney_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import normalize_code
from app.financial_data.stock.insights.fund_flow import get_stock_fund_flow
from app.financial_data.stock.insights.schemas import (
    BlockTradeItem,
    HolderChangeItem,
    MarginTradingItem,
    RiskSection,
    StockRiskData,
)
from app.financial_data.stock.insights.sources import RISK_FIELD_SOURCES, RISK_SOURCE_APIS
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

_risk_singleflight: AsyncSingleFlight[StockRiskData] = AsyncSingleFlight()


async def _load_stock_risk_data(code: str, cache_key: str) -> StockRiskData:
    provider = get_provider("eastmoney")
    sections: list[RiskSection] = ["fund_flow", "margin_trading", "block_trade", "holder_change"]
    values = await asyncio.gather(
        get_stock_fund_flow(code),
        provider_gateway.call(
            "eastmoney",
            "margin_trading",
            lambda: call_blocking(
                provider.fetch_margin_trading,
                code,
                semaphore=eastmoney_semaphore,
            ),
        ),
        provider_gateway.call(
            "eastmoney",
            "block_trade",
            lambda: call_blocking(
                provider.fetch_block_trade,
                code,
                semaphore=eastmoney_semaphore,
            ),
        ),
        provider_gateway.call(
            "eastmoney",
            "holder_num_change",
            lambda: call_blocking(
                provider.fetch_holder_num_change,
                code,
                semaphore=eastmoney_semaphore,
            ),
        ),
        return_exceptions=True,
    )

    unavailable_sections = [
        section
        for section, value in zip(sections, values, strict=True)
        if isinstance(value, Exception)
    ]
    available_sources = {
        section: RISK_FIELD_SOURCES[section]
        for section in sections
        if section not in unavailable_sections and section != "fund_flow"
    }
    available_apis = {
        section: RISK_SOURCE_APIS[section]
        for section in sections
        if section not in unavailable_sections and section != "fund_flow"
    }
    fund_flow, margin, block, holder = values
    if not isinstance(fund_flow, Exception) and fund_flow:
        available_sources["fund_flow"] = fund_flow[0].source
        available_apis["fund_flow"] = fund_flow[0].source_api
    result = StockRiskData(
        code=code,
        fund_flow=[] if isinstance(fund_flow, Exception) else fund_flow[:30],
        margin_trading=[] if isinstance(margin, Exception) else [MarginTradingItem.model_validate(row) for row in margin[:10]],
        block_trade=[] if isinstance(block, Exception) else [BlockTradeItem.model_validate(row) for row in block[:10]],
        holder_change=[] if isinstance(holder, Exception) else [HolderChangeItem.model_validate(row) for row in holder[:4]],
        partial=bool(unavailable_sections),
        unavailable_sections=unavailable_sections,
        field_sources=available_sources,
        source_apis=available_apis,
    )
    cache.set(cache_key, result, ttl=30 if result.partial else 300)
    return result


async def get_stock_risk_data(code: str) -> StockRiskData:
    sym = normalize_code(code)
    cache_key = dated_cache_key("stock_risk", sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        return StockRiskData.model_validate(cached)
    return await _risk_singleflight.do(
        cache_key,
        lambda: _load_stock_risk_data(sym.raw, cache_key),
    )
