"""产业链标的画像与股票数据富化服务。

负责将模型抽取的公司名称自动补全为 A 股标准证券代码，并联动全市场行情快照
富化动态市盈率（PE）、市净率（PB）及总市值等微观估值数据。
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.modules.industry_chain.models import IndustryChainResult

logger = logging.getLogger(__name__)


def format_market_cap(val: float) -> str:
    """格式化市值显示（保留一位小数，转为亿/万）。"""
    if val <= 0:
        return ""
    if val >= 1e8:
        return f"{val / 1e8:.1f}亿"
    if val >= 1e4:
        return f"{val / 1e4:.1f}万"
    return f"{val:.0f}"


def find_stock_code_from_text(text: str, reverse_map: dict[str, str]) -> str:
    """从文本模糊匹配股票代码。"""
    clean_text = text.strip()
    if not clean_text:
        return ""
    if clean_text in reverse_map:
        return reverse_map[clean_text]
    for name, code in reverse_map.items():
        if len(name) >= 3 and (name in clean_text or clean_text in name):
            return code
    return ""


def load_market_snapshots() -> dict[str, dict[str, str]]:
    """从本地全市场行情快照中解析各标的的最新 PE、PB 与市值字符串。"""
    try:
        import pandas as pd

        from app.financial_data.stock.quotes.spot_snapshot import load_spot_snapshot_file

        df = load_spot_snapshot_file()
        if df is None or df.empty:
            return {}

        spot_map: dict[str, dict[str, str]] = {}
        for _, row in df.iterrows():
            code = str(row.get("代码") or "").strip()
            if not code:
                continue
            pe_val = row.get("市盈率-动态")
            pb_val = row.get("市净率")
            cap_val = row.get("总市值")

            pe_str = ""
            if pe_val is not None and not pd.isna(pe_val):
                try:
                    f_pe = float(pe_val)
                    if f_pe > 0 and not math.isinf(f_pe):
                        pe_str = f"{f_pe:.1f}x"
                except (ValueError, TypeError):
                    pass

            pb_str = ""
            if pb_val is not None and not pd.isna(pb_val):
                try:
                    f_pb = float(pb_val)
                    if f_pb > 0 and not math.isinf(f_pb):
                        pb_str = f"{f_pb:.2f}"
                except (ValueError, TypeError):
                    pass

            cap_str = ""
            if cap_val is not None and not pd.isna(cap_val):
                try:
                    f_cap = float(cap_val)
                    if f_cap > 0 and not math.isinf(f_cap):
                        cap_str = format_market_cap(f_cap)
                except (ValueError, TypeError):
                    pass

            spot_map[code] = {"pe": pe_str, "pb": pb_str, "total_market_cap": cap_str}
        return spot_map
    except Exception as exc:
        logger.debug("加载全市场行情快照失败: %s", exc)
        return {}


def enrich_result_stock_codes(
    result: IndustryChainResult,
    name_map: dict[str, str],
) -> IndustryChainResult:
    """基于全市场 5000+ 股票名称代码映射表，自动补齐并修正产业链各环节公司代码与名称。"""
    if not name_map:
        return result
    reverse_map = {name.strip(): code.strip() for code, name in name_map.items() if name}

    def enrich_node(node: Any) -> Any:
        code = (node.code or "").strip()
        name = (node.name or "").strip()
        company = (node.company or "").strip()

        if code and code in name_map:
            if not name or name == code:
                node.name = name_map[code]

        if not code:
            candidates = [name, company, *getattr(node, "companies", [])]
            for cand in candidates:
                found_code = find_stock_code_from_text(cand, reverse_map)
                if found_code:
                    node.code = found_code
                    if not node.name:
                        node.name = name_map.get(found_code, cand)
                    break
        return node

    result.key_stocks = [enrich_node(node) for node in result.key_stocks]
    result.upstream = [enrich_node(node) for node in result.upstream]
    result.midstream = [enrich_node(node) for node in result.midstream]
    result.downstream = [enrich_node(node) for node in result.downstream]
    for group in result.competition:
        group.companies = [enrich_node(node) for node in group.companies]

    return result


def enrich_stock_market_snapshots(
    result: IndustryChainResult,
    spot_map: dict[str, dict[str, str]] | None = None,
    *,
    refresh_existing: bool = False,
) -> IndustryChainResult:
    """结合全市场行情快照，为重点公司及产业链各环节标的富化最新估值（动态PE、PB）与市值数据。"""
    if spot_map is None:
        spot_map = load_market_snapshots()
    if not spot_map:
        return result

    def _enrich_single_node(node: Any) -> None:
        code = (getattr(node, "code", "") or "").strip()
        if code and code in spot_map:
            info = spot_map[code]
            if (refresh_existing or not getattr(node, "pe", "")) and info.get("pe"):
                node.pe = info["pe"]
            if (refresh_existing or not getattr(node, "pb", "")) and info.get("pb"):
                node.pb = info["pb"]
            if (refresh_existing or not getattr(node, "total_market_cap", "")) and info.get("total_market_cap"):
                node.total_market_cap = info["total_market_cap"]

    for node in result.key_stocks:
        _enrich_single_node(node)
    for node in result.upstream:
        _enrich_single_node(node)
    for node in result.midstream:
        _enrich_single_node(node)
    for node in result.downstream:
        _enrich_single_node(node)
    for group in result.competition:
        for node in getattr(group, "companies", []):
            _enrich_single_node(node)

    return result


async def enrich_industry_chain_stock_data(result: IndustryChainResult) -> IndustryChainResult:
    """异步统一富化产业链标的代码与行情快照数据。"""
    try:
        from app.financial_data.stock.profile.name_map import get_stock_name_map

        name_map = await get_stock_name_map()
        if name_map:
            result = enrich_result_stock_codes(result, name_map)
        result = enrich_stock_market_snapshots(result)
    except Exception as exc:
        logger.debug("股票代码与估值富化流程跳过: %s", exc)
    return result
