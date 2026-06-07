import asyncio
import logging

from app.services.providers.eastmoney import eastmoney_provider as _eastmoney_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)


def _extract_latest(data: list[dict], keys: list[str]) -> dict | None:
    """从数据列表中提取最新一条记录，仅保留指定字段。

    Param:
        data: 数据列表，按日期降序排列
        keys: 需要保留的字段名列表
    Return:
        最新一条数据的字典；无数据时返回 None
    """
    if not data:
        return None
    row = data[0]
    return {k: row.get(k) for k in keys if row.get(k) is not None}


def _extract_recent(data: list[dict], keys: list[str], n: int = 3) -> list[dict]:
    """从数据列表中提取最近 n 条记录，仅保留指定字段。

    Param:
        data: 数据列表，按日期降序排列
        keys: 需要保留的字段名列表
        n: 提取的记录数，默认 3
    Return:
        最近 n 条数据的字典列表
    """
    results = []
    for row in data[:n]:
        item = {k: row.get(k) for k in keys if row.get(k) is not None}
        if item:
            results.append(item)
    return results


async def get_macro_data() -> dict:
    """获取宏观经济指标汇总：CPI、PPI、PMI 和货币供应量。

    并发调用东方财富数据中心的 4 个宏观数据接口，
    每个指标取最新一条和最近 3 条趋势数据。

    Param:
        无
    Return:
        包含 cpi/ppi/pmi/money_supply 四个板块的字典
    """
    cache_key = dated_cache_key("macro_data")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    cpi_data, ppi_data, pmi_data, money_data = await asyncio.gather(
        call_blocking(_eastmoney_provider.fetch_china_cpi),
        call_blocking(_eastmoney_provider.fetch_china_ppi),
        call_blocking(_eastmoney_provider.fetch_china_pmi),
        call_blocking(_eastmoney_provider.fetch_china_economy_currency_supply),
        return_exceptions=True,
    )

    result = {}

    # CPI: 全国当月、同比、环比、累计
    if not isinstance(cpi_data, Exception) and cpi_data:
        result["cpi"] = {
            "latest": _extract_latest(cpi_data, ["TIME", "NATIONAL_SAME", "NATIONAL_SEQUENTIAL", "NATIONAL_ACCUMULATE"]),
            "trend": _extract_recent(cpi_data, ["TIME", "NATIONAL_SAME", "NATIONAL_SEQUENTIAL", "NATIONAL_ACCUMULATE"]),
        }
    else:
        result["cpi"] = {"latest": None, "trend": []}
        if isinstance(cpi_data, Exception):
            logger.warning("CPI 数据获取失败: %s", cpi_data)

    # PPI: 当月、同比、累计
    if not isinstance(ppi_data, Exception) and ppi_data:
        result["ppi"] = {
            "latest": _extract_latest(ppi_data, ["TIME", "BASE", "BASE_SAME", "BASE_ACCUMULATE"]),
            "trend": _extract_recent(ppi_data, ["TIME", "BASE", "BASE_SAME", "BASE_ACCUMULATE"]),
        }
    else:
        result["ppi"] = {"latest": None, "trend": []}
        if isinstance(ppi_data, Exception):
            logger.warning("PPI 数据获取失败: %s", ppi_data)

    # PMI: 制造业、非制造业
    if not isinstance(pmi_data, Exception) and pmi_data:
        result["pmi"] = {
            "latest": _extract_latest(pmi_data, ["TIME", "MAKE_INDEX", "MAKE_SAME", "NMAKE_INDEX", "NMAKE_SAME"]),
            "trend": _extract_recent(pmi_data, ["TIME", "MAKE_INDEX", "MAKE_SAME", "NMAKE_INDEX", "NMAKE_SAME"]),
        }
    else:
        result["pmi"] = {"latest": None, "trend": []}
        if isinstance(pmi_data, Exception):
            logger.warning("PMI 数据获取失败: %s", pmi_data)

    # 货币供应量: M0/M1/M2 及同比
    if not isinstance(money_data, Exception) and money_data:
        result["money_supply"] = {
            "latest": _extract_latest(money_data, [
                "TIME", "BASIC_CURRENCY", "BASIC_CURRENCY_SAME",
                "CURRENCY", "CURRENCY_SAME",
                "FREE_CASH", "FREE_CASH_SAME",
            ]),
            "trend": _extract_recent(money_data, [
                "TIME", "BASIC_CURRENCY", "BASIC_CURRENCY_SAME",
                "CURRENCY", "CURRENCY_SAME",
                "FREE_CASH", "FREE_CASH_SAME",
            ]),
        }
    else:
        result["money_supply"] = {"latest": None, "trend": []}
        if isinstance(money_data, Exception):
            logger.warning("货币供应量数据获取失败: %s", money_data)

    cache.set(cache_key, result, ttl=300)
    return result


if __name__ == "__main__":
   result = asyncio.run(get_macro_data())
   print(result)