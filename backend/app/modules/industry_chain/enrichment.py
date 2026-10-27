"""产业链标的画像与股票数据富化服务。

负责将模型抽取的公司名称自动补全为 A 股标准证券代码，并联动全市场行情快照
富化动态市盈率（PE）、市净率（PB）及总市值等微观估值数据。
"""

from __future__ import annotations

import logging
import math
import re
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.modules.industry_chain.models import IndustryChainResult

logger = logging.getLogger(__name__)

_COMPANY_SUFFIX_PATTERN = re.compile(
    r"(?:股份有限公司|有限责任公司|有限公司|（集团）有限公司|集团有限公司|集团股份公司|股份公司|集团|控股|科技)+$"
)
_SNAPSHOT_CACHE: dict[str, dict[str, str]] = {}
_SNAPSHOT_CACHE_TIME: float = 0.0
_SNAPSHOT_TTL_SECONDS: float = 60.0


def format_market_cap(val: float) -> str:
    """格式化市值显示（保留一位小数，转为亿/万）。"""
    if val <= 0:
        return ""
    if val >= 1e8:
        return f"{val / 1e8:.1f}亿"
    if val >= 1e4:
        return f"{val / 1e4:.1f}万"
    return f"{val:.0f}"


def _normalize_company_name(text: str) -> str:
    cleaned = re.sub(r"[\(\)（）\s]", "", text)
    return _COMPANY_SUFFIX_PATTERN.sub("", cleaned).strip()


def find_stock_code_from_text(text: str, reverse_map: dict[str, str]) -> str:
    """从文本模糊匹配股票代码，优先精确全词与剥离后缀匹配，避免短文本反向包含误匹配。"""
    clean_text = text.strip()
    if not clean_text:
        return ""
    if clean_text in reverse_map:
        return reverse_map[clean_text]

    normalized = _normalize_company_name(clean_text)
    if normalized and normalized in reverse_map:
        return reverse_map[normalized]

    # 正向包含：要求名称表中的有效股票名（>=3字）出现在待查文本中，严禁 clean_text in name 误匹配短词
    for name, code in reverse_map.items():
        if len(name) >= 3 and name in clean_text:
            return code
    return ""


def load_market_snapshots() -> dict[str, dict[str, str]]:
    """从本地全市场行情快照中解析各标的的最新 PE、PB 与市值字符串（向量化提取 + 内存短缓存）。"""
    global _SNAPSHOT_CACHE, _SNAPSHOT_CACHE_TIME
    now = time.time()
    if _SNAPSHOT_CACHE and (now - _SNAPSHOT_CACHE_TIME < _SNAPSHOT_TTL_SECONDS):
        return _SNAPSHOT_CACHE

    try:
        import pandas as pd

        from app.financial_data.stock.quotes.spot_snapshot import load_spot_snapshot_file

        df = load_spot_snapshot_file()
        if df is None or df.empty:
            from app.configuration.paths import DATA_DIR
            snap_file = DATA_DIR / "stock_spot_snapshot.json"
            if snap_file.exists():
                try:
                    import json
                    with open(snap_file, "r", encoding="utf-8") as f:
                        snap_data = json.load(f)
                    df = pd.DataFrame(snap_data.get("rows", []))
                except Exception as exc:
                    logger.debug("读取备用行情快照缓存失败: %s", exc)
        if df is None or df.empty:
            return {}

        target_cols = [c for c in ["代码", "市盈率-动态", "市净率", "总市值", "最新价", "涨跌幅"] if c in df.columns]
        if "代码" not in target_cols:
            return {}

        records = df[target_cols].to_dict(orient="records")
        spot_map: dict[str, dict[str, str]] = {}
        for row in records:
            code = str(row.get("代码") or "").strip()
            if not code:
                continue
            pe_val = row.get("市盈率-动态")
            pb_val = row.get("市净率")
            cap_val = row.get("总市值")
            price_val = row.get("最新价")
            chg_val = row.get("涨跌幅")

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

            price_str = ""
            if price_val is not None and not pd.isna(price_val):
                try:
                    f_pr = float(price_val)
                    if f_pr > 0 and not math.isinf(f_pr):
                        price_str = f"{f_pr:.2f}"
                        if chg_val is not None and not pd.isna(chg_val):
                            f_chg = float(chg_val)
                            price_str += f" ({f_chg:+.2f}%)"
                except (ValueError, TypeError):
                    pass

            spot_map[code] = {
                "pe": pe_str,
                "pb": pb_str,
                "total_market_cap": cap_str,
                "price_change": price_str,
            }

        _SNAPSHOT_CACHE = spot_map
        _SNAPSHOT_CACHE_TIME = now
        return spot_map
    except Exception as exc:
        logger.debug("加载全市场行情快照失败: %s", exc)
        return _SNAPSHOT_CACHE or {}


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
            if (refresh_existing or not getattr(node, "price_change", "")) and info.get("price_change"):
                node.price_change = info["price_change"]

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


