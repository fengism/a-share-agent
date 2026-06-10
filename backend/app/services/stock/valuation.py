import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from app.models.stock import DCFValuationResult, InstitutionForecast, StockBasicInfo, ValuationDetail, ValuationFundamentals, ValuationMethodResult, ValuationMultiples, ValuationPeer, ValuationPeerSummary, ValuationPercentiles, ValuationProfile
from app.services.providers import get_provider
from app.services.stock.basic_info import get_basic_info
from app.services.stock.financials import get_financial_metrics
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking
from app.utils.data_clean import safe_float
from app.utils.symbol_utils import normalize_code

logger = logging.getLogger(__name__)


FINANCIAL_KEYWORDS = ("银行", "保险", "证券", "券商", "多元金融", "金融")
CYCLICAL_KEYWORDS = ("煤炭", "有色", "钢铁", "化工", "航运", "石油", "建材", "矿", "金属")
GROWTH_KEYWORDS = ("半导体", "软件", "电子", "计算机", "医药", "新能源", "机器人", "通信", "芯片")
STABLE_KEYWORDS = ("白酒", "食品", "饮料", "公用事业", "电力", "高速", "运营商", "水务", "燃气")


def _get_akshare_provider():
    """Lazily resolve the Akshare provider singleton."""
    return get_provider("akshare")


def _get_ths_provider():
    """Lazily resolve the THS provider singleton."""
    return get_provider("ths")


@dataclass(frozen=True)
class _MultipleMethodContext:
    """Purpose: 倍数法估值方法的目标倍数、依据、置信度与适用性上下文。"""
    target: float | None
    basis: str | None
    confidence: float
    applicability: str


@dataclass(frozen=True)
class _ValuationBases:
    """Purpose: 估值计算共享的盈利、收入、现金流年化与 TTM 基础数据。"""
    net_profit_annualized: float | None
    revenue_annualized: float | None
    operating_cashflow_annualized: float | None
    net_profit_ttm: float | None
    revenue_ttm: float | None


@dataclass(frozen=True)
class _PegContext:
    """Purpose: PEG 估值方法使用的增长率、依据与当前 PEG 上下文。"""
    growth_rate: float | None
    growth_basis: str | None
    confidence: float
    current_peg: float | None


@dataclass(frozen=True)
class _WeightedValuationOutputs:
    """Purpose: 加权估值产物（权重、综合公允价值、区间、观点、摘要）。"""
    method_weights: dict[str, float]
    blended_fair_value: float | None
    fair_value_range: list[float] | None
    valuation_view: str | None
    valuation_summary: str | None



