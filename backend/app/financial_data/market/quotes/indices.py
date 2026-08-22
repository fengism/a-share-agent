import logging
from collections.abc import Awaitable
from datetime import date

from app.core.cache import cache, dated_cache_key
from app.core.cache_policies import MARKET_INDICES
from app.core.concurrency.rate_limiter import akshare_semaphore, call_blocking, tencent_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.core.market import safe_float
from app.domain.market import IndexItem, MarketIndices
from app.financial_data.market.quotes.normalization import build_indices_from_sina, normalize_indices
from app.financial_data.market.trading_session import resolve_market_data_cache_policy
from app.infrastructure.providers.provider_chain import BaseProviderChain, ProviderAttempt
from app.infrastructure.providers.registry import get_provider

_indices_singleflight: AsyncSingleFlight[MarketIndices] = AsyncSingleFlight()

logger = logging.getLogger(__name__)


def _get_akshare_provider():
    """延迟获取 akshare provider。"""
    return get_provider("akshare")


def _get_eastmoney_provider():
    """延迟获取东方财富 provider。"""
    return get_provider("eastmoney")


def _get_sina_provider():
    """延迟获取新浪 provider。"""
    return get_provider("sina")


def _get_tencent_provider():
    """延迟获取腾讯 provider。"""
    return get_provider("tencent")



def _safe_scaled(value, scale: float = 1.0) -> float | None:
    """安全转换为浮点数并按比例缩放。

    Args:
        value: 待处理的数值
        scale: 缩放因子（除数）
    Return:
        缩放后的浮点数或 None
    """
    number = safe_float(value)
    if number is None:
        return None
    return float(number) / scale


def _build_em_indices(data, source: str, price_scale: float = 1.0) -> MarketIndices:
    """从东方财富 DataFrame 构造统一的 MarketIndices。

    Args:
        data: 东方财富指数数据 DataFrame
        source: 数据来源标识
        price_scale: 价格字段缩放系数
    Return:
        MarketIndices 模型对象
    """
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
    """通过东方财富直连接口构造大盘指数。

    Args:
        无
    Return:
        MarketIndices 模型对象
    """
    data = _get_eastmoney_provider().fetch_market_indices()
    return _build_em_indices(data, "east_direct", price_scale=1.)


async def _build_akshare_em_indices() -> MarketIndices:
    """通过 akshare 东方财富接口构造大盘指数。

    Args:
        无
    Return:
        MarketIndices 模型对象
    """
    data = await call_blocking(_get_akshare_provider().fetch_market_indices, semaphore=akshare_semaphore)
    return _build_em_indices(data, "em_ak")


async def _build_akshare_sina_indices() -> MarketIndices:
    """通过 akshare 新浪接口构造大盘指数。

    Args:
        无
    Return:
        MarketIndices 模型对象
    """
    data = await call_blocking(_get_akshare_provider().fetch_market_indices_sina, semaphore=akshare_semaphore)
    return build_indices_from_sina(data).model_copy(update={"source": "sina_ak"})


async def _build_sina_direct_indices() -> MarketIndices:
    """通过新浪直连接口构造大盘指数。

    Args:
        无
    Return:
        MarketIndices 模型对象
    """
    data = await call_blocking(_get_sina_provider().fetch_market_indices)
    return build_indices_from_sina(data).model_copy(update={"source": "sina_direct"})


async def _build_tencent_direct_indices() -> MarketIndices:
    """通过腾讯批量直连接口构造大盘指数。"""
    data = await call_blocking(
        _get_tencent_provider().fetch_market_indices,
        semaphore=tencent_semaphore,
    )
    return _build_em_indices(data, "tencent_direct")


async def _require_market_indices(
    source: str,
    loader: Awaitable[MarketIndices],
) -> MarketIndices:
    result = await loader
    if not result.indices:
        raise ValueError(f"{source} 未返回有效大盘指数")
    return result


def _build_indices_attempts() -> list[ProviderAttempt[MarketIndices]]:
    """构造大盘指数多数据源回退链。

    Args:
        无
    Return:
        Provider 尝试列表，按优先级排序
    """
    return [
        ProviderAttempt(
            label="腾讯指数直连",
            loader=lambda: _require_market_indices("腾讯指数直连", _build_tencent_direct_indices()),
            on_error="腾讯直连指数接口失败，尝试新浪直连回退",
        ),
        ProviderAttempt(
            label="新浪指数直连",
            loader=lambda: _require_market_indices("新浪指数直连", _build_sina_direct_indices()),
            on_error="新浪直连指数接口失败，尝试东方财富直连回退",
        ),
        ProviderAttempt(
            label="东方财富指数直连",
            loader=lambda: _require_market_indices(
                "东方财富指数直连",
                call_blocking(_build_east_direct_indices),
            ),
            on_error="东方财富直连指数接口失败，尝试 Akshare 东方财富回退",
        ),
        ProviderAttempt(
            label="Akshare 东方财富指数",
            loader=lambda: _require_market_indices("Akshare 东方财富指数", _build_akshare_em_indices()),
            on_error="Akshare 东方财富指数接口失败，尝试 Akshare 新浪回退",
        ),
        ProviderAttempt(
            label="Akshare 新浪指数",
            loader=lambda: _require_market_indices("Akshare 新浪指数", _build_akshare_sina_indices()),
        ),
    ]


def _add_total_amount(result: MarketIndices) -> MarketIndices:
    """合计沪深主板成交额并写入 total_amount。

    Args:
        result: 已填充 indices 的 MarketIndices
    Return:
        累加完 total_amount 的 MarketIndices
    """
    result.total_amount = 0.0
    for index in result.indices:
        if index.code not in ["000001", "399001"]:
            continue
        if index.amount is None:
            continue
        result.total_amount += safe_float(index.amount)
    return result


async def get_indices() -> MarketIndices:
    """获取大盘指数数据，交易时段缓存 30 秒，休市缓存到下一开盘。

    使用 SingleFlight 防止缓存击穿。

    Args:
        无
    Return:
        MarketIndices 模型对象，附带 total_amount
    """
    cache_key = dated_cache_key("market_indices")
    cache_policy = await resolve_market_data_cache_policy("daily", date.today())
    ttl_seconds = (
        MARKET_INDICES.live_seconds
        if not cache_policy.write_cache
        else cache_policy.ttl_seconds or MARKET_INDICES.stable_seconds
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    async def _load() -> MarketIndices:
        try:
            result = await BaseProviderChain(_build_indices_attempts(), operation="market_indices").run()
        except Exception as error:
            raise UpstreamUnavailableError("大盘指数上游暂时不可用") from error
        result = _add_total_amount(result)
        cache.set(cache_key, result, ttl=ttl_seconds)
        return result

    return await _indices_singleflight.do(cache_key, _load)
