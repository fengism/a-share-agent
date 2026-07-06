import asyncio
import logging

from app.services.providers import get_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)

# Cache the provider at module level to avoid repeated import_module calls
_eastmoney_provider = None


def _get_eastmoney_provider():
    """Lazily resolve the EastMoney provider singleton, cached at module level."""
    global _eastmoney_provider
    if _eastmoney_provider is None:
        _eastmoney_provider = get_provider("eastmoney")
    return _eastmoney_provider


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

    provider = _get_eastmoney_provider()

    cpi_data, ppi_data, pmi_data, money_data = await asyncio.gather(
        call_blocking(provider.fetch_china_cpi),
        call_blocking(provider.fetch_china_ppi),
        call_blocking(provider.fetch_china_pmi),
        call_blocking(provider.fetch_china_economy_currency_supply),
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


def _df_to_list(df, columns: list[str] | None = None) -> list[dict]:
    """将 akshare DataFrame 转为 dict 列表。

    Param:
        df: akshare 返回的 DataFrame
        columns: 需要保留的列名列表，为 None 时保留所有列
    Return:
        dict 列表，每行为一个字典
    """
    if df is None or df.empty:
        return []
    if columns:
        available = [c for c in columns if c in df.columns]
        df = df[available]
    return df.to_dict(orient="records")


async def get_macro_all_data() -> dict:
    """获取全量宏观经济指标数据（6大类）。

    并发调用东方财富和 akshare 的宏观数据接口，
    每个指标取最新一条和最近 12 条趋势数据用于图表展示。

    Param:
        无
    Return:
        包含 prices/sentiment/monetary/rates/growth/trade 六大板块的字典
    """
    cache_key = dated_cache_key("macro_all_data")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    provider = _get_eastmoney_provider()

    # 并发获取所有数据源
    (cpi_data, ppi_data, pmi_data, money_data,
     lpr_data, shibor_data, trade_data, sf_data, gdp_data) = await asyncio.gather(
        call_blocking(provider.fetch_china_cpi),
        call_blocking(provider.fetch_china_ppi),
        call_blocking(provider.fetch_china_pmi),
        call_blocking(provider.fetch_china_economy_currency_supply),
        call_blocking(provider.fetch_china_lpr),
        call_blocking(provider.fetch_china_shibor),
        call_blocking(provider.fetch_china_trade),
        call_blocking(provider.fetch_china_social_financing),
        call_blocking(provider.fetch_china_gdp),
        return_exceptions=True,
    )

    result = {}

    # --- 物价指标 ---
    prices = {}
    if not isinstance(cpi_data, Exception) and cpi_data:
        prices["cpi"] = {
            "latest": _extract_latest(cpi_data, ["TIME", "NATIONAL_SAME", "NATIONAL_SEQUENTIAL", "NATIONAL_ACCUMULATE"]),
            "trend": _extract_recent(cpi_data, ["TIME", "NATIONAL_SAME", "NATIONAL_SEQUENTIAL", "NATIONAL_ACCUMULATE"], n=12),
        }
    else:
        prices["cpi"] = {"latest": None, "trend": []}
        if isinstance(cpi_data, Exception):
            logger.warning("CPI 数据获取失败: %s", cpi_data)

    if not isinstance(ppi_data, Exception) and ppi_data:
        prices["ppi"] = {
            "latest": _extract_latest(ppi_data, ["TIME", "BASE", "BASE_SAME", "BASE_ACCUMULATE"]),
            "trend": _extract_recent(ppi_data, ["TIME", "BASE", "BASE_SAME", "BASE_ACCUMULATE"], n=12),
        }
    else:
        prices["ppi"] = {"latest": None, "trend": []}
        if isinstance(ppi_data, Exception):
            logger.warning("PPI 数据获取失败: %s", ppi_data)
    result["prices"] = prices

    # --- 经济景气 ---
    sentiment = {}
    if not isinstance(pmi_data, Exception) and pmi_data:
        sentiment["pmi"] = {
            "latest": _extract_latest(pmi_data, ["TIME", "MAKE_INDEX", "MAKE_SAME", "NMAKE_INDEX", "NMAKE_SAME"]),
            "trend": _extract_recent(pmi_data, ["TIME", "MAKE_INDEX", "MAKE_SAME", "NMAKE_INDEX", "NMAKE_SAME"], n=12),
        }
    else:
        sentiment["pmi"] = {"latest": None, "trend": []}
        if isinstance(pmi_data, Exception):
            logger.warning("PMI 数据获取失败: %s", pmi_data)
    result["sentiment"] = sentiment

    # --- 货币金融 ---
    monetary = {}
    if not isinstance(money_data, Exception) and money_data:
        monetary["money_supply"] = {
            "latest": _extract_latest(money_data, [
                "TIME", "BASIC_CURRENCY", "BASIC_CURRENCY_SAME",
                "CURRENCY", "CURRENCY_SAME",
                "FREE_CASH", "FREE_CASH_SAME",
            ]),
            "trend": _extract_recent(money_data, [
                "TIME", "BASIC_CURRENCY", "BASIC_CURRENCY_SAME",
                "CURRENCY", "CURRENCY_SAME",
                "FREE_CASH", "FREE_CASH_SAME",
            ], n=12),
        }
    else:
        monetary["money_supply"] = {"latest": None, "trend": []}
        if isinstance(money_data, Exception):
            logger.warning("货币供应量数据获取失败: %s", money_data)

    if not isinstance(sf_data, Exception) and sf_data:
        # 东方财富社融字段: RMB_LOAN(新增贷款), RMB_LOAN_SAME(同比), RMB_LOAN_ACCUMULATE(累计), LOAN_ACCUMULATE_SAME(累计同比)
        monetary["social_financing"] = {
            "latest": _extract_latest(sf_data, ["TIME", "RMB_LOAN", "RMB_LOAN_SAME", "RMB_LOAN_ACCUMULATE", "LOAN_ACCUMULATE_SAME"]),
            "trend": _extract_recent(sf_data, ["TIME", "RMB_LOAN", "RMB_LOAN_SAME", "RMB_LOAN_ACCUMULATE", "LOAN_ACCUMULATE_SAME"], n=12),
        }
    else:
        monetary["social_financing"] = {"latest": None, "trend": []}
        if isinstance(sf_data, Exception):
            logger.warning("社会融资数据获取失败: %s", sf_data)
    result["monetary"] = monetary

    # --- 利率 ---
    rates = {}
    if not isinstance(lpr_data, Exception) and lpr_data:
        lpr_result = {
            "latest": _extract_latest(lpr_data, ["TIME", "LPR1Y", "LPR5Y"]),
            "trend": _extract_recent(lpr_data, ["TIME", "LPR1Y", "LPR5Y"], n=12),
        }
        rates["lpr"] = lpr_result
    else:
        rates["lpr"] = {"latest": None, "trend": []}
        if isinstance(lpr_data, Exception):
            logger.warning("LPR 数据获取失败: %s", lpr_data)

    if not isinstance(shibor_data, Exception) and shibor_data:
        # SHIBOR 数据为纵向结构：每行一个市场+期限+利率
        # 只取上海银行间同业拆放利率（SHIBOR CNY）
        period_map = {
            "隔夜": "ON", "O/N": "ON",
            "1周": "WEEK1", "1W": "WEEK1",
            "1月": "MONTH1", "1M": "MONTH1",
            "3月": "MONTH3", "3M": "MONTH3",
            "4月": "MONTH4", "4M": "MONTH4",
            "6月": "MONTH6", "6M": "MONTH6",
            "9月": "MONTH9", "9M": "MONTH9",
            "1年": "YEAR1", "1Y": "YEAR1",
        }
        shibor_cny = [r for r in shibor_data
                      if r.get("MARKET_CODE") == "001"
                      and r.get("CURRENCY_CODE") == "CNY"]
        # 按日期分组 pivot
        date_rows: dict[str, dict] = {}
        for row in shibor_cny:
            date_str = str(row.get("REPORT_DATE", ""))[:10]
            period = str(row.get("REPORT_PERIOD", ""))
            rate = row.get("IR_RATE")
            col = None
            for keyword, col_name in period_map.items():
                if keyword in period:
                    col = col_name
                    break
            if col and rate is not None:
                if date_str not in date_rows:
                    date_rows[date_str] = {"TIME": date_str}
                date_rows[date_str][col] = rate
        shibor_pivoted = sorted(date_rows.values(), key=lambda x: x["TIME"], reverse=True)
        # 动态收集实际存在的列
        all_cols = set()
        for row in shibor_pivoted:
            all_cols.update(row.keys())
        all_cols.discard("TIME")
        shibor_cols = ["TIME"] + sorted(all_cols)
        rates["shibor"] = {
            "latest": _extract_latest(shibor_pivoted, shibor_cols),
            "trend": _extract_recent(shibor_pivoted, shibor_cols, n=12),
        }
    else:
        rates["shibor"] = {"latest": None, "trend": []}
        if isinstance(shibor_data, Exception):
            logger.warning("SHIBOR 数据获取失败: %s", shibor_data)
    result["rates"] = rates

    # --- 经济增速 ---
    growth = {}
    if not isinstance(gdp_data, Exception) and gdp_data:
        # 东方财富 GDP 字段: DOMESTICL_PRODUCT_BASE(当季值), SUM_SAME(同比)
        gdp_normalized = []
        for row in gdp_data:
            gdp_normalized.append({
                "TIME": row.get("TIME"),
                "GDP_VALUE": row.get("DOMESTICL_PRODUCT_BASE"),
                "GDP_SAME": row.get("SUM_SAME"),
            })
        growth["gdp"] = {
            "latest": _extract_latest(gdp_normalized, ["TIME", "GDP_VALUE", "GDP_SAME"]),
            "trend": _extract_recent(gdp_normalized, ["TIME", "GDP_VALUE", "GDP_SAME"], n=12),
        }
    else:
        growth["gdp"] = {"latest": None, "trend": []}
        if isinstance(gdp_data, Exception):
            logger.warning("GDP 数据获取失败: %s", gdp_data)
    result["growth"] = growth

    # --- 外贸 ---
    trade = {}
    if not isinstance(trade_data, Exception) and trade_data:
        # 东方财富字段: EXIT_BASE_SAME(出口同比), IMPORT_BASE_SAME(进口同比)
        # EXIT_BASE/IMPORT_BASE 单位为千美元，BALANCE 换算为亿美元
        trade_normalized = []
        for row in trade_data:
            exit_val = row.get("EXIT_BASE")
            import_val = row.get("IMPORT_BASE")
            balance = None
            if exit_val is not None and import_val is not None:
                try:
                    balance = round((exit_val - import_val) / 100000, 2)  # 千美元→亿美元
                except (TypeError, ValueError):
                    balance = None
            trade_normalized.append({
                "TIME": row.get("TIME"),
                "EXPORTS_SAME": row.get("EXIT_BASE_SAME"),
                "IMPORTS_SAME": row.get("IMPORT_BASE_SAME"),
                "BALANCE": balance,
            })
        trade["exports_imports"] = {
            "latest": _extract_latest(trade_normalized, ["TIME", "EXPORTS_SAME", "IMPORTS_SAME"]),
            "trend": _extract_recent(trade_normalized, ["TIME", "EXPORTS_SAME", "IMPORTS_SAME"], n=12),
        }
        trade["balance"] = {
            "latest": _extract_latest(trade_normalized, ["TIME", "BALANCE"]),
            "trend": _extract_recent(trade_normalized, ["TIME", "BALANCE"], n=12),
        }
    else:
        trade["exports_imports"] = {"latest": None, "trend": []}
        trade["balance"] = {"latest": None, "trend": []}
        if isinstance(trade_data, Exception):
            logger.warning("外贸数据获取失败: %s", trade_data)
    result["trade"] = trade

    cache.set(cache_key, result, ttl=300)
    return result


if __name__ == "__main__":
   result = asyncio.run(get_macro_data())
   print(result)
