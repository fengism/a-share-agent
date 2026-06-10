import logging

from app.services.providers import get_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.data_clean import safe_float
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)


def _get_baidu_provider():
    """延迟获取百度 provider。"""
    return get_provider("baidu")


def _get_eastmoney_provider():
    """延迟获取东方财富 provider。"""
    return get_provider("eastmoney")


def _get_tencent_provider():
    """延迟获取腾讯 provider。"""
    return get_provider("tencent")


def _normalize_tencent_sectors(top_df, bottom_df) -> dict:
    """将腾讯板块数据归一化为统一格式。

    Param:
        top_df: 涨幅榜板块 DataFrame
        bottom_df: 跌幅榜板块 DataFrame
    Return:
        包含 sectors 列表和 total 数量的字典
    """
    seen = set()
    sectors = []
    for _, row in top_df.iterrows():
        name = str(row.get("板块名称", ""))
        if name in seen:
            continue
        seen.add(name)
        sectors.append({
            "rank": len(sectors) + 1,
            "name": name,
            "change_pct": safe_float(row.get("涨跌幅")),
            "code": str(row.get("板块代码", "")),
            "up_count": None,
            "down_count": None,
            "leader": str(row.get("领涨跌股票名称", "")),
            "leader_change": safe_float(row.get("领涨股票-涨跌幅")),
        })
    for _, row in bottom_df.iterrows():
        name = str(row.get("板块名称", ""))
        if name in seen:
            continue
        seen.add(name)
        sectors.append({
            "rank": len(sectors) + 1,
            "name": name,
            "change_pct": safe_float(row.get("涨跌幅")),
            "code": str(row.get("板块代码", "")),
            "up_count": None,
            "down_count": None,
            "leader": str(row.get("领涨跌股票名称", "")),
            "leader_change": safe_float(row.get("领涨股票-涨跌幅")),
        })
    sectors.sort(key=lambda x: x["change_pct"] or 0, reverse=True)
    for i, s in enumerate(sectors):
        s["rank"] = i + 1
    return {"sectors": sectors, "total": len(sectors)}


async def get_industry_rankings() -> dict:
    """获取行业涨幅排名，百度优先，回退东方财富，再回退腾讯。

    Param:
        无
    Return:
        包含 sectors 列表和 total 数量的字典
    """
    cache_key = dated_cache_key("industry_rankings")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = None
    for label, fetch_fn in [
        ("百度", lambda: _get_baidu_provider().fetch_industry_rankings(50)),
        ("东方财富", lambda: _get_eastmoney_provider().fetch_industry_rankings(50)),
    ]:
        try:
            result = await call_blocking(fetch_fn)
            data = {
                "sectors": result.get("top", []),
                "total": result.get("total", 0),
            }
            break
        except Exception as e:
            logger.warning(f"{label}行业排名获取失败: {e}")

    if data is None:
        try:
            top_df, bottom_df = await call_blocking(_get_tencent_provider().fetch_industry_rankings)
            data = _normalize_tencent_sectors(top_df, bottom_df)
        except Exception as e:
            logger.warning(f"腾讯行业排名获取失败: {e}")
            data = {"sectors": [], "total": 0}

    cache.set(cache_key, data, ttl=300)
    return data
