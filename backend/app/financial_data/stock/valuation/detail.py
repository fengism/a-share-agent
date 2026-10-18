import asyncio
import json
import logging
import math
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from app.configuration.paths import DATA_DIR
from app.core.cache import analysis_cache as cache
from app.core.cache import cache_date, dated_cache_key
from app.core.cache_policies import VALUATION_DETAIL
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore, misc_semaphore, ths_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import is_hk_code, market_today, normalize_code, safe_float
from app.financial_data.stock.fundamentals.financials import get_financial, get_financial_metrics
from app.financial_data.stock.fundamentals.schemas import FinancialMetrics
from app.financial_data.stock.profile.basic_info import get_basic_info
from app.financial_data.stock.profile.schemas import StockBasicInfo
from app.financial_data.stock.valuation.blending import (
    _adjust_method_weights,
    _apply_weights,
    _base_method_weights,
    _build_blended_range,
    _build_blended_value,
    _build_valuation_summary,
    _build_valuation_view,
    _method_dispersion,
)
from app.financial_data.stock.valuation.helpers import (
    _annualize_report_metric,
    _cap_target_multiple,
    _current_peg,
    _derive_normalized_dcf_growth,
    _derive_ttm_basis,
    _derive_ttm_report_metric,
    _fallback_target_multiple,
    _get_ths_provider,
    _normalized_metric_basis,
    _peer_quality_benchmark,
    _quality_adjusted_multiple,
    _robust_peer_metric,
)
from app.financial_data.stock.valuation.methods import (
    _build_dcf_valuation,
    _build_multiple_valuation,
    _build_peg_valuation,
)
from app.financial_data.stock.valuation.models import (
    _MultipleMethodContext,
    _PegContext,
    _ValuationBases,
    _WeightedValuationOutputs,
)
from app.financial_data.stock.valuation.orchestrator import get_valuation
from app.financial_data.stock.valuation.percentiles import compute_percentile
from app.financial_data.stock.valuation.profile import (
    _calc_net_margin,
    _calc_roe,
    _classify_stock_profile,
    _derive_peg_growth_rate,
)
from app.financial_data.stock.valuation.schemas import (
    DCFValuationResult,
    InstitutionForecast,
    StockValuation,
    ValuationDataQuality,
    ValuationDetail,
    ValuationFundamentals,
    ValuationMethodResult,
    ValuationMultiples,
    ValuationPeer,
    ValuationPeerSummary,
    ValuationPercentiles,
    ValuationProfile,
)
from app.infrastructure.persistence.json_storage import atomic_write_json
from app.infrastructure.providers.provider_gateway import provider_gateway

logger = logging.getLogger(__name__)
_valuation_detail_singleflight = AsyncSingleFlight[ValuationDetail]()


async def _fetch_institution_forecasts(code: str) -> list[InstitutionForecast]:
    """从同花顺抓取并解析机构盈利预测。

    Param:
        code: 股票代码
    Return:
        InstitutionForecast 列表，失败时返回空列表
    """
    forecasts: list[InstitutionForecast] = []
    try:
        reports_df = await provider_gateway.call(
            "ths",
            "stock_forecast_reports",
            lambda: call_blocking(
                _get_ths_provider().fetch_stock_forecast_reports,
                semaphore=ths_semaphore,
                code=code,
            ),
        )
        if reports_df is not None and not reports_df.empty:
            for _, row in reports_df.iterrows():
                forecasts.append(
                    InstitutionForecast(
                        metric=str(row.get("指标", "")),
                        year=str(row.get("年度", "")),
                        institution_count=safe_float(row.get("预测机构数")),
                        min_value=safe_float(row.get("最小值")),
                        mean_value=safe_float(row.get("均值")),
                        max_value=safe_float(row.get("最大值")),
                        industry_avg=safe_float(row.get("行业平均数")),
                        unit=str(row.get("单位", "")).strip(),
                    )
                )
    except Exception:
        logger.info(f"同花顺机构预测获取失败: {code}")
    return forecasts


async def _fetch_valuation_detail_inputs(
    code: str,
    raw_code: str,
) -> tuple[
    StockBasicInfo,
    StockValuation,
    FinancialMetrics,
    list[InstitutionForecast],
    list[dict],
    list[dict],
    ValuationPercentiles,
]:
    """并发抓取详细估值需要的多份原始数据。

    Param:
        code: 原始股票代码
        raw_code: 归一化后的代码
    Return:
        (基本信息, 估值数据, 财务指标, 机构预测, 利润表, 现金流量表, 估值百分位) 元组
    """
    (
        basic_info,
        valuation_data,
        financial_metrics,
        institution_forecasts,
        profit_rows,
        cashflow_rows,
        percentiles,
    ) = await asyncio.gather(
        get_basic_info(code),
        get_valuation(code),
        get_financial_metrics(code),
        _fetch_institution_forecasts(raw_code),
        get_financial(code, "profit"),
        get_financial(code, "cashflow"),
        _fetch_valuation_percentiles(raw_code),
    )
    return (
        basic_info,
        valuation_data,
        financial_metrics,
        institution_forecasts,
        profit_rows,
        cashflow_rows,
        percentiles,
    )


