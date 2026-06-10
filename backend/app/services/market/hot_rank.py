import logging

from app.services.providers import get_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)



async def get_hot_stocks() -> list[dict]:
    """获取同花顺热股榜单，带 5 分钟缓存。

    Param:
        无
    Return:
        热门股票字典列表，失败返回空列表
    """
    cache_key = dated_cache_key("hot_rank")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = []
    try:
        result = await call_blocking(get_provider("ths").fetch_hot_stock_rank)
    except Exception as e:
        logger.warning(f"同花顺热股榜单获取失败: {e}")

    cache.set(cache_key, result, ttl=300)
    return result


async def get_ths_hot_concept() -> list[dict]:
    """获取同花顺热门概念板块榜单，带 5 分钟缓存。

    Param:
        无
    Return:
        热门概念板块字典列表，失败返回空列表
    """
    cache_key = dated_cache_key("ths_hot_concept")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = []
    try:
        result = await call_blocking(get_provider("ths").fetch_hot_plate_rank, "concept")
    except Exception as e:
        logger.warning(f"同花顺热门概念获取失败: {e}")

    cache.set(cache_key, result, ttl=300)
    return result


async def get_ths_hot_industry() -> list[dict]:
    """获取同花顺热门行业板块榜单，带 5 分钟缓存。

    Param:
        无
    Return:
        热门行业板块字典列表，失败返回空列表
    """
    cache_key = dated_cache_key("ths_hot_industry")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = []
    try:
        result = await call_blocking(get_provider("ths").fetch_hot_plate_rank, "industry")
    except Exception as e:
        logger.warning(f"同花顺热门行业获取失败: {e}")

    cache.set(cache_key, result, ttl=300)
    return result