async def get_valuation(code: str) -> dict:
    """获取股票当前估值与同行对比，并在缺失时回退到基础信息。

    Param:
        code: 股票代码
    Return:
        包含 code/pe_ttm/pb/ps_ttm/peers 字段的字典
    """
    sym = normalize_code(code)
    cache_key = dated_cache_key("valuation", sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result: dict = {"code": sym.raw, "pe_ttm": None, "pb": None, "ps_ttm": None, "peers": []}

    try:
        df = await call_blocking(_get_akshare_provider().fetch_stock_valuation_comparison, symbol=sym.prefixed_upper)
        if len(df) > 0:
            row = df.iloc[0]
            result["pe_ttm"] = safe_float(row.get("市盈率-TTM"))
            result["pb"] = safe_float(row.get("市净率-MRQ"))
            result["ps_ttm"] = safe_float(row.get("市销率-TTM"))
        peers = []
        for _, row in df.head(10).iterrows():
            peer_name = str(row.get("简称", "")).strip()
            peer_code = str(row.get("代码", "")).strip()
            if not peer_code or peer_code in {"行业中值", "行业平均"} or peer_name in {"行业中值", "行业平均"}:
                continue
            peers.append(
                {
                    "name": peer_name,
                    "code": peer_code,
                    "pe_ttm": safe_float(row.get("市盈率-TTM")),
                    "pb": safe_float(row.get("市净率-MRQ")),
                    "ps_ttm": safe_float(row.get("市销率-TTM")),
                }
            )
        result["peers"] = peers
    except Exception:
        logger.info(f"估值数据获取失败，回退到基础信息: {sym.raw}")

    if result["pe_ttm"] is None or result["pb"] is None:
        try:
            basic_info = await get_basic_info(code)
            if result["pe_ttm"] is None:
                result["pe_ttm"] = basic_info.pe_ttm
            if result["pb"] is None:
                result["pb"] = basic_info.pb
        except Exception:
            logger.info(f"基础信息估值回退失败: {sym.raw}")

    cache.set(cache_key, result, ttl=86400)
    return result


def _median_positive(values: list[float | None]) -> float | None:
    """计算列表中正值的中位数。

    Param:
        values: 数值列表，允许 None
    Return:
        正值中位数，无正值时返回 None
    """
    series = sorted(value for value in values if value is not None and value > 0)
    if not series:
        return None
    mid = len(series) // 2
    if len(series) % 2 == 1:
        return round(series[mid], 4)
    return round((series[mid - 1] + series[mid]) / 2, 4)


def _normalize_growth_rate(value: float | None) -> float:
    """将增长率归一化到小数形式并限制在 0-15% 区间。

    Param:
        value: 增长率，可能为百分数或小数
    Return:
        归一化后的小数增长率
    """
    if value is None:
        return 0.03
    rate = value / 100 if abs(value) > 1 else value
    return max(0.0, min(rate, 0.15))


def _normalize_peg_growth_rate(value: float | None) -> float | None:
    """归一化 PEG 用增长率，过低或异常时返回 None。

    Param:
        value: 增长率，可能为百分数或小数
    Return:
        归一化后的小数增长率，不满足条件时返回 None
    """
    if value is None:
        return None
    rate = value / 100 if abs(value) > 1 else value
    if rate <= 0.03:
        return None
    return min(rate, 0.50)


def _parse_forecast_year(value: object) -> int | None:
    """从字符串中解析出 4 位年份数字。

    Param:
        value: 任意值，会先转换为字符串
    Return:
        年份整数，未匹配到时返回 None
    """
    match = re.search(r"\d{4}", str(value or ""))
    if match is None:
        return None
    return int(match.group(0))


def _select_forecast(forecasts: list[InstitutionForecast], metric: str, min_year: int) -> InstitutionForecast | None:
    """从机构预测中挑选指定指标和最小年份的最优条目。

    Param:
        forecasts: 机构预测列表
        metric: 指标名（如 EPS）
        min_year: 最低年份
    Return:
        优先选取年份较近、机构数较多的预测，未命中返回 None
    """
    candidates = []
    for forecast in forecasts:
        year = _parse_forecast_year(forecast.year)
        if forecast.metric != metric or year is None or year < min_year:
            continue
        if forecast.mean_value is None or forecast.mean_value <= 0:
            continue
        candidates.append((year, -(forecast.institution_count or 0), forecast))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def _forecast_confidence_adjustment(forecast: InstitutionForecast) -> float:
    """按机构数量与预测离散度计算置信度调整值。

    Param:
        forecast: 单条机构预测
    Return:
        置信度调整数（负数表示降低）
    """
    adjustment = 0.0
    institution_count = forecast.institution_count or 0
    if institution_count < 2:
        adjustment -= 0.15
    elif institution_count < 5:
        adjustment -= 0.08
    if forecast.min_value is not None and forecast.max_value is not None and forecast.mean_value not in (None, 0):
        if (forecast.max_value - forecast.min_value) / abs(forecast.mean_value) > 0.6:
            adjustment -= 0.12
    return adjustment


def _derive_peg_growth_rate(forecasts: list[InstitutionForecast], net_profit_ttm: float | None, total_shares: float | None, net_profit_yoy: float | None) -> tuple[float | None, str | None, float]:
    """综合机构预测与历史同比推导 PEG 用增长率。

    Param:
        forecasts: 机构预测列表
        net_profit_ttm: TTM 净利润
        total_shares: 总股本
        net_profit_yoy: 净利润同比增长率
    Return:
        (增长率, 增长依据描述, 置信度) 元组
    """
    current_year = datetime.now().year
    if net_profit_ttm is not None and net_profit_ttm > 0 and total_shares not in (None, 0):
        ttm_eps = net_profit_ttm / total_shares
        forecast = _select_forecast(forecasts, "EPS", current_year)
        forecast_year = _parse_forecast_year(forecast.year) if forecast is not None else None
        if forecast is not None and forecast.mean_value is not None and forecast_year is not None and ttm_eps > 0:
            years_forward = max(forecast_year - current_year + 1, 1)
            growth_rate = _normalize_peg_growth_rate((forecast.mean_value / ttm_eps) ** (1 / years_forward) - 1)
            if growth_rate is not None:
                confidence_score = max(0.3, min(0.8, 0.72 + _forecast_confidence_adjustment(forecast)))
                basis = f"机构 EPS 一致预期推导增长率 {growth_rate * 100:.1f}%（{forecast.year}，机构数 {forecast.institution_count or 0:g}）"
                return growth_rate, basis, confidence_score

    growth_rate = _normalize_peg_growth_rate(net_profit_yoy)
    if growth_rate is not None:
        return growth_rate, f"历史净利润同比增长率 {growth_rate * 100:.1f}%", 0.45
    return None, None, 0.3


def _target_peg_by_profile(profile: ValuationProfile) -> float | None:
    """根据股票画像选择 PEG 目标倍数。

    Param:
        profile: 估值画像对象
    Return:
        目标 PEG，亏损画像返回 None
    """
    target_by_category = {
        "growth": 1.1,
        "stable": 1.0,
        "general": 1.0,
        "cyclical": 0.8,
        "financial": 0.8,
        "loss_making": None,
    }
    return target_by_category.get(profile.category, 1.0)


def _cap_peg_target_pe(raw_target_pe: float, current_pe: float | None, peer_pe_median: float | None) -> tuple[float, list[str]]:
    """对 PEG 推导的目标 PE 设置上下限约束。

    Param:
        raw_target_pe: 原始目标 PE
        current_pe: 当前 PE
        peer_pe_median: 同行 PE 中位数
    Return:
        (受约束的目标 PE, 约束注释列表) 元组
    """
    capped = max(5.0, min(raw_target_pe, 60.0))
    notes: list[str] = []
    if capped != raw_target_pe:
        notes.append("目标 PE 按 5-60 倍区间约束")
    if peer_pe_median is not None and peer_pe_median > 0:
        peer_cap = peer_pe_median * 1.5
        if capped > peer_cap:
            capped = peer_cap
            notes.append("目标 PE 按同行 PE 中位数 1.5 倍约束")
    if current_pe is not None and current_pe > 0:
        current_cap = current_pe * 1.5
        if capped > current_cap:
            capped = current_cap
            notes.append("目标 PE 按当前 PE 1.5 倍约束")
    return round(capped, 4), notes


def _current_peg(current_pe: float | None, growth_rate: float | None) -> float | None:
    """根据当前 PE 与增长率计算当前 PEG。

    Param:
        current_pe: 当前 PE
        growth_rate: 增长率（小数形式）
    Return:
        当前 PEG，数据无效时返回 None
    """
    if current_pe is None or current_pe <= 0 or growth_rate is None or growth_rate <= 0:
        return None
    return round(current_pe / (growth_rate * 100), 4)


def _normalize_industry_text(basic_info: StockBasicInfo) -> str:
    """合并一级和二级行业名称为单一字符串。

    Param:
        basic_info: 股票基本信息
    Return:
        以空格连接的行业名称
    """
    names = [
        basic_info.first_industry.name if basic_info.first_industry else "",
        basic_info.second_industry.name if basic_info.second_industry else "",
    ]
    return " ".join(name for name in names if name)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    """判断文本是否包含任一关键词。

    Param:
        text: 待检查文本
        keywords: 关键词元组
    Return:
        命中任一关键词返回 True
    """
    return any(keyword in text for keyword in keywords)


def _calc_roe(fundamentals: ValuationFundamentals) -> float | None:
    """根据净利润和股东权益计算 ROE。

    Param:
        fundamentals: 估值基本面数据
    Return:
        ROE 小数值，数据不足时返回 None
    """
    if fundamentals.net_profit is None or fundamentals.shareholders_equity in (None, 0):
        return None
    return fundamentals.net_profit / fundamentals.shareholders_equity


def _is_loss_making(fundamentals: ValuationFundamentals) -> bool:
    """判断公司是否处于亏损状态。

    Param:
        fundamentals: 估值基本面数据
    Return:
        净利润或扣非净利润为负时返回 True
    """
    return any(value is not None and value < 0 for value in [fundamentals.net_profit, fundamentals.non_net_profit])


def _classify_stock_profile(basic_info: StockBasicInfo, fundamentals: ValuationFundamentals) -> ValuationProfile:
    """根据行业和财务指标对股票进行画像分类。

    Param:
        basic_info: 股票基本信息
        fundamentals: 估值基本面数据
    Return:
        ValuationProfile 对象，含分类和理由
    """
    industry_text = _normalize_industry_text(basic_info)
    rationale: list[str] = []
    if _is_loss_making(fundamentals):
        rationale.append("净利润或扣非净利润为负，盈利法估值可靠性较低")
        return ValuationProfile(category="loss_making", label="亏损/利润承压类", rationale=rationale)
    if _contains_any(industry_text, FINANCIAL_KEYWORDS):
        rationale.append(f"行业属性偏金融：{industry_text}")
        return ValuationProfile(category="financial", label="金融类", rationale=rationale)
    if _contains_any(industry_text, CYCLICAL_KEYWORDS):
        rationale.append(f"行业属性偏周期：{industry_text}")
        return ValuationProfile(category="cyclical", label="周期类", rationale=rationale)
    revenue_growth = _normalize_growth_rate(fundamentals.revenue_yoy)
    profit_growth = _normalize_growth_rate(fundamentals.net_profit_yoy)
    if _contains_any(industry_text, GROWTH_KEYWORDS) or revenue_growth >= 0.12 or profit_growth >= 0.12:
        rationale.append(f"行业或增速具备成长属性：{industry_text or '行业数据不足'}")
        return ValuationProfile(category="growth", label="成长类", rationale=rationale)
    if _contains_any(industry_text, STABLE_KEYWORDS) or (fundamentals.operating_cashflow is not None and fundamentals.operating_cashflow > 0 and fundamentals.net_profit is not None and fundamentals.net_profit > 0):
        rationale.append(f"现金流和利润为正，行业或经营特征偏稳定：{industry_text or '行业数据不足'}")
        return ValuationProfile(category="stable", label="稳定经营类", rationale=rationale)
    rationale.append("未匹配到强行业特征，采用通用估值权重")
    return ValuationProfile(category="general", label="通用类", rationale=rationale)


def _confidence_text(score: float) -> str:
    """将置信度数值映射为 high/medium/low 文本。

    Param:
        score: 置信度数值
    Return:
        置信度文本标签
    """
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _value_range(per_share_value: float | None, confidence_score: float | None, extra_spread: float = 0.0) -> list[float] | None:
    """按置信度生成公允价值上下区间。

    Param:
        per_share_value: 每股公允价值
        confidence_score: 置信度数值
        extra_spread: 额外宽幅
    Return:
        [下限, 上限] 列表，缺失输入时返回 None
    """
    if per_share_value is None:
        return None
    confidence = confidence_score or 0.5
    spread = (0.12 if confidence >= 0.75 else 0.18 if confidence >= 0.5 else 0.25) + extra_spread
    return [round(per_share_value * (1 - spread), 2), round(per_share_value * (1 + spread), 2)]


def _fallback_target_multiple(current_multiple: float | None, percentile: float | None) -> tuple[float | None, str | None]:
    """当无同行数据时按历史百分位推导目标倍数。

    Param:
        current_multiple: 当前倍数
        percentile: 历史百分位
    Return:
        (目标倍数, 依据说明) 元组
    """
    if current_multiple is None or current_multiple <= 0:
        return None, None
    if percentile is None:
        return round(current_multiple, 4), "当前倍数"
    if percentile >= 80:
        return round(current_multiple * 0.85, 4), "当前倍数按历史高位折价"
    if percentile <= 20:
        return round(current_multiple * 1.15, 4), "当前倍数按历史低位修复"
    return round(current_multiple, 4), "当前倍数"


def _derive_ttm_basis(market_cap: float | None, current_multiple: float | None, fallback_metric: float | None) -> float | None:
    """根据市值与倍数反推 TTM 基础指标。

    Param:
        market_cap: 总市值
        current_multiple: 当前倍数
        fallback_metric: 缺失时使用的回退值
    Return:
        TTM 基础指标，全部缺失时返回 None
    """
    if market_cap not in (None, 0) and current_multiple not in (None, 0) and current_multiple > 0:
        return market_cap / current_multiple
    return fallback_metric


def _annualize_report_metric(value: float | None, report_date: str | None) -> float | None:
    """按报告期将单季度/半年度指标年化。

    Param:
        value: 报告期指标值
        report_date: 报告期字符串
    Return:
        年化后的指标值
    """
    if value is None:
        return None
    if not report_date:
        return value
    text = str(report_date)
    if "03-31" in text or "一季" in text:
        return value * 4
    if "06-30" in text or "中报" in text:
        return value * 2
    if "09-30" in text or "三季" in text:
        return value * 4 / 3
    return value


def _build_multiple_valuation(method: str, basis_metric: float | None, target_multiple: float | None, current_price: float | None, total_shares: float | None, basis: str, confidence_score: float, applicability: str) -> ValuationMethodResult:
    """构造单一倍数法估值结果。

    Param:
        method: 估值方法名（PE/PB/PS 等）
        basis_metric: 基础财务指标
        target_multiple: 目标倍数
        current_price: 当前股价
        total_shares: 总股本
        basis: 估值依据说明
        confidence_score: 置信度数值
        applicability: 适用性说明
    Return:
        ValuationMethodResult 模型对象
    """
    confidence = _confidence_text(confidence_score)
    if basis_metric is None or basis_metric <= 0:
        return ValuationMethodResult(method=method, available=False, reason="基础指标不可用", basis=basis, confidence=confidence, confidence_score=confidence_score, applicability=applicability)
    if target_multiple is None or target_multiple <= 0:
        return ValuationMethodResult(method=method, available=False, reason="缺少有效的目标倍数", basis=basis, confidence=confidence, confidence_score=confidence_score, applicability=applicability)
    if total_shares in (None, 0):
        return ValuationMethodResult(method=method, available=False, reason="总股本不可用", basis=basis, confidence=confidence, confidence_score=confidence_score, applicability=applicability)

    equity_value = round(target_multiple * basis_metric, 2)
    per_share_value = round(equity_value / total_shares, 2)
    upside_pct = None if current_price in (None, 0) else round((per_share_value - current_price) / current_price * 100, 2)
    return ValuationMethodResult(
        method=method,
        available=True,
        target_multiple=round(target_multiple, 4),
        equity_value=equity_value,
        per_share_value=per_share_value,
        upside_pct=upside_pct,
        confidence=confidence,
        confidence_score=confidence_score,
        value_range=_value_range(per_share_value, confidence_score),
        applicability=applicability,
        basis=basis,
    )


def _build_peg_valuation(net_profit_ttm: float | None, current_pe: float | None, peer_pe_median: float | None, growth_rate: float | None, growth_basis: str | None, current_price: float | None, total_shares: float | None, profile: ValuationProfile, confidence_score: float) -> ValuationMethodResult:
    """构造 PEG 估值结果，包含目标 PE 推导与约束。

    Param:
        net_profit_ttm: TTM 净利润
        current_pe: 当前 PE
        peer_pe_median: 同行 PE 中位数
        growth_rate: 增长率（小数）
        growth_basis: 增长率依据说明
        current_price: 当前股价
        total_shares: 总股本
        profile: 估值画像
        confidence_score: 置信度数值
    Return:
        ValuationMethodResult 模型对象
    """
    applicability = "PEG 将盈利增速与 PE 结合，适合盈利为正且成长性较清晰的公司"
    target_peg = _target_peg_by_profile(profile)
    basis_parts = [growth_basis or "缺少有效盈利增长率"]
    if profile.category == "loss_making":
        return ValuationMethodResult(method="PEG", available=False, reason="亏损或盈利承压，PEG 不适用", basis="；".join(basis_parts), confidence="low", confidence_score=0.2, applicability=applicability)
    if growth_rate is None:
        return ValuationMethodResult(method="PEG", available=False, reason="成长率过低或不可用", basis="；".join(basis_parts), confidence="low", confidence_score=confidence_score, applicability=applicability)
    if target_peg is None:
        return ValuationMethodResult(method="PEG", available=False, reason="股票画像不适用 PEG", basis="；".join(basis_parts), confidence="low", confidence_score=confidence_score, applicability=applicability)

    current_peg = _current_peg(current_pe, growth_rate)
    raw_target_pe = target_peg * growth_rate * 100
    target_pe, cap_notes = _cap_peg_target_pe(raw_target_pe, current_pe, peer_pe_median)
    basis_parts.append(f"当前 PEG {current_peg:.2f}" if current_peg is not None else "当前 PEG 不可计算")
    basis_parts.append(f"目标 PEG {target_peg:.1f} 推导目标 PE {target_pe:.2f}")
    basis_parts.extend(cap_notes)
    return _build_multiple_valuation(
        "PEG",
        net_profit_ttm,
        target_pe,
        current_price,
        total_shares,
        "；".join(basis_parts),
        confidence_score,
        applicability,
    )


async def _fetch_institution_forecasts(code: str) -> list[InstitutionForecast]:
    """从同花顺抓取并解析机构盈利预测。

    Param:
        code: 股票代码
    Return:
        InstitutionForecast 列表，失败时返回空列表
    """
    forecasts: list[InstitutionForecast] = []
    try:
        reports_df = await call_blocking(_get_ths_provider().fetch_stock_forecast_reports, code=code)
        if reports_df is not None and not reports_df.empty:
            for _, row in reports_df.iterrows():
                forecasts.append(InstitutionForecast(
                    metric=str(row.get("指标", "")),
                    year=str(row.get("年度", "")),
                    institution_count=safe_float(row.get("预测机构数")),
                    min_value=safe_float(row.get("最小值")),
                    mean_value=safe_float(row.get("均值")),
                    max_value=safe_float(row.get("最大值")),
                    industry_avg=safe_float(row.get("行业平均数")),
                    unit=str(row.get("单位", "")).strip(),
                ))
    except Exception:
        logger.info(f"同花顺机构预测获取失败: {code}")
    return forecasts


def _build_dcf_valuation(operating_cashflow: float | None, net_profit: float | None, revenue_yoy: float | None, net_profit_yoy: float | None, current_price: float | None, total_shares: float | None) -> DCFValuationResult:
    """构造保守 DCF 估值结果（FCFE 近似模型）。

    Param:
        operating_cashflow: 经营现金流
        net_profit: 净利润
        revenue_yoy: 营收同比增长率
        net_profit_yoy: 净利润同比增长率
        current_price: 当前股价
        total_shares: 总股本
    Return:
        DCFValuationResult 模型对象
    """
    base_cashflow = None
    basis = None
    confidence_score = 0.45
    applicability = "DCF 对现金流假设敏感，仅作为区间参考"
    if operating_cashflow is not None and operating_cashflow > 0:
        base_cashflow = operating_cashflow * 0.7
        basis = "经营现金流折减 30% 近似 FCFE"
        confidence_score = 0.6
    elif net_profit is not None and net_profit > 0:
        base_cashflow = net_profit * 0.8
        basis = "净利润折减 20% 近似 FCFE"

    if base_cashflow is None or base_cashflow <= 0:
        return DCFValuationResult(available=False, reason="缺少可用现金流基础", basis=basis, confidence="low", confidence_score=confidence_score, applicability=applicability)
    if total_shares in (None, 0):
        return DCFValuationResult(available=False, reason="总股本不可用", basis=basis, confidence="low", confidence_score=confidence_score, applicability=applicability)

    discount_rate = 0.10
    terminal_growth_rate = 0.03
    growth_rate = max(_normalize_growth_rate(revenue_yoy), _normalize_growth_rate(net_profit_yoy))
    forecast_years = 5

    cashflow = base_cashflow
    discounted_sum = 0.0
    for year in range(1, forecast_years + 1):
        fade_rate = growth_rate if year <= 3 else growth_rate - (growth_rate - terminal_growth_rate) * ((year - 3) / 2)
        cashflow = cashflow * (1 + max(fade_rate, terminal_growth_rate))
        discounted_sum += cashflow / ((1 + discount_rate) ** year)

    terminal_cashflow = cashflow * (1 + terminal_growth_rate)
    terminal_value = terminal_cashflow / (discount_rate - terminal_growth_rate)
    equity_value = round(discounted_sum + terminal_value / ((1 + discount_rate) ** forecast_years), 2)
    per_share_value = round(equity_value / total_shares, 2)
    upside_pct = None if current_price in (None, 0) else round((per_share_value - current_price) / current_price * 100, 2)
    return DCFValuationResult(
        available=True,
        base_cashflow=round(base_cashflow, 2),
        discount_rate=discount_rate,
        terminal_growth_rate=terminal_growth_rate,
        forecast_years=forecast_years,
        equity_value=equity_value,
        per_share_value=per_share_value,
        upside_pct=upside_pct,
        confidence=_confidence_text(confidence_score),
        confidence_score=confidence_score,
        value_range=_value_range(per_share_value, confidence_score, extra_spread=0.07),
        applicability=applicability,
        basis=basis,
    )


def _base_method_weights(profile: ValuationProfile) -> dict[str, float]:
    """根据股票画像返回各估值方法的基础权重。

    Param:
        profile: 估值画像
    Return:
        方法名到权重的字典
    """
    weights_by_category = {
        "financial": {"pe": 0.12, "pb": 0.58, "ps": 0.08, "peg": 0.07, "dcf": 0.15},
        "cyclical": {"pe": 0.22, "pb": 0.43, "ps": 0.08, "peg": 0.07, "dcf": 0.20},
        "growth": {"pe": 0.18, "pb": 0.12, "ps": 0.28, "peg": 0.22, "dcf": 0.20},
        "stable": {"pe": 0.34, "pb": 0.18, "ps": 0.08, "peg": 0.10, "dcf": 0.30},
        "loss_making": {"pe": 0.0, "pb": 0.25, "ps": 0.55, "peg": 0.0, "dcf": 0.20},
        "general": {"pe": 0.25, "pb": 0.22, "ps": 0.22, "peg": 0.11, "dcf": 0.20},
    }
    return weights_by_category.get(profile.category, weights_by_category["general"])


def _adjust_method_weights(fair_values: dict[str, ValuationMethodResult | DCFValuationResult], base_weights: dict[str, float]) -> dict[str, float]:
    """根据置信度调整估值方法权重并归一化。

    Param:
        fair_values: 方法名到估值结果的字典
        base_weights: 基础权重字典
    Return:
        归一化后的权重字典
    """
    raw_weights = {
        method: base_weights.get(method, 0) * (item.confidence_score or 0.5)
        for method, item in fair_values.items()
        if item.available and item.per_share_value is not None and base_weights.get(method, 0) > 0
    }
    total = sum(raw_weights.values())
    if total <= 0:
        return {}
    return {method: round(weight / total, 4) for method, weight in raw_weights.items()}


def _apply_weights(fair_values: dict[str, ValuationMethodResult | DCFValuationResult], weights: dict[str, float]) -> None:
    """将权重写回各估值方法对象。

    Param:
        fair_values: 方法名到估值结果的字典
        weights: 方法名到权重的字典
    Return:
        无
    """
    for method, item in fair_values.items():
        item.weight = weights.get(method)


def _build_blended_value(fair_values: dict[str, ValuationMethodResult | DCFValuationResult], weights: dict[str, float]) -> float | None:
    """按权重加权得到综合公允每股价值。

    Param:
        fair_values: 方法名到估值结果的字典
        weights: 方法名到权重的字典
    Return:
        加权后的每股公允价值，无权重时返回 None
    """
    if not weights:
        return None
    return round(sum((fair_values[method].per_share_value or 0) * weight for method, weight in weights.items()), 2)


def _build_blended_range(fair_values: dict[str, ValuationMethodResult | DCFValuationResult], weights: dict[str, float]) -> list[float] | None:
    """按权重加权得到综合公允区间。

    Param:
        fair_values: 方法名到估值结果的字典
        weights: 方法名到权重的字典
    Return:
        [下限, 上限] 列表，缺失区间时返回 None
    """
    ranges = []
    for method, weight in weights.items():
        value_range = fair_values[method].value_range
        if value_range is None or len(value_range) != 2:
            return None
        ranges.append((value_range, weight))
    if not ranges:
        return None
    low = sum(value_range[0] * weight for value_range, weight in ranges)
    high = sum(value_range[1] * weight for value_range, weight in ranges)
    return [round(low, 2), round(high, 2)]


def _build_valuation_view(fair_value_range: list[float] | None, blended_fair_value: float | None, current_price: float | None) -> str | None:
    """根据当前价与公允区间判断估值倾向。

    Param:
        fair_value_range: 公允价值区间
        blended_fair_value: 综合公允价值
        current_price: 当前股价
    Return:
        高估/低估/基本合理 文本，缺失数据时返回 None
    """
    if current_price in (None, 0):
        return None
    if fair_value_range is not None and len(fair_value_range) == 2:
        low, high = fair_value_range
        if current_price < low * 0.9:
            return "低估"
        if current_price > high * 1.1:
            return "高估"
        return "基本合理"
    if blended_fair_value is None:
        return None
    diff_pct = (blended_fair_value - current_price) / current_price * 100
    if diff_pct >= 15:
        return "低估"
    if diff_pct <= -15:
        return "高估"
    return "基本合理"


def _build_valuation_summary(profile: ValuationProfile, fair_value_range: list[float] | None, valuation_view: str | None) -> str | None:
    """构造一句话估值摘要文本。

    Param:
        profile: 估值画像
        fair_value_range: 公允价值区间
        valuation_view: 估值倾向描述
    Return:
        摘要字符串，区间或观点缺失时返回兜底说明
    """
    if fair_value_range is None or valuation_view is None:
        return f"{profile.label}画像下，可用估值数据不足，建议结合财务质量和行业景气度进一步验证。"
    return f"{profile.label}画像下，综合合理区间约为 {fair_value_range[0]:.2f}-{fair_value_range[1]:.2f} 元，当前估值判断为{valuation_view}。"


async def _fetch_valuation_detail_inputs(code: str, raw_code: str):
    """并发抓取详细估值需要的多份原始数据。

    Param:
        code: 原始股票代码
        raw_code: 归一化后的代码
    Return:
        (基本信息, 估值数据, 财务指标, 机构预测) 元组
    """
    return await asyncio.gather(
        get_basic_info(code),
        get_valuation(code),
        get_financial_metrics(code),
        _fetch_institution_forecasts(raw_code),
    )


async def _fetch_valuation_percentiles(raw_code: str, compute_percentile) -> ValuationPercentiles:
    """并发计算 PE/PB/PS 三年百分位。

    Param:
        raw_code: 归一化后的股票代码
        compute_percentile: 百分位计算函数
    Return:
        ValuationPercentiles 模型对象
    """
    pe_percentile, pb_percentile, ps_percentile = await asyncio.gather(
        compute_percentile(raw_code, "市盈率(TTM)", "近三年"),
        compute_percentile(raw_code, "市净率", "近三年"),
        compute_percentile(raw_code, "市销率(TTM)", "近三年"),
        return_exceptions=True,
    )
    return ValuationPercentiles(
        pe_3y=None if isinstance(pe_percentile, Exception) else pe_percentile,
        pb_3y=None if isinstance(pb_percentile, Exception) else pb_percentile,
        ps_3y=None if isinstance(ps_percentile, Exception) else ps_percentile,
    )


def _build_peer_summary(valuation_data: dict) -> ValuationPeerSummary:
    """根据估值数据中的同行字段构造同行汇总。

    Param:
        valuation_data: 估值数据字典
    Return:
        ValuationPeerSummary 模型对象
    """
    peers = [ValuationPeer.model_validate(peer) for peer in valuation_data.get("peers", [])]
    return ValuationPeerSummary(
        pe_median=_median_positive([peer.pe_ttm for peer in peers]),
        pb_median=_median_positive([peer.pb for peer in peers]),
        ps_median=_median_positive([peer.ps_ttm for peer in peers]),
        peer_count=len(peers),
        peers=peers,
    )


def _build_fundamentals(financial_metrics) -> ValuationFundamentals:
    """从财务指标中提取估值用基本面数据。

    Param:
        financial_metrics: FinancialMetrics 模型对象
    Return:
        ValuationFundamentals 模型对象
    """
    return ValuationFundamentals(
        revenue=financial_metrics.metrics.get("营收"),
        revenue_yoy=financial_metrics.metrics.get("营收同比"),
        net_profit=financial_metrics.metrics.get("净利润"),
        net_profit_yoy=financial_metrics.metrics.get("净利润同比"),
        non_net_profit=financial_metrics.metrics.get("扣非净利润"),
        non_net_profit_yoy=financial_metrics.metrics.get("扣非净利润同比"),
        shareholders_equity=financial_metrics.metrics.get("股东权益"),
        operating_cashflow=financial_metrics.metrics.get("经营现金流"),
    )


def _derive_current_price(basic_info: StockBasicInfo) -> float | None:
    """通过市值和总股本反推当前股价。

    Param:
        basic_info: 股票基本信息
    Return:
        当前股价，数据缺失时返回 None
    """
    if basic_info.market_cap in (None, 0) or basic_info.total_shares in (None, 0):
        return None
    return round(basic_info.market_cap / basic_info.total_shares, 2)


def _build_detail_notes(profile: ValuationProfile) -> list[str]:
    """组装估值详情备注列表。

    Param:
        profile: 估值画像
    Return:
        备注字符串列表
    """
    return [
        *profile.rationale,
        "综合估值仅使用可用方法，并按股票画像和置信度动态加权。",
        "PEG 依赖盈利增长假设，增长率异常或预测缺失时会自动降级或剔除。",
        "DCF 采用保守 FCFE 代理模型，结果更适合作为区间参考。",
    ]


def _build_multiple_method_contexts(valuation_data: dict, percentiles: ValuationPercentiles, peer_summary: ValuationPeerSummary, profile: ValuationProfile, roe: float | None) -> dict[str, _MultipleMethodContext]:
    """组装 PE/PB/PS 倍数法上下文，按画像与 ROE 调整置信度。

    Param:
        valuation_data: 估值数据字典
        percentiles: 估值百分位
        peer_summary: 同行汇总
        profile: 估值画像
        roe: ROE 值
    Return:
        方法名到 _MultipleMethodContext 的字典
    """
    pe_target, pe_basis = (peer_summary.pe_median, "同行 PE 中位数") if peer_summary.pe_median is not None else _fallback_target_multiple(valuation_data.get("pe_ttm"), percentiles.pe_3y)
    pb_target, pb_basis = (peer_summary.pb_median, "同行 PB 中位数") if peer_summary.pb_median is not None else _fallback_target_multiple(valuation_data.get("pb"), percentiles.pb_3y)
    ps_target, ps_basis = (peer_summary.ps_median, "同行 PS 中位数") if peer_summary.ps_median is not None else _fallback_target_multiple(valuation_data.get("ps_ttm"), percentiles.ps_3y)

    pe_confidence = 0.65
    pe_applicability = "盈利为正时 PE 可反映利润定价"
    if profile.category == "loss_making":
        pe_target = None
        pe_confidence = 0.2
        pe_applicability = "亏损或扣非亏损，PE 不适合作为核心估值方法"
    elif profile.category == "cyclical":
        pe_confidence = 0.45
        pe_applicability = "周期行业利润波动较大，PE 仅作低权重参考"
    elif profile.category in {"stable", "growth"}:
        pe_confidence = 0.7

    pb_confidence = 0.65
    pb_applicability = "PB 可辅助衡量资产定价"
    if profile.category in {"financial", "cyclical"}:
        pb_confidence = 0.8
        pb_applicability = "金融/周期资产属性较强，PB 权重较高"
    if roe is not None and roe < 0.06:
        pb_confidence = min(pb_confidence, 0.5)
        pb_applicability = "ROE 偏低，PB 估值需要折价看待"
        if pb_target is not None:
            pb_target = pb_target * 0.85

    ps_confidence = 0.55
    ps_applicability = "PS 适合辅助观察收入规模定价"
    if profile.category in {"growth", "loss_making"}:
        ps_confidence = 0.72
        ps_applicability = "成长或利润承压阶段，PS 比 PE 更有参考价值"
    elif profile.category in {"financial", "stable"}:
        ps_confidence = 0.4
        ps_applicability = "该类型公司收入倍数解释力有限，PS 低权重参考"

    return {
        "pe": _MultipleMethodContext(pe_target, pe_basis, pe_confidence, pe_applicability),
        "pb": _MultipleMethodContext(pb_target, pb_basis, pb_confidence, pb_applicability),
        "ps": _MultipleMethodContext(ps_target, ps_basis, ps_confidence, ps_applicability),
    }


def _derive_valuation_bases(fundamentals: ValuationFundamentals, report_date: str | None, market_cap: float | None, valuation_data: dict) -> _ValuationBases:
    """构造估值用年化指标与 TTM 基础数据。

    Param:
        fundamentals: 估值基本面
        report_date: 最新报告期
        market_cap: 总市值
        valuation_data: 估值数据字典
    Return:
        _ValuationBases 数据类
    """
    net_profit_annualized = _annualize_report_metric(fundamentals.net_profit, report_date)
    revenue_annualized = _annualize_report_metric(fundamentals.revenue, report_date)
    operating_cashflow_annualized = _annualize_report_metric(fundamentals.operating_cashflow, report_date)
    return _ValuationBases(
        net_profit_annualized=net_profit_annualized,
        revenue_annualized=revenue_annualized,
        operating_cashflow_annualized=operating_cashflow_annualized,
        net_profit_ttm=_derive_ttm_basis(market_cap, valuation_data.get("pe_ttm"), net_profit_annualized),
        revenue_ttm=_derive_ttm_basis(market_cap, valuation_data.get("ps_ttm"), revenue_annualized),
    )


def _derive_peg_context(institution_forecasts: list[InstitutionForecast], net_profit_ttm: float | None, total_shares: float | None, net_profit_yoy: float | None, pe_ttm: float | None) -> _PegContext:
    """汇总 PEG 所需的增长率、依据、置信度与当前 PEG。

    Param:
        institution_forecasts: 机构盈利预测列表
        net_profit_ttm: TTM 净利润
        total_shares: 总股本
        net_profit_yoy: 净利润同比增长率
        pe_ttm: 当前 PE TTM
    Return:
        _PegContext 数据类
    """
    growth_rate, growth_basis, confidence = _derive_peg_growth_rate(
        institution_forecasts,
        net_profit_ttm,
        total_shares,
        net_profit_yoy,
    )
    return _PegContext(
        growth_rate=growth_rate,
        growth_basis=growth_basis,
        confidence=confidence,
        current_peg=_current_peg(pe_ttm, growth_rate),
    )


def _build_fair_values(valuation_data: dict, fundamentals: ValuationFundamentals, peer_summary: ValuationPeerSummary, profile: ValuationProfile, contexts: dict[str, _MultipleMethodContext], bases: _ValuationBases, peg_context: _PegContext, current_price: float | None, total_shares: float | None) -> dict[str, ValuationMethodResult | DCFValuationResult]:
    """组装 PE/PB/PS/PEG/DCF 各方法的估值结果。

    Param:
        valuation_data: 估值数据字典
        fundamentals: 估值基本面
        peer_summary: 同行汇总
        profile: 估值画像
        contexts: 倍数法上下文字典
        bases: 估值基础数据
        peg_context: PEG 上下文
        current_price: 当前股价
        total_shares: 总股本
    Return:
        方法名到估值结果模型的字典
    """
    pe_context = contexts["pe"]
    pb_context = contexts["pb"]
    ps_context = contexts["ps"]
    return {
        "pe": _build_multiple_valuation("PE", bases.net_profit_ttm, pe_context.target, current_price, total_shares, pe_context.basis or "同行 PE 中位数", pe_context.confidence, pe_context.applicability),
        "pb": _build_multiple_valuation("PB", fundamentals.shareholders_equity, pb_context.target, current_price, total_shares, pb_context.basis or "同行 PB 中位数", pb_context.confidence, pb_context.applicability),
        "ps": _build_multiple_valuation("PS", bases.revenue_ttm, ps_context.target, current_price, total_shares, ps_context.basis or "同行 PS 中位数", ps_context.confidence, ps_context.applicability),
        "peg": _build_peg_valuation(bases.net_profit_ttm, valuation_data.get("pe_ttm"), peer_summary.pe_median, peg_context.growth_rate, peg_context.growth_basis, current_price, total_shares, profile, peg_context.confidence),
        "dcf": _build_dcf_valuation(bases.operating_cashflow_annualized, bases.net_profit_annualized, fundamentals.revenue_yoy, fundamentals.net_profit_yoy, current_price, total_shares),
    }


def _build_weighted_outputs(fair_values: dict[str, ValuationMethodResult | DCFValuationResult], profile: ValuationProfile, current_price: float | None) -> _WeightedValuationOutputs:
    """根据估值结果构造加权综合公允价值与摘要。

    Param:
        fair_values: 方法名到估值结果的字典
        profile: 估值画像
        current_price: 当前股价
    Return:
        _WeightedValuationOutputs 数据类
    """
    method_weights = _adjust_method_weights(fair_values, _base_method_weights(profile))
    _apply_weights(fair_values, method_weights)
    blended_fair_value = _build_blended_value(fair_values, method_weights)
    fair_value_range = _build_blended_range(fair_values, method_weights)
    valuation_view = _build_valuation_view(fair_value_range, blended_fair_value, current_price)
    return _WeightedValuationOutputs(
        method_weights=method_weights,
        blended_fair_value=blended_fair_value,
        fair_value_range=fair_value_range,
        valuation_view=valuation_view,
        valuation_summary=_build_valuation_summary(profile, fair_value_range, valuation_view),
    )


async def get_valuation_detail(code: str, compute_percentile) -> ValuationDetail:
    """汇总多估值方法的详细结果，带 1 天缓存。

    Param:
        code: 股票代码
        compute_percentile: 估值百分位计算函数
    Return:
        ValuationDetail 模型对象，含画像、各方法结果与综合估值
    """
    sym = normalize_code(code)
    cache_key = dated_cache_key("valuation_detail_v3", sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    basic_info, valuation_data, financial_metrics, institution_forecasts = await _fetch_valuation_detail_inputs(code, sym.raw)
    percentiles = await _fetch_valuation_percentiles(sym.raw, compute_percentile)
    peer_summary = _build_peer_summary(valuation_data)
    fundamentals = _build_fundamentals(financial_metrics)
    current_price = _derive_current_price(basic_info)
    profile = _classify_stock_profile(basic_info, fundamentals)
    contexts = _build_multiple_method_contexts(valuation_data, percentiles, peer_summary, profile, _calc_roe(fundamentals))
    bases = _derive_valuation_bases(fundamentals, financial_metrics.latest_report_date, basic_info.market_cap, valuation_data)
    peg_context = _derive_peg_context(institution_forecasts, bases.net_profit_ttm, basic_info.total_shares, fundamentals.net_profit_yoy, valuation_data.get("pe_ttm"))
    fair_values = _build_fair_values(valuation_data, fundamentals, peer_summary, profile, contexts, bases, peg_context, current_price, basic_info.total_shares)
    weighted_outputs = _build_weighted_outputs(fair_values, profile, current_price)

    result = ValuationDetail(
        code=sym.raw,
        report_date=financial_metrics.latest_report_date,
        current_price=current_price,
        market_cap=basic_info.market_cap,
        total_shares=basic_info.total_shares,
        industry=basic_info.first_industry.name if basic_info.first_industry else None,
        multiples=ValuationMultiples(
            pe_ttm=valuation_data.get("pe_ttm"),
            pb=valuation_data.get("pb"),
            ps_ttm=valuation_data.get("ps_ttm"),
            peg=peg_context.current_peg,
        ),
        percentiles=percentiles,
        fundamentals=fundamentals,
        peer_summary=peer_summary,
        fair_values=fair_values,
        blended_fair_value=weighted_outputs.blended_fair_value,
        fair_value_range=weighted_outputs.fair_value_range,
        valuation_view=weighted_outputs.valuation_view,
        valuation_summary=weighted_outputs.valuation_summary,
        profile=profile,
        method_weights=weighted_outputs.method_weights,
        notes=_build_detail_notes(profile),
        institution_forecasts=institution_forecasts,
    )
    cache.set(cache_key, result, ttl=86400)
    return result