async def _fetch_valuation_percentiles(raw_code: str) -> ValuationPercentiles:
    """并发计算 PE/PB/PS 三年百分位。

    Param:
        raw_code: 归一化后的股票代码
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
        pe_3y=None if isinstance(pe_percentile, BaseException) else pe_percentile,
        pb_3y=None if isinstance(pb_percentile, BaseException) else pb_percentile,
        ps_3y=None if isinstance(ps_percentile, BaseException) else ps_percentile,
    )


def _build_peer_summary(valuation_data: StockValuation) -> ValuationPeerSummary:
    """根据估值数据中的同行字段构造同行汇总。

    Param:
        valuation_data: 估值数据模型
    Return:
        ValuationPeerSummary 模型对象
    """
    peers = [peer for peer in valuation_data.peers if peer.code != valuation_data.code]
    pe_median, pe_stats = _robust_peer_metric([peer.pe_ttm for peer in peers])
    pb_median, pb_stats = _robust_peer_metric([peer.pb for peer in peers])
    ps_median, ps_stats = _robust_peer_metric([peer.ps_ttm for peer in peers])
    return ValuationPeerSummary(
        pe_median=pe_median,
        pb_median=pb_median,
        ps_median=ps_median,
        peer_count=len(peers),
        peers=peers,
        pe_stats=pe_stats,
        pb_stats=pb_stats,
        ps_stats=ps_stats,
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


def _resolve_price_and_shares(basic_info: StockBasicInfo) -> tuple[float | None, float | None]:
    """解析当前股价与总股本，保证两者口径一致。

    市值与股本同时可用时用二者反推现价，保证市值、现价、股本口径
    一致；任一字段缺失时再用行情现价与市值互推，避免仅因一个字段
    缺失就让全部倍数法估值不可用。

    Param:
        basic_info: 股票基本信息
    Return:
        (当前股价, 总股本) 元组
    """
    market_cap = basic_info.market_cap
    total_shares = basic_info.total_shares
    if total_shares is not None and (not math.isfinite(total_shares) or total_shares <= 0):
        total_shares = None
    if market_cap is not None and (not math.isfinite(market_cap) or market_cap <= 0):
        market_cap = None
    price = None
    if market_cap is not None and total_shares is not None:
        # 市值与股本同源时优先用二者反推，保证市值、现价、股本口径一致。
        price = market_cap / total_shares
    if price is None:
        price = basic_info.current_price
        if price is not None and (not math.isfinite(price) or price <= 0):
            price = None
    if total_shares is None and market_cap is not None and price is not None:
        total_shares = market_cap / price
    resolved_price = round(price, 2) if price is not None and math.isfinite(price) else None
    resolved_shares = total_shares if total_shares is not None and math.isfinite(total_shares) else None
    return resolved_price, resolved_shares


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
        "PB/PS 目标倍数按目标公司与同行的 ROE、净利率差异做质量调整，避免高盈利质量公司被同行低倍数系统性低估。",
        "金融类不使用 PS/PEG/DCF，周期类不使用 PEG/DCF，避免现金流与增速口径不匹配。",
        "上年同期缺失时用本期同比桥接 TTM；周期股用近三年或近一年与 TTM 平均盈利正常化。",
        "PEG 依赖盈利增长假设，增长率异常或预测缺失时会自动降级或剔除。",
        "DCF 采用保守 FCFE 代理模型，结果更适合作为区间参考。",
        "方法分歧过大时标注“分歧较大”，不强行给出单一中枢。",
    ]


def _build_multiple_method_contexts(
    valuation_data: StockValuation,
    percentiles: ValuationPercentiles,
    peer_summary: ValuationPeerSummary,
    profile: ValuationProfile,
    stock_roe: float | None,
    stock_net_margin: float | None,
    normalized_roe: float | None = None,
    normalized_net_margin: float | None = None,
    normalized_basis: str | None = None,
) -> dict[str, _MultipleMethodContext]:
    """组装 PE/PB/PS 倍数法上下文，并按财务质量调整目标倍数。

    直接把同行 PB/PS 中位数套到高 ROE 或高净利率公司上，会得到远低于
    现价的“合理价值”；反之低质量公司会被高估。这里用同行 PB/PE 近似
    同行 ROE、PS/PE 近似同行净利率，对 PB/PS 目标倍数做质量调整。
    周期股使用正常化盈利（近三年平均，历史不足时用近一年与 TTM 平均）
    计算的 ROE/净利率，避免峰值或低谷盈利把 PB/PS 推到极端；同行 TTM
    盈利失真时，PE 改用前瞻 PE 口径。

    Param:
        valuation_data: 估值数据模型
        percentiles: 估值百分位
        peer_summary: 同行汇总
        profile: 估值画像
        stock_roe: 目标公司 TTM ROE
        stock_net_margin: 目标公司 TTM 净利率
        normalized_roe: 正常化 ROE（周期股使用）
        normalized_net_margin: 正常化净利率（周期股使用）
        normalized_basis: 正常化口径说明
    Return:
        方法名到 _MultipleMethodContext 的字典
    """
    pe_target, pe_basis = (
        (peer_summary.pe_median, "同行 PE 中位数")
        if peer_summary.pe_median is not None
        else _fallback_target_multiple(valuation_data.pe_ttm, percentiles.pe_3y)
    )
    pb_target, pb_basis = (
        (peer_summary.pb_median, "同行 PB 中位数")
        if peer_summary.pb_median is not None
        else _fallback_target_multiple(valuation_data.pb, percentiles.pb_3y)
    )
    ps_target, ps_basis = (
        (peer_summary.ps_median, "同行 PS 中位数")
        if peer_summary.ps_median is not None
        else _fallback_target_multiple(valuation_data.ps_ttm, percentiles.ps_3y)
    )

    use_normalized = profile.category == "cyclical"
    quality_roe = normalized_roe if use_normalized and normalized_roe is not None else stock_roe
    quality_margin = (
        normalized_net_margin if use_normalized and normalized_net_margin is not None else stock_net_margin
    )
    quality_note = (
        f"按{normalized_basis}盈利正常化"
        if use_normalized
        and normalized_basis
        and (normalized_roe is not None or normalized_net_margin is not None)
        else None
    )
    peer_roe, peer_roe_basis = _peer_quality_benchmark(peer_summary.peers, "pb", "pe_ttm", quality_roe)
    peer_net_margin, peer_margin_basis = _peer_quality_benchmark(
        peer_summary.peers, "ps_ttm", "pe_ttm", quality_margin
    )

    pe_current_multiple = None
    peer_forward_pe, _ = _robust_peer_metric([peer._pe_forward for peer in peer_summary.peers])
    target_forward_pe = getattr(valuation_data, "_pe_forward", None)
    forward_pe_distorted = (
        peer_forward_pe is not None
        and target_forward_pe is not None
        and math.isfinite(target_forward_pe)
        and target_forward_pe > 0
        and peer_summary.pe_median is not None
        and peer_summary.pe_median > 0
        and (
            peer_forward_pe < peer_summary.pe_median * 0.7
            or peer_forward_pe > peer_summary.pe_median * 1.3
        )
    )
    if forward_pe_distorted:
        assert (
            peer_forward_pe is not None
            and target_forward_pe is not None
            and peer_summary.pe_median is not None
        )
        # 同行 TTM 盈利处于低谷或峰值时，TTM PE 会被动失真，改用前瞻 PE 口径。
        pe_target = peer_forward_pe
        pe_basis = "同行前瞻 PE 中位数（TTM 盈利失真，改用前瞻口径）"
        pe_current_multiple = target_forward_pe

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
    if pe_target is not None:
        pe_target, pe_cap_note = _cap_target_multiple(
            pe_target, pe_current_multiple or valuation_data.pe_ttm, label="PE"
        )
        if pe_cap_note:
            pe_basis = f"{pe_basis}；{pe_cap_note}" if pe_basis else pe_cap_note

    pb_confidence = 0.65
    pb_applicability = "PB 可辅助衡量资产定价"
    if profile.category in {"financial", "cyclical"}:
        pb_confidence = 0.8
        pb_applicability = "金融/周期资产属性较强，PB 权重较高"
    if pb_target is not None:
        pb_target, pb_quality_note = _quality_adjusted_multiple(pb_target, quality_roe, peer_roe, label="ROE")
        if pb_quality_note:
            if peer_roe_basis and "质量调整 ×" in pb_quality_note:
                pb_quality_note = f"{pb_quality_note}，对标{peer_roe_basis}"
            if quality_note and "质量调整 ×" in pb_quality_note:
                pb_quality_note = f"{pb_quality_note}，{quality_note}"
            pb_basis = f"{pb_basis}；{pb_quality_note}" if pb_basis else pb_quality_note
        pb_target, pb_cap_note = _cap_target_multiple(pb_target, valuation_data.pb, label="PB")
        if pb_cap_note:
            pb_basis = f"{pb_basis}；{pb_cap_note}" if pb_basis else pb_cap_note
    if quality_roe is not None and quality_roe < 0.06:
        pb_confidence = min(pb_confidence, 0.5)
        pb_applicability = "ROE 偏低，PB 估值需要折价看待"
    elif quality_roe is not None and quality_roe > 0.2 and peer_roe is not None and quality_roe > peer_roe * 1.5:
        pb_applicability = "ROE 显著高于同行，PB 已按盈利质量上调"

    ps_confidence = 0.55
    ps_applicability = "PS 适合辅助观察收入规模定价"
    if profile.category == "financial":
        ps_target = None
        ps_basis = "金融企业收入口径与一般企业不可比，PS 不参与估值"
        ps_confidence = 0.2
        ps_applicability = "金融企业以 PE/PB 为主，PS 不适用"
    else:
        if ps_target is not None:
            ps_target, ps_quality_note = _quality_adjusted_multiple(
                ps_target, quality_margin, peer_net_margin, label="净利率"
            )
            if ps_quality_note:
                if peer_margin_basis and "质量调整 ×" in ps_quality_note:
                    ps_quality_note = f"{ps_quality_note}，对标{peer_margin_basis}"
                if quality_note and "质量调整 ×" in ps_quality_note:
                    ps_quality_note = f"{ps_quality_note}，{quality_note}"
                ps_basis = f"{ps_basis}；{ps_quality_note}" if ps_basis else ps_quality_note
            ps_target, ps_cap_note = _cap_target_multiple(ps_target, valuation_data.ps_ttm, label="PS")
            if ps_cap_note:
                ps_basis = f"{ps_basis}；{ps_cap_note}" if ps_basis else ps_cap_note
        if profile.category in {"growth", "loss_making"}:
            ps_confidence = 0.72
            ps_applicability = "成长或利润承压阶段，PS 比 PE 更有参考价值"
        elif profile.category == "stable":
            ps_confidence = 0.4
            ps_applicability = "该类型公司收入倍数解释力有限，PS 低权重参考"

    return {
        "pe": _MultipleMethodContext(
            pe_target, pe_basis, pe_confidence, pe_applicability, pe_current_multiple
        ),
        "pb": _MultipleMethodContext(pb_target, pb_basis, pb_confidence, pb_applicability),
        "ps": _MultipleMethodContext(ps_target, ps_basis, ps_confidence, ps_applicability),
    }


def _derive_valuation_bases(
    fundamentals: ValuationFundamentals,
    report_date: str | None,
    market_cap: float | None,
    valuation_data: StockValuation,
    profit_rows: list[dict],
    cashflow_rows: list[dict],
) -> _ValuationBases:
    """构造估值用年化指标与 TTM 基础数据。

    Param:
        fundamentals: 估值基本面
        report_date: 最新报告期
        market_cap: 总市值
        valuation_data: 估值数据模型
    Return:
        _ValuationBases 数据类
    """
    net_profit_ttm, net_profit_source = _derive_ttm_report_metric(
        profit_rows,
        ("PARENT_NETPROFIT", "NET_PROFIT"),
        report_date,
        fundamentals.net_profit_yoy,
    )
    revenue_ttm, revenue_source = _derive_ttm_report_metric(
        profit_rows,
        ("TOTAL_OPERATE_INCOME", "OPERATE_INCOME", "TOTAL_REVENUE"),
        report_date,
        fundamentals.revenue_yoy,
    )
    operating_cashflow_ttm, operating_cashflow_source = _derive_ttm_report_metric(
        cashflow_rows,
        ("NETCASH_OPERATE",),
        report_date,
    )
    capital_expenditure_ttm, capital_expenditure_source = _derive_ttm_report_metric(
        cashflow_rows,
        ("CONSTRUCT_LONG_ASSET", "ACQUASSETCASH"),
        report_date,
    )
    loan_proceeds_ttm, loan_proceeds_source = _derive_ttm_report_metric(
        cashflow_rows,
        ("RECEIVE_LOAN_CASH", "LOANGETCASH", "RECEFROMLOAN"),
        report_date,
    )
    debt_repayments_ttm, debt_repayments_source = _derive_ttm_report_metric(
        cashflow_rows,
        ("PAY_DEBT_CASH", "DEBTPAYCASH"),
        report_date,
    )
    net_borrowing_ttm = None
    net_borrowing_source = "unavailable"
    if loan_proceeds_ttm is not None and debt_repayments_ttm is not None:
        net_borrowing_ttm = loan_proceeds_ttm - debt_repayments_ttm
        net_borrowing_source = min(
            (loan_proceeds_source, debt_repayments_source),
            key=_source_quality,
        )
    normalized_growth_rate, normalized_growth_basis, normalized_growth_quality = _derive_normalized_dcf_growth(
        profit_rows,
        fundamentals.revenue_yoy,
        fundamentals.net_profit_yoy,
        report_date,
    )
    parsed_report_date = None
    try:
        parsed_report_date = date.fromisoformat(str(report_date or "")[:10])
    except ValueError:
        pass
    if fundamentals.shareholders_equity is None:
        balance_sheet_quality = 0.2
    elif parsed_report_date is None:
        balance_sheet_quality = 0.55
    else:
        age_days = (market_today() - parsed_report_date).days
        balance_sheet_quality = 0.95 if 0 <= age_days <= 550 else 0.7 if age_days <= 900 else 0.45
    net_profit_annualized = _annualize_report_metric(fundamentals.net_profit, report_date)
    revenue_annualized = _annualize_report_metric(fundamentals.revenue, report_date)
    operating_cashflow_annualized = _annualize_report_metric(
        fundamentals.operating_cashflow,
        report_date,
    )
    if net_profit_ttm is None:
        net_profit_ttm = _derive_ttm_basis(
            market_cap,
            valuation_data.pe_ttm,
            net_profit_annualized,
        )
        net_profit_source = (
            "market_implied"
            if market_cap not in (None, 0) and valuation_data.pe_ttm not in (None, 0)
            else "annualized_fallback"
        )
    if revenue_ttm is None:
        revenue_ttm = _derive_ttm_basis(
            market_cap,
            valuation_data.ps_ttm,
            revenue_annualized,
        )
        revenue_source = (
            "market_implied"
            if market_cap not in (None, 0) and valuation_data.ps_ttm not in (None, 0)
            else "annualized_fallback"
        )
    normalized_net_profit, normalized_net_profit_basis = _normalized_metric_basis(
        profit_rows,
        ("PARENT_NETPROFIT", "NET_PROFIT"),
        net_profit_ttm,
    )
    normalized_revenue, normalized_revenue_basis = _normalized_metric_basis(
        profit_rows,
        ("TOTAL_OPERATE_INCOME", "OPERATE_INCOME", "TOTAL_REVENUE"),
        revenue_ttm,
    )
    normalized_basis = normalized_net_profit_basis or normalized_revenue_basis
    normalized_roe = (
        _calc_roe(fundamentals, normalized_net_profit) if normalized_net_profit is not None else None
    )
    normalized_net_margin = _calc_net_margin(normalized_net_profit, normalized_revenue)
    return _ValuationBases(
        net_profit_annualized=net_profit_annualized,
        revenue_annualized=revenue_annualized,
        operating_cashflow_annualized=(
            operating_cashflow_ttm if operating_cashflow_ttm is not None else operating_cashflow_annualized
        ),
        capital_expenditure_ttm=(abs(capital_expenditure_ttm) if capital_expenditure_ttm is not None else None),
        net_borrowing_ttm=net_borrowing_ttm,
        net_profit_ttm=net_profit_ttm,
        revenue_ttm=revenue_ttm,
        normalized_net_profit=normalized_net_profit,
        normalized_revenue=normalized_revenue,
        normalized_roe=normalized_roe,
        normalized_net_margin=normalized_net_margin,
        normalized_basis=normalized_basis,
        normalized_growth_rate=normalized_growth_rate,
        normalized_growth_basis=normalized_growth_basis,
        normalized_growth_quality=normalized_growth_quality,
        balance_sheet_quality=balance_sheet_quality,
        net_profit_source=net_profit_source,
        revenue_source=revenue_source,
        operating_cashflow_source=(
            operating_cashflow_source if operating_cashflow_ttm is not None else "annualized_fallback"
        ),
        capital_expenditure_source=capital_expenditure_source,
        net_borrowing_source=net_borrowing_source,
    )


def _source_quality(source: str) -> float:
    return {
        "reported_ttm": 1.0,
        "reported_annual": 0.95,
        "reported_ttm_yoy_bridge": 0.85,
        "annualized_fallback": 0.55,
        "market_implied": 0.45,
    }.get(source, 0.2)


def _build_data_quality(
    bases: _ValuationBases,
    peer_summary: ValuationPeerSummary,
    profile: ValuationProfile,
) -> ValuationDataQuality:
    is_financial = profile.category == "financial"
    peer_scores = [peer_summary.pe_stats.confidence_score, peer_summary.pb_stats.confidence_score]
    if not is_financial:
        peer_scores.append(peer_summary.ps_stats.confidence_score)
    peer_confidence = sum(peer_scores) / len(peer_scores)
    ttm_quality = (
        _source_quality(bases.net_profit_source)
        if is_financial
        else (_source_quality(bases.net_profit_source) + _source_quality(bases.revenue_source)) / 2
    )
    cashflow_quality = (
        _source_quality(bases.operating_cashflow_source) + _source_quality(bases.capital_expenditure_source)
    ) / 2
    if is_financial:
        # 金融企业不使用 PS/DCF，数据质量只由盈利口径与 PE/PB 同行样本决定。
        score = round(0.60 * ttm_quality + 0.40 * peer_confidence, 4)
    else:
        score = round(0.45 * ttm_quality + 0.30 * cashflow_quality + 0.25 * peer_confidence, 4)
    limitations = []
    disclosed_sources = {"reported_ttm", "reported_annual"}
    if bases.net_profit_source not in disclosed_sources:
        limitations.append("净利润未使用完整披露 TTM，估值基础可靠性下降。")
    if not is_financial and bases.revenue_source not in disclosed_sources:
        limitations.append("营业收入未使用完整披露 TTM，PS 估值仅供参考。")
    if not is_financial and bases.capital_expenditure_ttm is None:
        limitations.append("资本开支缺失，DCF 使用保守现金流代理。")
    peer_sample_sizes = [peer_summary.pe_stats.sample_size, peer_summary.pb_stats.sample_size]
    if not is_financial:
        peer_sample_sizes.append(peer_summary.ps_stats.sample_size)
    if min(peer_sample_sizes) < 3:
        limitations.append("有效同行样本偏少，相对估值置信度有限。")
    if profile.category == "loss_making":
        limitations.append("亏损公司未计入研发管线与扭亏预期，PB/PS 估值参考性有限。")
    return ValuationDataQuality(
        score=score,
        grade="high" if score >= 0.8 else "medium" if score >= 0.6 else "low",
        ttm_source=bases.net_profit_source,
        cashflow_source=("reported_fcfe" if bases.capital_expenditure_ttm is not None else "cashflow_proxy"),
        peer_confidence=round(peer_confidence, 4),
        limitations=limitations,
    )


def _build_method_data_quality(
    bases: _ValuationBases,
    peer_summary: ValuationPeerSummary,
    growth_quality: float,
) -> dict[str, float]:
    """按各估值方法实际依赖的数据计算独立质量分。"""

    def average(*scores: float) -> float:
        return round(sum(scores) / len(scores), 4)

    return {
        "pe": average(_source_quality(bases.net_profit_source), peer_summary.pe_stats.confidence_score),
        "pb": average(bases.balance_sheet_quality, peer_summary.pb_stats.confidence_score),
        "ps": average(_source_quality(bases.revenue_source), peer_summary.ps_stats.confidence_score),
        "peg": average(
            _source_quality(bases.net_profit_source),
            max(0.0, min(growth_quality, 1.0)),
            peer_summary.pe_stats.confidence_score,
        ),
        "dcf": average(
            _source_quality(bases.operating_cashflow_source),
            _source_quality(bases.capital_expenditure_source),
            _source_quality(bases.net_borrowing_source),
            max(0.0, min(bases.normalized_growth_quality, 1.0)),
        ),
    }


def _derive_peg_context(
    institution_forecasts: list[InstitutionForecast],
    net_profit_ttm: float | None,
    total_shares: float | None,
    net_profit_yoy: float | None,
    pe_ttm: float | None,
) -> _PegContext:
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


def _build_fair_values(
    valuation_data: StockValuation,
    fundamentals: ValuationFundamentals,
    peer_summary: ValuationPeerSummary,
    profile: ValuationProfile,
    contexts: dict[str, _MultipleMethodContext],
    bases: _ValuationBases,
    peg_context: _PegContext,
    current_price: float | None,
    total_shares: float | None,
    data_quality: ValuationDataQuality,
) -> dict[str, ValuationMethodResult | DCFValuationResult]:
    """组装 PE/PB/PS/PEG/DCF 各方法的估值结果。

    Param:
        valuation_data: 估值数据模型
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
    method_data_quality = _build_method_data_quality(
        bases,
        peer_summary,
        peg_context.confidence,
    )
    return {
        "pe": _build_multiple_valuation(
            "PE",
            bases.net_profit_ttm,
            pe_context.target,
            current_price,
            total_shares,
            pe_context.basis or "同行 PE 中位数",
            pe_context.confidence,
            pe_context.applicability,
            method_data_quality["pe"],
            current_multiple=pe_context.current_multiple or valuation_data.pe_ttm,
        ),
        "pb": _build_multiple_valuation(
            "PB",
            fundamentals.shareholders_equity,
            pb_context.target,
            current_price,
            total_shares,
            pb_context.basis or "同行 PB 中位数",
            pb_context.confidence,
            pb_context.applicability,
            method_data_quality["pb"],
            current_multiple=valuation_data.pb,
        ),
        "ps": _build_multiple_valuation(
            "PS",
            bases.revenue_ttm,
            ps_context.target,
            current_price,
            total_shares,
            ps_context.basis or "同行 PS 中位数",
            ps_context.confidence,
            ps_context.applicability,
            method_data_quality["ps"],
            current_multiple=valuation_data.ps_ttm,
        ),
        "peg": _build_peg_valuation(
            bases.net_profit_ttm,
            valuation_data.pe_ttm,
            peer_summary.pe_median,
            peg_context.growth_rate,
            peg_context.growth_basis,
            current_price,
            total_shares,
            profile,
            peg_context.confidence,
            method_data_quality["peg"],
        ),
        "dcf": _build_dcf_valuation(
            bases.operating_cashflow_annualized,
            bases.net_profit_annualized,
            fundamentals.revenue_yoy,
            fundamentals.net_profit_yoy,
            current_price,
            total_shares,
            capital_expenditure=bases.capital_expenditure_ttm,
            net_borrowing=bases.net_borrowing_ttm,
            normalized_growth_rate=bases.normalized_growth_rate,
            growth_basis=bases.normalized_growth_basis,
            data_quality_score=method_data_quality["dcf"],
            disabled_reason=(
                "金融企业现金流口径与 FCFE 不匹配，DCF 不参与估值"
                if profile.category == "financial"
                else "周期行业当期现金流受商品价格影响大，DCF 不参与估值"
                if profile.category == "cyclical"
                else None
            ),
        ),
    }