async def enrich_stocks_financial_breakdown(
    result: IndustryChainResult,
    max_targets: int = 6,
) -> IndustryChainResult:
    """结合真实财报分产品、分业务与分地区营收构成，为重点公司补充最新主营产品、毛利率、收入占比及出海占比（异步非阻塞）。"""
    import asyncio

    from app.financial_data.stock.fundamentals.financials import get_revenue_breakdown

    async def _enrich_one(node: Any) -> None:
        code = (getattr(node, "code", "") or "").strip()
        if not code or len(code) not in (5, 6):
            return
        if getattr(node, "gross_margin", "") and getattr(node, "revenue_share", "") and getattr(node, "overseas_share", ""):
            return
        try:
            breakdown = await get_revenue_breakdown(code)
            products = breakdown.by_product or breakdown.by_business
            if products:
                valid_items = [p for p in products if (p.revenue_share_pct or 0.0) > 0]
                if valid_items:
                    best = max(valid_items, key=lambda p: (p.revenue_share_pct or 0.0))
                    if not getattr(node, "gross_margin", "") and best.gross_margin_pct is not None:
                        node.gross_margin = f"{best.gross_margin_pct:.1f}%"
                    if not getattr(node, "revenue_share", "") and best.revenue_share_pct is not None:
                        node.revenue_share = f"{best.revenue_share_pct:.1f}% ({best.class_name})"

            # 提取出海/海外业务营收占比与毛利率
            if not getattr(node, "overseas_share", "") and breakdown.by_region:
                overseas_kws = ("境外", "国外", "海外", "出口", "外销", "港澳台")
                overseas_items = [
                    r for r in breakdown.by_region
                    if any(kw in (r.class_name or "") for kw in overseas_kws) and (r.revenue_share_pct or 0.0) > 0
                ]
                if overseas_items:
                    total_overseas_pct = sum(r.revenue_share_pct or 0.0 for r in overseas_items)
                    top_region = max(overseas_items, key=lambda r: (r.revenue_share_pct or 0.0))
                    if top_region.gross_margin_pct is not None and top_region.gross_margin_pct > 0:
                        node.overseas_share = f"{total_overseas_pct:.1f}% ({top_region.class_name} · 毛利{top_region.gross_margin_pct:.1f}%)"
                    else:
                        node.overseas_share = f"{total_overseas_pct:.1f}% ({top_region.class_name})"
                else:
                    domestic_items = [r for r in breakdown.by_region if any(kw in (r.class_name or "") for kw in ("境内", "国内", "内销"))]
                    if domestic_items and any((r.revenue_share_pct or 0.0) >= 95.0 for r in domestic_items):
                        node.overseas_share = "<1% (内销为主)"
        except Exception as exc:
            logger.debug("获取个股 %s 财报营收拆解失败: %s", code, exc)

    targets = [node for node in getattr(result, "key_stocks", []) if getattr(node, "code", "")][:max_targets]
    if targets:
        await asyncio.gather(*[_enrich_one(node) for node in targets], return_exceptions=True)
    return result


async def enrich_stocks_valuation_percentile(
    result: IndustryChainResult,
) -> IndustryChainResult:
    """批量异步富化重点标的近三年市盈率百分位（PE Percentile）。"""
    from app.financial_data.stock.valuation.percentiles import compute_percentiles

    key_nodes = [node for node in getattr(result, "key_stocks", []) if getattr(node, "code", "")]
    if not key_nodes:
        return result
    codes = [node.code for node in key_nodes if node.code and len(node.code) == 6]
    if not codes:
        return result

    try:
        percentile_records = await compute_percentiles(codes, indicator="市盈率(TTM)", period="近三年")
        pct_map = {r["code"]: r.get("percentile") for r in percentile_records if r.get("percentile") is not None}
        for node in key_nodes:
            code = getattr(node, "code", "")
            if code in pct_map and not getattr(node, "pe_percentile", ""):
                pct = pct_map[code]
                if pct <= 20:
                    status_text = "近三年低估"
                elif pct >= 80:
                    status_text = "近三年高估"
                else:
                    status_text = "近三年中位"
                node.pe_percentile = f"{pct:.1f}% ({status_text})"
    except Exception as exc:
        logger.debug("估值分位数富化跳过: %s", exc)
    return result


