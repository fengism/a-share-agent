import asyncio
import logging

from app.models.market import IndexItem, MarketIndices
from app.services.base.provider_chain import BaseProviderChain, ProviderAttempt
from app.services.providers.akshare import akshare_provider as _akshare_provider
from app.services.providers.eastmoney import eastmoney_provider as _eastmoney_provider
from app.services.providers.sina import sina_provider as _sina_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.market_utils import build_indices_from_sina, normalize_indices
from app.utils.data_clean import safe_float
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)



def _safe_scaled(value, scale: float = 1.0) -> float | None:
    number = safe_float(value)
    if number is None:
        return None
    return number / scale


def _build_em_indices(data, source: str, price_scale: float = 1.0) -> MarketIndices:
    return MarketIndices(indices=normalize_indices([
        IndexItem(
            code=str(row.get("代码", "")),
            name=str(row.get("名称", "")),
            price=_safe_scaled(row.get("最新价"), price_scale),
            change_pct=_safe_scaled(row.get("涨跌幅"), price_scale),
            volume=safe_float(row.get("成交量")),
            amount=safe_float(row.get("成交额")),
            open=_safe_scaled(row.get("今开"), price_scale),
            high=_safe_scaled(row.get("最高"), price_scale),
            low=_safe_scaled(row.get("最低"), price_scale),
            amplitude=_safe_scaled(row.get("振幅"), price_scale),
            pre_close=_safe_scaled(row.get("昨收"), price_scale),
        )
        for _, row in data.iterrows()
    ]), source=source)


def _build_east_direct_indices() -> MarketIndices:
    data = _eastmoney_provider.fetch_market_indices_direct()
    return _build_em_indices(data, "east_direct", price_scale=100)


async def _build_akshare_em_indices() -> MarketIndices:
    data = await call_blocking(_akshare_provider.fetch_market_indices)
    return _build_em_indices(data, "em_ak")


async def _build_akshare_sina_indices() -> MarketIndices:
    data = await call_blocking(_akshare_provider.fetch_market_indices_sina)
    return build_indices_from_sina(data).model_copy(update={"source": "sina_ak"})


async def _build_sina_direct_indices() -> MarketIndices:
    data = await call_blocking(_sina_provider.fetch_market_indices_direct)
    return build_indices_from_sina(data).model_copy(update={"source": "sina_direct"})


def _build_indices_attempts() -> list[ProviderAttempt]:
    return [
        ProviderAttempt(
            label="Akshare 东方财富指数",
            loader=_build_akshare_em_indices,
            on_error="大盘指数接口不可用，尝试东方财富直连回退",
        ),
        ProviderAttempt(
            label="东方财富指数直连",
            loader=lambda: call_blocking(_build_east_direct_indices),
            on_error="东方财富直连指数接口失败，尝试新浪 akshare 回退",
        ),
        ProviderAttempt(
            label="Akshare 新浪指数",
            loader=_build_akshare_sina_indices,
            on_error="新浪指数接口失败，尝试新浪直连回退",
        ),
        ProviderAttempt(
            label="新浪指数直连",
            loader=_build_sina_direct_indices,
        ),
    ]


def _add_total_amount(result: MarketIndices) -> MarketIndices:
    result.total_amount = 0.0
    for index in result.indices:
        if index.code not in ["000001", "399001"]:
            continue
        if index.amount is None:
            continue
        result.total_amount += safe_float(index.amount)
    return result


async def get_indices() -> MarketIndices:
    cache_key = dated_cache_key("market_indices")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = await BaseProviderChain(_build_indices_attempts()).run()
    result = _add_total_amount(result)
    cache.set(cache_key, result, ttl=300)
    return result


if __name__ == "__main__":
    indices = asyncio.run(get_indices())
    print(indices)