def _build_weighted_outputs(
    fair_values: dict[str, ValuationMethodResult | DCFValuationResult],
    profile: ValuationProfile,
    current_price: float | None,
) -> _WeightedValuationOutputs:
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
    dispersion = _method_dispersion(fair_values, method_weights)
    valuation_view = _build_valuation_view(fair_value_range, blended_fair_value, current_price, dispersion)
    if profile.category == "loss_making" and valuation_view in {"低估", "高估"}:
        # 亏损公司缺少盈利锚，PB/PS 方向性结论容易被研发管线/扭亏预期推翻。
        valuation_view = "参考性有限"
    return _WeightedValuationOutputs(
        method_weights=method_weights,
        blended_fair_value=blended_fair_value,
        fair_value_range=fair_value_range,
        method_dispersion=dispersion,
        valuation_view=valuation_view,
        valuation_summary=_build_valuation_summary(profile, fair_value_range, valuation_view, dispersion),
    )


def _snapshot_path(code: str) -> Path:
    return Path(DATA_DIR) / "valuation_snapshots" / f"{code}.json"


_VALUATION_SNAPSHOT_SCHEMA_VERSION = 9


def _read_disk_snapshot(code: str, *, ignore_date: bool = False) -> ValuationDetail | None:
    path = _snapshot_path(code)
    try:
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            logger.debug("估值快照结构无效 %s: payload 非对象", code)
            return None
        if payload.get("schema_version") != _VALUATION_SNAPSHOT_SCHEMA_VERSION:
            logger.debug(
                "估值快照版本过期 %s: expected=%s actual=%s",
                code,
                _VALUATION_SNAPSHOT_SCHEMA_VERSION,
                payload.get("schema_version"),
            )
            return None
        if payload.get("code") not in (None, code):
            logger.debug("估值快照代码不匹配 %s: %s", code, payload.get("code"))
            return None
        if not ignore_date and payload.get("snapshot_date") != cache_date():
            return None
        data = payload.get("data")
        if not isinstance(data, dict):
            logger.debug("估值快照缺少 data %s", code)
            return None
        snapshot: ValuationDetail = ValuationDetail.model_validate(data)
        return snapshot
    except Exception as error:
        logger.debug("读取个股估值快照失败 %s: %s", code, error)
        return None


