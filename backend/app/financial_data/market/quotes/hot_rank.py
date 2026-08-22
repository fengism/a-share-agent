"""热门排名服务：热股、热门概念、热门行业，统一入口 + 5 分钟缓存。"""

import logging
from typing import Any

from app.core.cache import cache, dated_cache_key
from app.core.cache_policies import THS_HOT_RANK
from app.core.concurrency.rate_limiter import call_blocking
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

# ── 统一获取函数 ──


async def _get_hot_rank(
    cache_prefix: str, provider_method: str, *args: Any, ttl: int = THS_HOT_RANK.ttl_seconds
) -> list[dict]:
    """通用热门排名获取：缓存 → 调用 provider → 缓存。

    Param:
        cache_prefix: 缓存键前缀，如 "hot_rank"、"ths_hot_concept"
        provider_method: THS provider 上的方法名
        *args: 传递给 provider 方法的额外参数
        ttl: 缓存过期时间（秒），默认 300
    Return:
        热门排名字典列表，失败返回空列表
    """
    cache_key = dated_cache_key(cache_prefix)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result: list[dict] = []
    try:
        method = getattr(get_provider("ths"), provider_method)
        result = await provider_gateway.call(
            "ths",
            provider_method,
            lambda: call_blocking(method, *args),
        )
    except Exception as e:
        logger.warning("同花顺热门数据获取失败 [%s]: %s", cache_prefix, e)

    cache.set(cache_key, result, ttl=ttl)
    return result


async def get_hot_stocks() -> list[dict]:
    """获取同花顺热股榜单，带 5 分钟缓存。

    Param:
        无
    Return:
        热门股票字典列表，失败返回空列表
    """
    return await _get_hot_rank("hot_rank", "fetch_hot_stock_rank")


async def get_ths_hot_concept() -> list[dict]:
    """获取同花顺热门概念板块榜单，带 5 分钟缓存。

    Param:
        无
    Return:
        热门概念板块字典列表，失败返回空列表
    """
    return await _get_hot_rank("ths_hot_concept", "fetch_hot_plate_rank", "concept")


async def get_ths_hot_industry() -> list[dict]:
    """获取同花顺热门行业板块榜单，带 5 分钟缓存。

    Param:
        无
    Return:
        热门行业板块字典列表，失败返回空列表
    """
    return await _get_hot_rank("ths_hot_industry", "fetch_hot_plate_rank", "industry")