async def enrich_stocks_consensus_forecast(
    result: IndustryChainResult,
    max_targets: int = 6,
) -> IndustryChainResult:
    """异步富化重点公司的卖方机构一致预期（Consensus Earnings / Forecast）。"""
    import asyncio

    from app.financial_data.stock.valuation.detail import _fetch_institution_forecasts

    async def _enrich_one(node: Any) -> None:
        code = (getattr(node, "code", "") or "").strip()
        if not code or len(code) != 6 or getattr(node, "consensus_forecast", ""):
            return
        try:
            forecasts = await _fetch_institution_forecasts(code)
            if not forecasts:
                return
            eps_forecasts = [f for f in forecasts if f.metric == "EPS" and f.mean_value is not None]
            pe_forecasts = [f for f in forecasts if f.metric == "PE" and f.mean_value is not None]
            if not eps_forecasts:
                return
            latest_eps = sorted(eps_forecasts, key=lambda f: str(f.year))[0]
            matching_pe = next((f for f in pe_forecasts if f.year == latest_eps.year), None)
            count_str = f"{int(latest_eps.institution_count)}家机构预测" if latest_eps.institution_count else "机构预测"
            pe_str = f" / PE {matching_pe.mean_value:.1f}倍" if matching_pe and matching_pe.mean_value else ""
            node.consensus_forecast = f"{count_str} {latest_eps.year}E EPS {latest_eps.mean_value:.2f}元{pe_str}"
        except Exception as exc:
            logger.debug("获取个股 %s 机构一致预期失败: %s", code, exc)

    targets = [node for node in getattr(result, "key_stocks", []) if getattr(node, "code", "")][:max_targets]
    if targets:
        await asyncio.gather(*[_enrich_one(node) for node in targets], return_exceptions=True)
    return result


async def enrich_stocks_financial_metrics(
    result: IndustryChainResult,
    max_targets: int = 6,
) -> IndustryChainResult:
    """结合真实财报三表指标，异步为重点标的富化 ROE（净资产收益率）与营收/净利润同比增长率。"""
    import asyncio

    from app.financial_data.stock.fundamentals.financials import get_financial_metrics

    async def _enrich_one(node: Any) -> None:
        code = (getattr(node, "code", "") or "").strip()
        if not code or len(code) not in (5, 6):
            return
        if getattr(node, "roe", "") and getattr(node, "growth_rate", ""):
            return
        try:
            metrics_obj = await asyncio.wait_for(get_financial_metrics(code), timeout=5.0)
            metrics = metrics_obj.metrics or {}
            roe_val = metrics.get("净资产收益率")
            if roe_val is not None and not getattr(node, "roe", ""):
                node.roe = f"{roe_val * 100:.1f}%"
            rev_yoy = metrics.get("营收同比")
            profit_yoy = metrics.get("净利润同比")
            if (rev_yoy is not None or profit_yoy is not None) and not getattr(node, "growth_rate", ""):
                parts = []
                if rev_yoy is not None:
                    parts.append(f"营收{rev_yoy:+.1f}%")
                if profit_yoy is not None:
                    parts.append(f"净利{profit_yoy:+.1f}%")
                node.growth_rate = " / ".join(parts)
        except Exception as exc:
            logger.debug("获取个股 %s 核心财务指标失败: %s", code, exc)

    targets = [node for node in getattr(result, "key_stocks", []) if getattr(node, "code", "")][:max_targets]
    if targets:
        await asyncio.gather(*[_enrich_one(node) for node in targets], return_exceptions=True)
    return result