def _write_disk_snapshot(code: str, detail: ValuationDetail) -> None:
    path = _snapshot_path(code)
    try:
        payload = {
            "schema_version": _VALUATION_SNAPSHOT_SCHEMA_VERSION,
            "snapshot_date": cache_date(),
            "code": code,
            "data": detail.model_dump(),
        }
        atomic_write_json(path, payload, indent=2)
    except Exception as error:
        logger.warning("写入个股估值快照失败 %s: %s", code, error)


async def _load_valuation_detail(code: str) -> ValuationDetail:
    """汇总多估值方法的详细结果，带 L1 内存 + L2 磁盘分级缓存。

    Param:
        code: 股票代码
    Return:
        ValuationDetail 模型对象，含画像、各方法结果与综合估值
    """
    sym = normalize_code(code)
    cache_key = dated_cache_key("valuation_detail_v9", sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        cached_detail: ValuationDetail = ValuationDetail.model_validate(cached)
        return cached_detail

    disk_cached: ValuationDetail | None = await call_blocking(_read_disk_snapshot, sym.raw, semaphore=misc_semaphore)
    if disk_cached is not None:
        cache.set(cache_key, disk_cached, ttl=VALUATION_DETAIL.ttl_seconds)
        return disk_cached

    try:
        (
            basic_info,
            valuation_data,
            financial_metrics,
            institution_forecasts,
            profit_rows,
            cashflow_rows,
            percentiles,
        ) = await _fetch_valuation_detail_inputs(code, sym.raw)
    except Exception as exc:
        fallback: ValuationDetail | None = await call_blocking(
            _read_disk_snapshot, sym.raw, ignore_date=True, semaphore=misc_semaphore
        )
        if fallback is not None:
            logger.warning("估值上游数据获取失败，回退历史本地快照 code=%s: %s", sym.raw, exc)
            return fallback
        raise

    peer_summary = _build_peer_summary(valuation_data)
    fundamentals = _build_fundamentals(financial_metrics)
    current_price, total_shares = _resolve_price_and_shares(basic_info)
    bases = _derive_valuation_bases(
        fundamentals,
        financial_metrics.latest_report_date,
        basic_info.market_cap,
        valuation_data,
        profit_rows,
        cashflow_rows,
    )
    fundamentals.capital_expenditure = bases.capital_expenditure_ttm
    profile = _classify_stock_profile(basic_info, fundamentals, bases.net_profit_ttm)
    stock_roe = _calc_roe(fundamentals, bases.net_profit_ttm)
    stock_net_margin = _calc_net_margin(bases.net_profit_ttm, bases.revenue_ttm)
    contexts = _build_multiple_method_contexts(
        valuation_data,
        percentiles,
        peer_summary,
        profile,
        stock_roe,
        stock_net_margin,
        bases.normalized_roe,
        bases.normalized_net_margin,
        bases.normalized_basis,
    )
    data_quality = _build_data_quality(bases, peer_summary, profile)
    peg_context = _derive_peg_context(
        institution_forecasts,
        bases.net_profit_ttm,
        total_shares,
        fundamentals.net_profit_yoy,
        valuation_data.pe_ttm,
    )
    fair_values = _build_fair_values(
        valuation_data,
        fundamentals,
        peer_summary,
        profile,
        contexts,
        bases,
        peg_context,
        current_price,
        total_shares,
        data_quality,
    )
    weighted_outputs = _build_weighted_outputs(fair_values, profile, current_price)
    if weighted_outputs.method_dispersion is not None and weighted_outputs.method_dispersion > 2.2:
        data_quality.limitations.append(
            f"各估值方法结果分歧较大（最高/最低约 {weighted_outputs.method_dispersion:.1f} 倍），综合中枢参考性下降。"
        )

    result = ValuationDetail(
        code=sym.raw,
        report_date=financial_metrics.latest_report_date,
        current_price=current_price,
        market_cap=basic_info.market_cap,
        total_shares=total_shares,
        industry=basic_info.first_industry.name if basic_info.first_industry else None,
        multiples=ValuationMultiples(
            pe_ttm=valuation_data.pe_ttm,
            pb=valuation_data.pb,
            ps_ttm=valuation_data.ps_ttm,
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
        data_quality=data_quality,
        notes=_build_detail_notes(profile),
        institution_forecasts=institution_forecasts,
    )
    cache.set(cache_key, result, ttl=VALUATION_DETAIL.ttl_seconds)
    await call_blocking(_write_disk_snapshot, sym.raw, result, semaphore=misc_semaphore)
    return result


async def _load_hk_valuation_detail(norm_code: str) -> ValuationDetail:
    from app.financial_data.hk.service import hk_market_service

    cache_key = dated_cache_key("valuation_detail_v9", norm_code)
    cached = cache.get(cache_key)
    if cached is not None:
        cached_hk_detail: ValuationDetail = ValuationDetail.model_validate(cached)
        return cached_hk_detail

    disk_cached: ValuationDetail | None = await call_blocking(_read_disk_snapshot, norm_code, semaphore=misc_semaphore)
    if disk_cached is not None:
        cache.set(cache_key, disk_cached, ttl=VALUATION_DETAIL.ttl_seconds)
        return disk_cached

    hk_val = await hk_market_service.get_stock_valuation(norm_code)
    quotes = await hk_market_service.get_stock_quotes(codes=[norm_code])
    quote = quotes.items[0] if quotes.items else None
    price = quote.price if quote else None

    industry = "港股上市公司"
    peers: list[ValuationPeer] = []
    try:
        from app.financial_data.hk.industry_comparison import get_hk_stock_industry_comparison

        comp = await get_hk_stock_industry_comparison(norm_code)
        if comp.industry_path:
            industry = comp.industry_path
        for p in comp.peers:
            if p.code == norm_code:
                continue
            peers.append(
                ValuationPeer(
                    name=p.name,
                    code=p.code,
                    pe_ttm=p.pe,
                    pb=p.pb,
                    ps_ttm=None,
                )
            )
    except Exception as exc:
        logger.debug("港股行业对比加载跳过: %s", exc)

    peer_summary = _build_peer_summary(
        StockValuation(
            code=norm_code,
            pe_ttm=hk_val.pe_ttm,
            pb=hk_val.pb,
            ps_ttm=hk_val.ps_ttm,
            peers=peers,
        )
    )

    result = ValuationDetail(
        code=norm_code,
        report_date=None,
        current_price=price,
        market_cap=hk_val.market_cap,
        total_shares=hk_val.total_shares,
        industry=industry,
        multiples=ValuationMultiples(
            pe_ttm=hk_val.pe_ttm,
            pb=hk_val.pb,
            ps_ttm=hk_val.ps_ttm,
            peg=None,
        ),
        percentiles=ValuationPercentiles(),
        fundamentals=ValuationFundamentals(),
        peer_summary=peer_summary,
        fair_values={},
        blended_fair_value=None,
        fair_value_range=None,
        valuation_view="港股提供实时行情与估值倍数（PE/PB），已整合行业可比公司",
        valuation_summary="港股估值基于实时行情、披露市值与同行业对比数据计算",
        notes=["港股暂未提供历史估值分位数与DCF模型"],
    )
    cache.set(cache_key, result, ttl=VALUATION_DETAIL.ttl_seconds)
    await call_blocking(_write_disk_snapshot, norm_code, result, semaphore=misc_semaphore)
    return result


async def get_valuation_detail(code: str) -> ValuationDetail:
    """获取详细估值，并合并相同股票的并发缓存未命中请求。"""
    if is_hk_code(code):
        from app.financial_data.hk.service import normalize_hk_code

        norm_code = normalize_hk_code(code)
        cache_key = dated_cache_key("valuation_detail_v9", norm_code)
        cached = cache.get(cache_key)
        if cached is not None:
            cached_hk_get: ValuationDetail = ValuationDetail.model_validate(cached)
            return cached_hk_get
        loaded_hk: ValuationDetail = await _valuation_detail_singleflight.do(
            cache_key, lambda: _load_hk_valuation_detail(norm_code)
        )
        return loaded_hk

    sym = normalize_code(code)
    cache_key = dated_cache_key("valuation_detail_v9", sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        cached_detail: ValuationDetail = ValuationDetail.model_validate(cached)
        return cached_detail
    loaded_detail: ValuationDetail = await _valuation_detail_singleflight.do(
        cache_key, lambda: _load_valuation_detail(code)
    )
    return loaded_detail


async def warm_up_valuation_details(codes: Sequence[str] | None = None) -> dict[str, int]:
    """预热自选与持仓股票的每日估值快照。

    Param:
        codes: 指定待预热的股票代码列表；若为 None 则自动预热用户自选与持仓标的
    Return:
        dict: {"succeeded": 成功数, "failed": 失败数}
    """
    if codes is None:
        targets_set: set[str] = set()
        try:
            from app.infrastructure.persistence import portfolio as portfolio_store
            from app.infrastructure.persistence import watchlist as watchlist_store

            def get_all_codes() -> list[str]:
                res = set()
                try:
                    w_conn = watchlist_store.get_connection()
                    w_rows = w_conn.execute("SELECT DISTINCT stock_code FROM watchlist_items").fetchall()
                    for r in w_rows:
                        if r["stock_code"]:
                            res.add(str(r["stock_code"]).strip())
                except Exception as e:
                    logger.debug("读取自选标的失败: %s", e)

                try:
                    p_conn = portfolio_store.get_connection()
                    p_rows = p_conn.execute("SELECT DISTINCT stock_code FROM portfolio_transactions").fetchall()
                    for r in p_rows:
                        if r["stock_code"]:
                            res.add(str(r["stock_code"]).strip())
                except Exception as e:
                    logger.debug("读取持仓标的失败: %s", e)

                return list(res)

            targets = await call_blocking(get_all_codes, semaphore=database_semaphore)
            targets_set.update(targets)
        except Exception as error:
            logger.warning("获取待预热自选/持仓标的失败: %s", error)
        targets = sorted(targets_set)
    else:
        targets = list(codes)

    succeeded = 0
    failed = 0
    for code in targets:
        try:
            await get_valuation_detail(code)
            succeeded += 1
        except Exception as error:
            failed += 1
            logger.warning("个股估值快照预热失败 code=%s error_type=%s", code, type(error).__name__)
    logger.info("个股估值快照预热完成: succeeded=%s failed=%s total=%s", succeeded, failed, len(targets))
    return {"succeeded": succeeded, "failed": failed}
