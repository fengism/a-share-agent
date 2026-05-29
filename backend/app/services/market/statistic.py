import asyncio
import logging
import time

import pandas as pd

from app.models.market import MarketStatistics
from app.services.providers.eastmoney import eastmoney_provider as _eastmoney_provider
from app.services.providers.tencent import tencent_provider as _tencent_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.data_clean import safe_float
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)


def get_sector_rankings() -> dict:
    top_df, bottom_df = _tencent_provider.fetch_market_sector_rankings_direct()
    def to_items(frame: pd.DataFrame) -> list[dict]:
        result = []
        for _, row in frame.iterrows():
            result.append(
                {
                    "name": str(row.get("板块名称", "")),
                    "change_pct": safe_float(row.get("涨跌幅")),
                    "change_pct_5d": safe_float(row.get("5日涨跌幅")),
                    "change_pct_20d": safe_float(row.get("20日涨跌幅")),
                    "leading_stock": str(row.get("领涨跌股票名称", "")),
                    "leading_change_pct": safe_float(row.get("领涨股票-涨跌幅"))
                }
            )
        return result

    return {
        "top_sectors": to_items(top_df),
        "bottom_sectors": to_items(bottom_df),
    }


async def get_market_statistics(date: str | None = None) -> MarketStatistics:
    if date is None:
        date = time.strftime("%Y-%m-%d", time.localtime())

    cache_key = dated_cache_key("market_statistics", date)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    top_sectors: list[dict] = []
    bottom_sectors: list[dict] = []
    limit_up_stocks: list[dict] = []
    limit_down_stocks: list[dict] = []
    stock_pct_distribution: list[dict] = []
    limit_up_count = 0
    limit_down_count = 0
    up_count = 0
    down_count = 0
    flat_count = 0
    total_stocks = 0
    source = "fallback"

    try:
        sector_rankings = get_sector_rankings()
        top_sectors = sector_rankings.get("top_sectors", [])
        bottom_sectors = sector_rankings.get("bottom_sectors", [])
        source = "sector-rankings"
    except Exception as e:
        logger.warning(f"获取板块涨跌榜失败: {e}")

    try:
        stock_pct_data = await call_blocking(_eastmoney_provider.fetch_market_pct_distribution, date)
        source = source if source != "fallback" else "stock-pct-distribution"
        fenbu = stock_pct_data.get("fenbu", []) if isinstance(stock_pct_data, dict) else []
        stock_pct_distribution = []
        for item in fenbu:
            for label, count in item.items():
                stock_pct_distribution.append({"label": label, "count": int(count or 0)})
        up_count = sum(item["count"] for item in stock_pct_distribution if float(item["label"]) > 0)
        down_count = sum(item["count"] for item in stock_pct_distribution if float(item["label"]) < 0)
        flat_count = sum(item["count"] for item in stock_pct_distribution if float(item["label"]) == 0)
        total_stocks = up_count + down_count + flat_count
    except Exception as e:
        logger.warning(f"获取股票涨跌分布失败: {e}")

    try:
        limit_up_data, limit_up_count_value = await call_blocking(_eastmoney_provider.fetch_market_limit_up_pool, date)
        limit_up_stocks = limit_up_data[:10]
        limit_up_count = int(limit_up_count_value or 0)
        source = source if source != "fallback" else "limit-up-pool"
    except Exception as e:
        logger.warning(f"获取涨停池失败: {e}")

    try:
        limit_down_data, limit_down_count_value = await call_blocking(_eastmoney_provider.fetch_market_limit_down_pool, date)
        limit_down_stocks = limit_down_data[:10]
        limit_down_count = int(limit_down_count_value or 0)
        source = source if source != "fallback" else "limit-down-pool"
    except Exception as e:
        logger.warning(f"获取跌停池失败: {e}")

    result = MarketStatistics(
        date=date,
        source=source,
        top_sectors=top_sectors,
        bottom_sectors=bottom_sectors,
        up_count=up_count,
        down_count=down_count,
        flat_count=flat_count,
        limit_up_count=limit_up_count,
        limit_down_count=limit_down_count,
        total_stocks=total_stocks,
        limit_up_stocks=limit_up_stocks,
        limit_down_stocks=limit_down_stocks,
        stock_pct_distribution=stock_pct_distribution,
    )
    cache.set(cache_key, result, ttl=300)
    return result


if __name__ == "__main__":
    market_statistics = asyncio.run(get_market_statistics(date="20260512"))
    print(market_statistics)
