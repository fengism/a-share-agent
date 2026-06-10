import asyncio
import logging

from app.models.market import IndexItem, MarketIndices
from app.services.base.provider_chain import BaseProviderChain, ProviderAttempt
from app.services.providers import get_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.market_utils import build_indices_from_sina, normalize_indices
from app.utils.data_clean import safe_float
from app.utils.rate_limiter import call_blocking

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
    return number / scale


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
    data = await call_blocking(_get_akshare_provider().fetch_market_indices)
    return _build_em_indices(data, "em_ak")


async def _build_akshare_sina_indices() -> MarketIndices:
    """通过 akshare 新浪接口构造大盘指数。

    Args:
        无
    Return:
        MarketIndices 模型对象
    """
    data = await call_blocking(_get_akshare_provider().fetch_market_indices_sina)
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


def _build_indices_attempts() -> list[ProviderAttempt]:
    """构造大盘指数多数据源回退链。

    Args:
        无
    Return:
        Provider 尝试列表，按优先级排序
    """
    return [
        ProviderAttempt(
            label="东方财富指数直连",
            loader=lambda: call_blocking(_build_east_direct_indices),
            on_error="东方财富直连指数接口失败，尝试新浪 akshare 回退",
        ),
        ProviderAttempt(
            label="新浪指数直连",
            loader=_build_sina_direct_indices,
        ),
        ProviderAttempt(
            label="Akshare 东方财富指数",
            loader=_build_akshare_em_indices,
            on_error="大盘指数接口不可用，尝试东方财富直连回退",
        ),
        ProviderAttempt(
            label="Akshare 新浪指数",
            loader=_build_akshare_sina_indices,
            on_error="新浪指数接口失败，尝试新浪直连回退",
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
    """获取大盘指数数据，带 5 分钟缓存和数据源回退。

    Args:
        无
    Return:
        MarketIndices 模型对象，附带 total_amount
    """
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
