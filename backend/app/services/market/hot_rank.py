import logging

from app.services.providers.ths import ths_provider as _ths_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)



async def get_hot_stocks() -> list[dict]:
    cache_key = dated_cache_key("hot_rank")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = []
    try:
        result = await call_blocking(_ths_provider.fetch_hot_stock_rank)
    except Exception as e:
        logger.warning(f"同花顺热股榜单获取失败: {e}")

    cache.set(cache_key, result, ttl=300)
    return result


async def get_ths_hot_concept() -> list[dict]:
    cache_key = dated_cache_key("ths_hot_concept")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = []
    try:
        result = await call_blocking(_ths_provider.fetch_hot_plate_rank, "concept")
    except Exception as e:
        logger.warning(f"同花顺热门概念获取失败: {e}")

    cache.set(cache_key, result, ttl=300)
    return result


async def get_ths_hot_industry() -> list[dict]:
    cache_key = dated_cache_key("ths_hot_industry")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = []
    try:
        result = await call_blocking(_ths_provider.fetch_hot_plate_rank, "industry")
    except Exception as e:
        logger.warning(f"同花顺热门行业获取失败: {e}")

    cache.set(cache_key, result, ttl=300)
    return result
