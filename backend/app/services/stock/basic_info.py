import asyncio
import logging
import pandas as pd

from app.models.stock import StockBasicInfo, StockConceptInfo
from app.services.providers import get_provider
from app.services.base.spot_snapshot import get_spot_snapshot, load_spot_snapshot_file
from app.services.stock.name_map import get_stock_name_map
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking
from app.utils.data_clean import safe_float, safe_string
from app.utils.symbol_utils import normalize_code

logger = logging.getLogger(__name__)

_EMPTY_STOCK_CONCEPT = StockConceptInfo(
    concepts=[],
    first_concept=None,
    second_concept=None,
)


def _get_akshare_provider():
    """Lazily resolve the Akshare provider singleton."""
    return get_provider("akshare")


def _get_tencent_provider():
    """Lazily resolve the Tencent provider singleton."""
    return get_provider("tencent")


def _format_listing_date(value) -> str | None:
    """将 YYYYMMDD 或其他格式的上市日期统一格式化为 YYYY-MM-DD。

    Param:
        value: 原始上市日期值
    Return:
        规范化日期字符串，空值返回 None
    """
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text or None


async def _fetch_exchange_basic_row(code: str) -> dict | None:
    """根据股票代码所属交易所抓取上市信息行。

    Param:
        code: 股票代码
    Return:
        包含 listing_date/industry/shares 的字典，找不到时返回 None
    """
    if code.startswith("6"):
        df = await call_blocking(_get_akshare_provider().fetch_stock_names_sh)
        row = df[df["证券代码"] == code]
        if row.empty:
            return None
        r = row.iloc[0]
        return {
            "listing_date": _format_listing_date(r.get("上市日期")),
            "industry": None,
            "total_shares": None,
            "circulating_shares": None,
        }
    if code.startswith(("0", "3")):
        df = await call_blocking(_get_akshare_provider().fetch_stock_names_sz)
        row = df[df["A股代码"] == code]
        if row.empty:
            return None
        r = row.iloc[0]
        return {
            "listing_date": _format_listing_date(r.get("A股上市日期")),
            "industry": safe_string(r.get("所属行业")),
            "total_shares": safe_float(str(r.get("A股总股本", "")).replace(",", "")),
            "circulating_shares": safe_float(str(r.get("A股流通股本", "")).replace(",", "")),
        }
    if code.startswith(("4", "8", "9")):
        df = await call_blocking(_get_akshare_provider().fetch_stock_names_bj)
        row = df[df["证券代码"] == code]
        if row.empty:
            return None
        r = row.iloc[0]
        return {
            "listing_date": _format_listing_date(r.get("上市日期")),
            "industry": safe_string(r.get("所属行业")),
            "total_shares": safe_float(r.get("总股本")),
            "circulating_shares": safe_float(r.get("流通股本")),
        }
    return None


def _extract_basic_info_dict(df: pd.DataFrame) -> dict:
    """将基本信息 DataFrame 转换为 item→value 字典。

    Param:
        df: 包含 item/value 两列的 DataFrame
    Return:
        item 到 value 的映射字典，空时返回空字典
    """
    if df.empty:
        return {}
    return dict(zip(df["item"], df["value"]))


async def _load_basic_info_spot_df() -> pd.DataFrame | None:
    """加载市场快照 DataFrame，按缓存/本地/远程顺序回退。

    Param:
        无
    Return:
        市场快照 DataFrame，全部失败时返回 None
    """
    spot_df = cache.get("stock_spot_all")
    if spot_df is not None:
        return spot_df

    spot_df = load_spot_snapshot_file()
    if spot_df is not None:
        return spot_df

    try:
        return await asyncio.wait_for(get_spot_snapshot(), timeout=2.0)
    except Exception as e:
        logger.info("实时快照获取失败: %s", e)
        return None


def _find_spot_row(spot_df: pd.DataFrame | None, code: str):
    """在快照 DataFrame 中查找指定代码对应的行。

    Param:
        spot_df: 全市场快照 DataFrame
        code: 股票代码
    Return:
        匹配的 Series，未找到时返回 None
    """
    if spot_df is None:
        return None
    matched = spot_df[spot_df["代码"] == code]
    if matched.empty:
        return None
    return matched.iloc[0]


async def _safe_fetch_exchange_basic_row(code: str) -> dict:
    """安全调用交易所基本信息获取，异常时返回空字典。

    Param:
        code: 股票代码
    Return:
        交易所基本信息字典，异常时返回空字典
    """
    try:
        return await _fetch_exchange_basic_row(code) or {}
    except Exception as e:
        logger.info("交易所基础信息获取失败: code=%s, error=%s", code, e)
        return {}


