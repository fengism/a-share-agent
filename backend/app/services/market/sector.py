import logging

from app.services.providers.eastmoney import eastmoney_provider as _eastmoney_provider
from app.services.providers.tencent import tencent_provider as _tencent_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.data_clean import safe_float
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)


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
    """获取行业涨幅排名，东方财富优先并回退到腾讯数据源。

    Param:
        无
    Return:
        包含 sectors 列表和 total 数量的字典
    """
    cache_key = dated_cache_key("industry_rankings")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        result = await call_blocking(_eastmoney_provider.fetch_industry_rankings, 200)
        data = {
            "sectors": result.get("top", []),
            "total": result.get("total", 0),
        }
    except Exception as e:
        logger.warning(f"东方财富行业排名获取失败，回退腾讯: {e}")
        top_df, bottom_df = await call_blocking(_tencent_provider.fetch_market_sector_rankings)
        data = _normalize_tencent_sectors(top_df, bottom_df)

    cache.set(cache_key, data, ttl=300)
    return data
