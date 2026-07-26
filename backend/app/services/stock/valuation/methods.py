import logging

import pandas as pd

from app.models.stock import DCFValuationResult, InstitutionForecast, StockBasicInfo, ValuationDetail, ValuationFundamentals, ValuationMethodResult, ValuationMultiples, ValuationPeer, ValuationPeerSummary, ValuationPercentiles, ValuationProfile
from app.services.providers import get_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking, akshare_semaphore, ths_semaphore
from app.utils.data_clean import safe_float

logger = logging.getLogger(__name__)

from datetime import datetime
from app.utils.symbol_utils import normalize_code

from app.services.stock.valuation.helpers import (
    _confidence_text,
    _current_peg,
    _normalize_growth_rate,
    _value_range,
)
from app.services.stock.valuation.profile import (
    _cap_peg_target_pe,
    _target_peg_by_profile,
)

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