def _pick_basic_name(info_dict: dict, spot_row, name_map: dict[str, str], code: str) -> str:
    """按优先级从多数据源中选出股票简称。

    Param:
        info_dict: 东方财富基本信息字典
        spot_row: 全市场快照对应行
        name_map: 股票代码到名称的映射
        code: 股票代码
    Return:
        股票简称字符串
    """
    return str(
        info_dict.get("股票简称")
        or (spot_row.get("名称") if spot_row is not None else "")
        or name_map.get(code, code)
    )


def _estimate_shares_from_spot(spot_row, market_cap_field: str) -> float | None:
    """根据市值和最新价估算股本。

    Param:
        spot_row: 全市场快照对应行
        market_cap_field: 市值字段名（总市值或流通市值）
    Return:
        估算的股本数量，数据缺失时返回 None
    """
    if spot_row is None:
        return None
    market_cap = safe_float(spot_row.get(market_cap_field))
    price = safe_float(spot_row.get("最新价"))
    if market_cap in (None, 0) or price in (None, 0):
        return None
    return market_cap / price


def _build_basic_info(sym, info_dict: dict, spot_row, exchange_basic_row: dict, name_map: dict[str, str], stock_concept: StockConceptInfo, tencent_basic_data: dict) -> StockBasicInfo:
    """合并多数据源字段构造 StockBasicInfo 模型。

    Param:
        sym: 归一化后的代码对象
        info_dict: 东方财富基本信息字典
        spot_row: 全市场快照对应行
        exchange_basic_row: 交易所补充信息字典
        name_map: 股票代码到名称的映射
        stock_concept: 概念/行业信息对象
        tencent_basic_data: 腾讯实时报价字典
    Return:
        StockBasicInfo 模型对象
    """
    return StockBasicInfo(
        code=sym.raw,
        name=tencent_basic_data.get("name") or _pick_basic_name(info_dict, spot_row, name_map, sym.raw),
        listing_date=_format_listing_date(info_dict.get("上市时间")) or exchange_basic_row.get("listing_date"),
        total_shares=safe_float(info_dict.get("总股本")) or exchange_basic_row.get("total_shares") or _estimate_shares_from_spot(spot_row, "总市值"),
        circulating_shares=safe_float(info_dict.get("流通股")) or exchange_basic_row.get("circulating_shares") or _estimate_shares_from_spot(spot_row, "流通市值"),
        pe_ttm=safe_float(tencent_basic_data.get("pe_ttm") or info_dict.get("市盈率")),
        pb=safe_float(tencent_basic_data.get("pb") or info_dict.get("市净率")),
        market_cap=safe_float(tencent_basic_data.get("mcap") or (spot_row.get("总市值") if spot_row is not None else None)),
        float_market_cap=safe_float(tencent_basic_data.get("float_mcap") or (spot_row.get("流通市值") if spot_row is not None else None)),
        turnover_pct=safe_float(tencent_basic_data.get("amplitude_pct") or None),
        first_industry=stock_concept.first_concept,
        second_industry=stock_concept.second_concept,
        current_price=safe_float(tencent_basic_data.get("price")),
        pe_static=safe_float(tencent_basic_data.get("pe_static")),
        concepts=stock_concept.concepts,
        
    )

async def get_basic_info(code: str) -> StockBasicInfo:
    """获取股票基本信息，融合东财、交易所、腾讯等多数据源。

    Param:
        code: 股票代码
    Return:
        StockBasicInfo 模型对象，包含估值、股本、行业等字段
    """
    sym = normalize_code(code)
    cache_key = dated_cache_key("stock_basic_info", sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    info_dict: dict = {}
    try:
        info_dict = await call_blocking(_get_akshare_provider().fetch_stock_basic_info, code=sym.raw)
    except Exception:
        logger.info(f"东方财富个股信息不可用，尝试备用方案: {sym.raw}")
    spot_df = await _load_basic_info_spot_df()
    spot_row = _find_spot_row(spot_df, sym.raw)
    exchange_result, name_map_result, concept_result, tencent_result = await asyncio.gather(
        _safe_fetch_exchange_basic_row(sym.raw),
        get_stock_name_map(),
        call_blocking(_get_tencent_provider().fetch_stock_concepts, sym.raw),
        call_blocking(_get_tencent_provider().fetch_stock_quote, sym.raw),
        return_exceptions=True,
    )
    exchange_basic_row = exchange_result if isinstance(exchange_result, dict) else {}
    name_map = name_map_result if isinstance(name_map_result, dict) else {}
    stock_concept = (
        concept_result
        if isinstance(concept_result, StockConceptInfo)
        else _EMPTY_STOCK_CONCEPT
    )
    tencent_basic_data = tencent_result if isinstance(tencent_result, dict) else {}
    result = _build_basic_info(sym, info_dict, spot_row, exchange_basic_row, name_map, stock_concept, tencent_basic_data)
    cache.set(cache_key, result, ttl=300)
    return result

if __name__ == "__main__":
    res = asyncio.run(get_basic_info("600032"))
    print("获取到的基本信息:", res)
