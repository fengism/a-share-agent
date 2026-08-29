import asyncio
import logging
import math
from datetime import date

from app.core.cache import cache, dated_cache_key
from app.core.concurrency.rate_limiter import call_blocking, ths_semaphore
from app.core.market import normalize_code, safe_float
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
)
from app.financial_data.stock.valuation.helpers import (
    _annualize_report_metric,
    _current_peg,
    _derive_normalized_dcf_growth,
    _derive_ttm_basis,
    _derive_ttm_report_metric,
    _fallback_target_multiple,
    _get_ths_provider,
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
    ValuationPeerSummary,
    ValuationPercentiles,
    ValuationProfile,
)
from app.infrastructure.providers.provider_gateway import provider_gateway

logger = logging.getLogger(__name__)


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
]:
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
        get_financial(code, "profit"),
        get_financial(code, "cashflow"),
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
        pe_3y=None if isinstance(pe_percentile, Exception) else pe_percentile,
        pb_3y=None if isinstance(pb_percentile, Exception) else pb_percentile,
        ps_3y=None if isinstance(ps_percentile, Exception) else ps_percentile,
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


def _derive_current_price(basic_info: StockBasicInfo) -> float | None:
    """通过市值和总股本反推当前股价。

    Param:
        basic_info: 股票基本信息
    Return:
        当前股价，数据缺失时返回 None
    """
    market_cap = basic_info.market_cap
    total_shares = basic_info.total_shares
    if (
        market_cap is None
        or not math.isfinite(market_cap)
        or market_cap <= 0
        or total_shares is None
        or not math.isfinite(total_shares)
        or total_shares <= 0
    ):
        return None
    current_price = market_cap / total_shares
    return round(current_price, 2) if math.isfinite(current_price) else None


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


def _build_multiple_method_contexts(
    valuation_data: StockValuation,
    percentiles: ValuationPercentiles,
    peer_summary: ValuationPeerSummary,
    profile: ValuationProfile,
    roe: float | None,
) -> dict[str, _MultipleMethodContext]:
    """组装 PE/PB/PS 倍数法上下文，按画像与 ROE 调整置信度。

    Param:
        valuation_data: 估值数据模型
        percentiles: 估值百分位
        peer_summary: 同行汇总
        profile: 估值画像
        roe: ROE 值
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
    )
    revenue_ttm, revenue_source = _derive_ttm_report_metric(
        profit_rows,
        ("TOTAL_OPERATE_INCOME", "OPERATE_INCOME", "TOTAL_REVENUE"),
        report_date,
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
        age_days = (date.today() - parsed_report_date).days
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
        "annualized_fallback": 0.55,
        "market_implied": 0.45,
    }.get(source, 0.2)


def _build_data_quality(
    bases: _ValuationBases,
    peer_summary: ValuationPeerSummary,
) -> ValuationDataQuality:
    peer_confidence = (
        sum(
            (
                peer_summary.pe_stats.confidence_score,
                peer_summary.pb_stats.confidence_score,
                peer_summary.ps_stats.confidence_score,
            )
        )
        / 3
    )
    ttm_quality = (_source_quality(bases.net_profit_source) + _source_quality(bases.revenue_source)) / 2
    cashflow_quality = (
        _source_quality(bases.operating_cashflow_source) + _source_quality(bases.capital_expenditure_source)
    ) / 2
    score = round(0.45 * ttm_quality + 0.30 * cashflow_quality + 0.25 * peer_confidence, 4)
    limitations = []
    disclosed_sources = {"reported_ttm", "reported_annual"}
    if bases.net_profit_source not in disclosed_sources:
        limitations.append("净利润未使用完整披露 TTM，估值基础可靠性下降。")
    if bases.revenue_source not in disclosed_sources:
        limitations.append("营业收入未使用完整披露 TTM，PS 估值仅供参考。")
    if bases.capital_expenditure_ttm is None:
        limitations.append("资本开支缺失，DCF 使用保守现金流代理。")
    if (
        min(
            peer_summary.pe_stats.sample_size,
            peer_summary.pb_stats.sample_size,
            peer_summary.ps_stats.sample_size,
        )
        < 3
    ):
        limitations.append("有效同行样本偏少，相对估值置信度有限。")
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
    valuation_view = _build_valuation_view(fair_value_range, blended_fair_value, current_price)
    return _WeightedValuationOutputs(
        method_weights=method_weights,
        blended_fair_value=blended_fair_value,
        fair_value_range=fair_value_range,
        valuation_view=valuation_view,
        valuation_summary=_build_valuation_summary(profile, fair_value_range, valuation_view),
    )


async def get_valuation_detail(code: str) -> ValuationDetail:
    """汇总多估值方法的详细结果，带 1 天缓存。

    Param:
        code: 股票代码
    Return:
        ValuationDetail 模型对象，含画像、各方法结果与综合估值
    """
    sym = normalize_code(code)
    cache_key = dated_cache_key("valuation_detail_v4", sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    (
        basic_info,
        valuation_data,
        financial_metrics,
        institution_forecasts,
        profit_rows,
        cashflow_rows,
    ) = await _fetch_valuation_detail_inputs(code, sym.raw)
    percentiles = await _fetch_valuation_percentiles(sym.raw)
    peer_summary = _build_peer_summary(valuation_data)
    fundamentals = _build_fundamentals(financial_metrics)
    current_price = _derive_current_price(basic_info)
    profile = _classify_stock_profile(basic_info, fundamentals)
    contexts = _build_multiple_method_contexts(
        valuation_data, percentiles, peer_summary, profile, _calc_roe(fundamentals)
    )
    bases = _derive_valuation_bases(
        fundamentals,
        financial_metrics.latest_report_date,
        basic_info.market_cap,
        valuation_data,
        profit_rows,
        cashflow_rows,
    )
    fundamentals.capital_expenditure = bases.capital_expenditure_ttm
    data_quality = _build_data_quality(bases, peer_summary)
    peg_context = _derive_peg_context(
        institution_forecasts,
        bases.net_profit_ttm,
        basic_info.total_shares,
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
        basic_info.total_shares,
        data_quality,
    )
    weighted_outputs = _build_weighted_outputs(fair_values, profile, current_price)

    result = ValuationDetail(
        code=sym.raw,
        report_date=financial_metrics.latest_report_date,
        current_price=current_price,
        market_cap=basic_info.market_cap,
        total_shares=basic_info.total_shares,
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
    cache.set(cache_key, result, ttl=86400)
    return result