async def enrich_stocks_restricted_risk(
    result: IndustryChainResult,
    max_targets: int = 6,
) -> IndustryChainResult:
    """异步排查重点标的未来限售股解禁抛压风险。"""
    import asyncio

    from app.financial_data.stock.insights.restricted import get_restricted_shares_lift

    async def _enrich_one(node: Any) -> None:
        code = (getattr(node, "code", "") or "").strip()
        if not code or len(code) != 6 or getattr(node, "restricted_risk", ""):
            return
        try:
            lift_data = await asyncio.wait_for(get_restricted_shares_lift(code), timeout=4.0)
            if not lift_data:
                return
            has_upcoming = lift_data.get("has_upcoming_lifts", False)
            ratio = lift_data.get("total_upcoming_ratio_float_pct", 0.0) or 0.0
            assessment = lift_data.get("pressure_risk_assessment", "")
            if has_upcoming and ratio >= 0.5:
                node.restricted_risk = f"近6个月预计解禁占流通盘 {ratio:.1f}%"
            elif assessment and "无" not in assessment:
                node.restricted_risk = assessment
        except Exception as exc:
            logger.debug("获取个股 %s 限售解禁风险失败: %s", code, exc)

    targets = [node for node in getattr(result, "key_stocks", []) if getattr(node, "code", "")][:max_targets]
    if targets:
        await asyncio.gather(*[_enrich_one(node) for node in targets], return_exceptions=True)
    return result


async def enrich_macro_commodity_and_customs(
    result: IndustryChainResult,
) -> IndustryChainResult:
    """联动大宗商品期货最新行情与海关月度出海/进出口数据，为产业链补充高频宏观与中观指标。"""
    try:
        from app.financial_data.market.quotes.commodity import get_commodity_spot_prices
        from app.financial_data.market.quotes.customs import get_customs_trade_data
        from app.modules.industry_chain.models import IndustryChainMetric

        existing_labels = {m.label for m in getattr(result, "market_metrics", [])}
        topic = result.name or ""

        # 1. 尝试匹配关联大宗商品期货最新行情
        commodity_res = await get_commodity_spot_prices(topic)
        items = commodity_res.get("items", [])
        for item in items[:2]:
            if item.get("status") == "available" and item.get("latest_price") is not None:
                lbl = f"{item.get('name')}主力价"
                if lbl not in existing_labels:
                    existing_labels.add(lbl)
                    chg_pct = item.get("change_pct")
                    growth_str = f"{chg_pct:+.2f}%" if chg_pct is not None else ""
                    result.market_metrics.append(
                        IndustryChainMetric(
                            label=lbl,
                            value=f"{item.get('latest_price')} {item.get('unit', '')}".strip(),
                            period=item.get("date") or "最新连续",
                            growth=growth_str,
                            source=item.get("source") or "新浪期货",
                            source_url=item.get("source_url") or "",
                            claim_type="fact",
                            confidence="high",
                        )
                    )

        # 2. 尝试匹配重点商品海关出口格局
        customs_res = await get_customs_trade_data(topic)
        matched_profs = customs_res.get("matched_commodity_profiles", [])
        latest_macro = customs_res.get("latest_month_summary") or {}
        if matched_profs:
            for prof in matched_profs[:2]:
                lbl = f"{prof.get('commodity')}出海跟踪"
                if lbl not in existing_labels:
                    existing_labels.add(lbl)
                    result.market_metrics.append(
                        IndustryChainMetric(
                            label=lbl,
                            value=f"重点市场: {prof.get('key_target_markets', '全球')}",
                            period=latest_macro.get("month") or "月度跟踪",
                            growth=f"全国{prof.get('trade_type', '出口')}跟踪",
                            source="海关总署 / 东方财富",
                            claim_type="fact",
                            confidence="high",
                        )
                    )
    except Exception as exc:
        logger.debug("宏观大宗商品与海关数据联动跳过: %s", exc)
    return result


async def enrich_industry_chain_stock_data(result: IndustryChainResult) -> IndustryChainResult:
    """异步统一富化产业链标的代码与行情快照数据。"""
    try:
        from app.financial_data.stock.profile.name_map import get_stock_name_map

        name_map = await get_stock_name_map()
        if name_map:
            result = enrich_result_stock_codes(result, name_map)
        result = enrich_stock_market_snapshots(result)
        result = await enrich_stocks_financial_breakdown(result)
        result = await enrich_stocks_valuation_percentile(result)
        result = await enrich_stocks_consensus_forecast(result)
        result = await enrich_stocks_financial_metrics(result)
        result = await enrich_stocks_restricted_risk(result)
        result = await enrich_macro_commodity_and_customs(result)
    except Exception as exc:
        logger.debug("股票代码与估值富化流程跳过: %s", exc)
    return result
