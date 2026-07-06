import logging

import pandas as pd

from app.models.stock import DCFValuationResult, InstitutionForecast, StockBasicInfo, ValuationDetail, ValuationFundamentals, ValuationMethodResult, ValuationMultiples, ValuationPeer, ValuationPeerSummary, ValuationPercentiles, ValuationProfile
from app.services.providers import get_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking, akshare_semaphore, ths_semaphore
from app.utils.data_clean import safe_float

logger = logging.getLogger(__name__)

import asyncio
import re
from datetime import datetime
from app.services.stock.basic_info import get_basic_info
from app.services.stock.financials import get_financial_metrics
from app.utils.symbol_utils import normalize_code

from app.services.stock.valuation.helpers import (
    _median_positive, _normalize_growth_rate, _normalize_peg_growth_rate,
    _parse_forecast_year, _select_forecast, _forecast_confidence_adjustment,
    _confidence_text, _value_range, _fallback_target_multiple,
    _derive_ttm_basis, _annualize_report_metric, _current_peg,
    _get_akshare_provider, _get_ths_provider,
)
from app.services.stock.valuation.profile import (
    _normalize_industry_text, _contains_any, _calc_roe, _is_loss_making,
    _classify_stock_profile, _target_peg_by_profile, _cap_peg_target_pe,
    _derive_peg_growth_rate,
)
from app.services.stock.valuation.methods import (
    _build_multiple_valuation, _build_peg_valuation, _build_dcf_valuation,
)
from app.services.stock.valuation.blending import (
    _base_method_weights, _adjust_method_weights, _apply_weights,
    _build_blended_value, _build_blended_range,
    _build_valuation_view, _build_valuation_summary,
)

from app.services.stock.valuation.orchestrator import get_valuation
from app.services.stock.valuation.models import _MultipleMethodContext, _ValuationBases, _PegContext, _WeightedValuationOutputs

async def _fetch_institution_forecasts(code: str) -> list[InstitutionForecast]:
    """从同花顺抓取并解析机构盈利预测。

    Param:
        code: 股票代码
    Return:
        InstitutionForecast 列表，失败时返回空列表
    """
    forecasts: list[InstitutionForecast] = []
    try:
        reports_df = await call_blocking(_get_ths_provider().fetch_stock_forecast_reports, semaphore=ths_semaphore, code=code)
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

