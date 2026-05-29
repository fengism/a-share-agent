import logging

import pandas as pd
from app.models.stock import StockSearchItem
from app.services.providers.eastmoney import eastmoney_provider
from app.services.stock.name_map import get_stock_name_map
from app.utils.cache import cache
from app.utils.rate_limiter import call_blocking
from app.utils.data_clean import safe_float

logger = logging.getLogger(__name__)

_SEARCH_RESULT_LIMIT = 5


def _merge_search_results(base: list[StockSearchItem], extra: list[StockSearchItem], limit: int = _SEARCH_RESULT_LIMIT) -> list[StockSearchItem]:
    merged = list(base)
    seen_codes = {item.code for item in base}
    for item in extra:
        if item.code in seen_codes:
            continue
        merged.append(item)
        seen_codes.add(item.code)
        if len(merged) >= limit:
            break
    return merged


def _append_search_result(results: list[StockSearchItem], code: str, name: str) -> bool:
    if any(item.code == code for item in results):
        return False
    results.append(StockSearchItem(code=code, name=name))
    return len(results) >= _SEARCH_RESULT_LIMIT


def _get_pinyin_prefix(name: str) -> str:
    try:
        import pypinyin
        return "".join([item[0][0] for item in pypinyin.lazy_pinyin(name)])
    except ImportError:
        return ""


def _search_local_by_code(query: str, name_map: dict[str, str]) -> list[StockSearchItem]:
    results: list[StockSearchItem] = []
    if query in name_map and _append_search_result(results, query, name_map[query]):
        return results
    for code, name in name_map.items():
        if code.startswith(query) and code != query and _append_search_result(results, code, name):
            return results
    for code, name in name_map.items():
        if query in name and _append_search_result(results, code, name):
            return results
    return results


def _search_local_by_name(query: str, name_map: dict[str, str]) -> list[StockSearchItem]:
    results: list[StockSearchItem] = []
    for code, name in name_map.items():
        if query in name and _append_search_result(results, code, name):
            return results

    query_lower = query.lower()
    for code, name in name_map.items():
        pinyin_prefix = _get_pinyin_prefix(name)
        if pinyin_prefix.startswith(query_lower) and _append_search_result(results, code, name):
            return results
    return results


def _enrich_search_results_with_spot(results: list[StockSearchItem], spot_df: pd.DataFrame | None) -> list[StockSearchItem]:
    if spot_df is None or not results:
        return results
    enriched = list(results)
    try:
        for i, item in enumerate(enriched):
            row = spot_df[spot_df["代码"] == item.code]
            if row.empty:
                continue
            enriched[i] = StockSearchItem(
                code=item.code,
                name=item.name,
                price=safe_float(row.iloc[0].get("最新价")),
                change_pct=safe_float(row.iloc[0].get("涨跌幅")),
            )
    except Exception:
        return results
    return enriched


async def search_stocks(query: str) -> list[StockSearchItem]:
    query = query.strip()
    if not query:
        return []

    name_map = await get_stock_name_map()
    results = _search_local_by_code(query, name_map) if query.isdigit() else _search_local_by_name(query, name_map)

    if len(results) < _SEARCH_RESULT_LIMIT:
        try:
            remote_results = await call_blocking(eastmoney_provider.search_stocks, query=query, count=_SEARCH_RESULT_LIMIT)
            results = _merge_search_results(results, remote_results)
        except Exception as e:
            logger.info(f"EastMoney 搜索建议 fallback 失败: {query}, error={e}")

    return _enrich_search_results_with_spot(results, cache.get("stock_spot_all"))
