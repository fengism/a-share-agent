import logging

import pandas as pd
from app.models.stock import StockSearchItem
from app.services.providers import get_provider
from app.services.stock.name_map import get_stock_name_map
from app.utils.cache import cache
from app.utils.rate_limiter import call_blocking
from app.utils.data_clean import safe_float

logger = logging.getLogger(__name__)

_SEARCH_RESULT_LIMIT = 5


def _get_eastmoney_provider():
    """Lazily resolve the EastMoney provider singleton."""
    return get_provider("eastmoney")


def _merge_search_results(base: list[StockSearchItem], extra: list[StockSearchItem], limit: int = _SEARCH_RESULT_LIMIT) -> list[StockSearchItem]:
    """合并基础结果与远程结果，按代码去重并限制总数。

    Param:
        base: 基础搜索结果列表
        extra: 远程补充结果列表
        limit: 返回数量上限
    Return:
        去重合并后的结果列表
    """
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
    """向结果列表追加一项，返回是否达到上限。

    Param:
        results: 待追加的结果列表
        code: 股票代码
        name: 股票名称
    Return:
        达到结果上限返回 True，否则 False
    """
    if any(item.code == code for item in results):
        return False
    results.append(StockSearchItem(code=code, name=name))
    return len(results) >= _SEARCH_RESULT_LIMIT


def _get_pinyin_prefix(name: str) -> str:
    """提取中文名称的拼音首字母串。

    Param:
        name: 中文名称
    Return:
        每个字的拼音首字母拼接结果，依赖缺失时返回空串
    """
    try:
        import pypinyin
        return "".join([item[0][0] for item in pypinyin.lazy_pinyin(name)])
    except ImportError:
        return ""


def _search_local_by_code(query: str, name_map: dict[str, str]) -> list[StockSearchItem]:
    """按股票代码在本地名称映射中模糊搜索。

    Param:
        query: 全部为数字的查询串
        name_map: 股票代码到名称的字典
    Return:
        StockSearchItem 列表
    """
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
    """按名称或拼音首字母在本地映射中搜索。

    Param:
        query: 名称或拼音首字母查询串
        name_map: 股票代码到名称的字典
    Return:
        StockSearchItem 列表
    """
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
    """用市场快照为搜索结果补充最新价和涨跌幅。

    Param:
        results: 原始搜索结果列表
        spot_df: 全市场快照 DataFrame
    Return:
        附带行情的搜索结果列表，异常时返回原结果
    """
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
    """按代码或名称搜索股票，自动融合本地映射与远程建议。

    Param:
        query: 查询关键词（代码、名称或拼音首字母）
    Return:
        StockSearchItem 列表，附带最新价格信息
    """
    query = query.strip()
    if not query:
        return []

    name_map = await get_stock_name_map()
    results = _search_local_by_code(query, name_map) if query.isdigit() else _search_local_by_name(query, name_map)

    if len(results) < _SEARCH_RESULT_LIMIT:
        try:
            remote_results = await call_blocking(_get_eastmoney_provider().search_stocks, query=query, count=_SEARCH_RESULT_LIMIT)
            results = _merge_search_results(results, remote_results)
        except Exception as e:
            logger.info(f"EastMoney 搜索建议 fallback 失败: {query}, error={e}")

    return _enrich_search_results_with_spot(results, cache.get("stock_spot_all"))
