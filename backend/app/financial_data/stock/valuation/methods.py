import logging
import math

from app.financial_data.stock.valuation.helpers import (
    _confidence_text,
    _current_peg,
    _value_range,
)
from app.financial_data.stock.valuation.profile import (
    _cap_peg_target_pe,
    _target_peg_by_profile,
)
from app.financial_data.stock.valuation.schemas import (
    DCFScenario,
    DCFSensitivityPoint,
    DCFValuationResult,
    ReverseDCFResult,
    ValuationMethodResult,
    ValuationProfile,
)

logger = logging.getLogger(__name__)


def _build_multiple_valuation(
    method: str,
    basis_metric: float | None,
    target_multiple: float | None,
    current_price: float | None,
    total_shares: float | None,
    basis: str,
    confidence_score: float,
    applicability: str,
    data_quality_score: float = 1.0,
) -> ValuationMethodResult:
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
    confidence_score = max(0.0, min(confidence_score, 1.0)) if math.isfinite(confidence_score) else 0.0
    data_quality_score = max(0.0, min(data_quality_score, 1.0)) if math.isfinite(data_quality_score) else 0.0
    confidence = _confidence_text(confidence_score)
    if basis_metric is None or not math.isfinite(basis_metric) or basis_metric <= 0:
        return ValuationMethodResult(
            method=method,
            available=False,
            reason="基础指标不可用",
            basis=basis,
            confidence=confidence,
            confidence_score=confidence_score,
            data_quality_score=data_quality_score,
            applicability=applicability,
        )
    if target_multiple is None or not math.isfinite(target_multiple) or target_multiple <= 0:
        return ValuationMethodResult(
            method=method,
            available=False,
            reason="缺少有效的目标倍数",
            basis=basis,
            confidence=confidence,
            confidence_score=confidence_score,
            data_quality_score=data_quality_score,
            applicability=applicability,
        )
    if total_shares is None or not math.isfinite(total_shares) or total_shares <= 0:
        return ValuationMethodResult(
            method=method,
            available=False,
            reason="总股本不可用",
            basis=basis,
            confidence=confidence,
            confidence_score=confidence_score,
            data_quality_score=data_quality_score,
            applicability=applicability,
        )

    equity_value = round(target_multiple * basis_metric, 2)
    per_share_value = round(equity_value / total_shares, 2)
    if (
        not math.isfinite(equity_value)
        or equity_value <= 0
        or not math.isfinite(per_share_value)
        or per_share_value <= 0
    ):
        return ValuationMethodResult(
            method=method,
            available=False,
            reason="估值计算结果不可用",
            basis=basis,
            confidence=confidence,
            confidence_score=confidence_score,
            data_quality_score=data_quality_score,
            applicability=applicability,
        )
    has_valid_current_price = current_price is not None and math.isfinite(current_price) and current_price > 0
    upside_pct = (per_share_value - current_price) / current_price * 100 if has_valid_current_price else None
    upside_pct = round(upside_pct, 2) if upside_pct is not None and math.isfinite(upside_pct) else None
    return ValuationMethodResult(
        method=method,
        available=True,
        target_multiple=round(target_multiple, 4),
        equity_value=equity_value,
        per_share_value=per_share_value,
        upside_pct=upside_pct,
        confidence=confidence,
        confidence_score=confidence_score,
        data_quality_score=data_quality_score,
        value_range=_value_range(per_share_value, confidence_score),
        applicability=applicability,
        basis=basis,
    )


def _build_peg_valuation(
    net_profit_ttm: float | None,
    current_pe: float | None,
    peer_pe_median: float | None,
    growth_rate: float | None,
    growth_basis: str | None,
    current_price: float | None,
    total_shares: float | None,
    profile: ValuationProfile,
    confidence_score: float,
    data_quality_score: float = 1.0,
) -> ValuationMethodResult:
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
        return ValuationMethodResult(
            method="PEG",
            available=False,
            reason="亏损或盈利承压，PEG 不适用",
            basis="；".join(basis_parts),
            confidence="low",
            confidence_score=0.2,
            data_quality_score=data_quality_score,
            applicability=applicability,
        )
    if growth_rate is None:
        return ValuationMethodResult(
            method="PEG",
            available=False,
            reason="成长率过低或不可用",
            basis="；".join(basis_parts),
            confidence="low",
            confidence_score=confidence_score,
            data_quality_score=data_quality_score,
            applicability=applicability,
        )
    if target_peg is None:
        return ValuationMethodResult(
            method="PEG",
            available=False,
            reason="股票画像不适用 PEG",
            basis="；".join(basis_parts),
            confidence="low",
            confidence_score=confidence_score,
            data_quality_score=data_quality_score,
            applicability=applicability,
        )

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
        data_quality_score,
    )


def _normalize_dcf_growth(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    rate = value / 100
    return max(-0.10, min(rate, 0.20))


def _project_dcf(
    base_cashflow: float,
    growth_rate: float,
    discount_rate: float,
    terminal_growth_rate: float,
    forecast_years: int = 5,
) -> float:
    assumptions = (
        base_cashflow,
        growth_rate,
        discount_rate,
        terminal_growth_rate,
    )
    if not all(math.isfinite(value) for value in assumptions):
        raise ValueError("DCF assumptions must be finite")
    if base_cashflow <= 0:
        raise ValueError("base cashflow must be positive")
    if forecast_years <= 0:
        raise ValueError("forecast years must be positive")
    if growth_rate <= -1 or terminal_growth_rate <= -1:
        raise ValueError("growth rates must be greater than -100%")
    if discount_rate <= -1 or discount_rate <= terminal_growth_rate:
        raise ValueError("discount rate must exceed terminal growth rate")

    cashflow = base_cashflow
    discounted_sum = 0.0
    for year in range(1, forecast_years + 1):
        fade_weight = min(1.0, max(0.0, (year - 1) / max(forecast_years - 1, 1)))
        annual_growth = growth_rate + (terminal_growth_rate - growth_rate) * fade_weight
        cashflow *= 1 + annual_growth
        discount_factor = (1 + discount_rate) ** year
        discounted_cashflow = cashflow / discount_factor
        if not all(math.isfinite(value) for value in (annual_growth, cashflow, discount_factor, discounted_cashflow)):
            raise ValueError("DCF projection overflowed")
        discounted_sum += discounted_cashflow
        if not math.isfinite(discounted_sum):
            raise ValueError("DCF projection overflowed")
    terminal_value = cashflow * (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
    result = discounted_sum + terminal_value / ((1 + discount_rate) ** forecast_years)
    if not math.isfinite(terminal_value) or not math.isfinite(result):
        raise ValueError("DCF projection overflowed")
    return result


def _reverse_dcf(
    base_cashflow: float,
    current_price: float | None,
    total_shares: float,
    discount_rate: float,
    terminal_growth_rate: float,
) -> ReverseDCFResult:
    if current_price is None or not math.isfinite(current_price) or current_price <= 0:
        return ReverseDCFResult(available=False, reason="当前股价不可用")

    if not math.isfinite(total_shares) or total_shares <= 0:
        return ReverseDCFResult(available=False, reason="总股本不可用")
    market_equity_value = current_price * total_shares
    if not math.isfinite(market_equity_value):
        return ReverseDCFResult(available=False, reason="当前市值不可用")
    low, high = -0.50, 0.50
    try:
        low_value = _project_dcf(base_cashflow, low, discount_rate, terminal_growth_rate)
        high_value = _project_dcf(base_cashflow, high, discount_rate, terminal_growth_rate)
    except ValueError:
        return ReverseDCFResult(
            available=False,
            market_equity_value=round(market_equity_value, 2),
            reason="DCF 计算结果不可用",
        )
    if not low_value <= market_equity_value <= high_value:
        return ReverseDCFResult(
            available=False,
            market_equity_value=round(market_equity_value, 2),
            reason="当前市值超出可反推增长率范围",
        )

    for _ in range(60):
        midpoint = (low + high) / 2
        try:
            value = _project_dcf(
                base_cashflow,
                midpoint,
                discount_rate,
                terminal_growth_rate,
            )
        except ValueError:
            return ReverseDCFResult(
                available=False,
                market_equity_value=round(market_equity_value, 2),
                reason="DCF 计算结果不可用",
            )
        if value < market_equity_value:
            low = midpoint
        else:
            high = midpoint
    return ReverseDCFResult(
        available=True,
        implied_growth_rate=round((low + high) / 2, 6),
        market_equity_value=round(market_equity_value, 2),
    )


def _build_dcf_valuation(
    operating_cashflow: float | None,
    net_profit: float | None,
    revenue_yoy: float | None,
    net_profit_yoy: float | None,
    current_price: float | None,
    total_shares: float | None,
    capital_expenditure: float | None = None,
    net_borrowing: float | None = None,
    normalized_growth_rate: float | None = None,
    growth_basis: str | None = None,
    data_quality_score: float = 0.5,
) -> DCFValuationResult:
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
    base_cashflow: float | None = None
    basis: str | None = None
    fcfe_source: str | None = None
    confidence_score = 0.45
    data_quality_score = max(0.0, min(data_quality_score, 1.0)) if math.isfinite(data_quality_score) else 0.0
    applicability = "DCF 对现金流假设敏感，仅作为区间参考"
    if operating_cashflow is not None and math.isfinite(operating_cashflow) and operating_cashflow > 0:
        if capital_expenditure is not None and math.isfinite(capital_expenditure) and capital_expenditure >= 0:
            base_cashflow = operating_cashflow - abs(capital_expenditure)
            if net_borrowing is not None and math.isfinite(net_borrowing):
                base_cashflow += net_borrowing
                basis = "FCFE 采用经营现金流减资本开支加净借款"
                fcfe_source = "经营现金流减资本开支加净借款"
                confidence_score = 0.8
            else:
                basis = "净借款缺失，FCFE 暂采用经营现金流减资本开支"
                fcfe_source = "经营现金流减资本开支"
                confidence_score = 0.65
                data_quality_score *= 0.85
        else:
            base_cashflow = operating_cashflow * 0.75
            basis = "缺少资本开支，经营现金流折减 25% 近似 FCFE"
            fcfe_source = "经营现金流保守代理"
            confidence_score = 0.55
    elif net_profit is not None and math.isfinite(net_profit) and net_profit > 0:
        base_cashflow = net_profit * 0.75
        basis = "净利润折减 25% 近似 FCFE"
        fcfe_source = "净利润保守代理"

    if base_cashflow is None or not math.isfinite(base_cashflow) or base_cashflow <= 0:
        return DCFValuationResult(
            available=False,
            reason="缺少可用现金流基础",
            basis=basis,
            fcfe_source=fcfe_source,
            confidence="low",
            confidence_score=confidence_score,
            data_quality_score=data_quality_score,
            applicability=applicability,
        )
    if total_shares is None or not math.isfinite(total_shares) or total_shares <= 0:
        return DCFValuationResult(
            available=False,
            reason="总股本不可用",
            basis=basis,
            fcfe_source=fcfe_source,
            confidence="low",
            confidence_score=confidence_score,
            data_quality_score=data_quality_score,
            applicability=applicability,
        )

    discount_rate = 0.10 + (1 - data_quality_score) * 0.02
    terminal_growth_rate = 0.03
    if normalized_growth_rate is not None and math.isfinite(normalized_growth_rate):
        growth_rate = normalized_growth_rate
    else:
        growth_inputs = [
            rate for value in (revenue_yoy, net_profit_yoy) if (rate := _normalize_dcf_growth(value)) is not None
        ]
        growth_rate = sum(growth_inputs) / len(growth_inputs) if growth_inputs else 0.03
    growth_rate = max(-0.05, min(growth_rate, 0.15))
    if growth_basis:
        basis = f"{basis}；增长假设：{growth_basis}"
    forecast_years = 5

    scenario_inputs = (
        ("bear", "悲观", max(-0.08, growth_rate - 0.04), discount_rate + 0.02, 0.02),
        ("base", "基准", growth_rate, discount_rate, terminal_growth_rate),
        ("bull", "乐观", min(0.20, growth_rate + 0.03), max(0.07, discount_rate - 0.01), 0.035),
    )
    scenarios = []
    has_valid_current_price = current_price is not None and math.isfinite(current_price) and current_price > 0
    try:
        for name, label, scenario_growth, scenario_discount, scenario_terminal in scenario_inputs:
            equity_value = _project_dcf(
                base_cashflow,
                scenario_growth,
                scenario_discount,
                scenario_terminal,
                forecast_years,
            )
            per_share_value = equity_value / total_shares
            if not math.isfinite(per_share_value) or per_share_value <= 0:
                raise ValueError("DCF per-share value is invalid")
            upside_pct = (per_share_value - current_price) / current_price * 100 if has_valid_current_price else None
            scenarios.append(
                DCFScenario(
                    name=name,
                    label=label,
                    growth_rate=round(scenario_growth, 6),
                    discount_rate=round(scenario_discount, 6),
                    terminal_growth_rate=scenario_terminal,
                    equity_value=round(equity_value, 2),
                    per_share_value=round(per_share_value, 2),
                    upside_pct=(round(upside_pct, 2) if upside_pct is not None and math.isfinite(upside_pct) else None),
                )
            )

        base_scenario = scenarios[1]
        sensitivity = []
        for sensitivity_discount in (
            discount_rate - 0.01,
            discount_rate,
            discount_rate + 0.01,
        ):
            for sensitivity_terminal in (
                terminal_growth_rate - 0.005,
                terminal_growth_rate,
                terminal_growth_rate + 0.005,
            ):
                sensitivity_value = (
                    _project_dcf(
                        base_cashflow,
                        growth_rate,
                        sensitivity_discount,
                        sensitivity_terminal,
                        forecast_years,
                    )
                    / total_shares
                )
                if not math.isfinite(sensitivity_value) or sensitivity_value <= 0:
                    raise ValueError("DCF sensitivity value is invalid")
                sensitivity.append(
                    DCFSensitivityPoint(
                        discount_rate=round(sensitivity_discount, 6),
                        terminal_growth_rate=round(sensitivity_terminal, 6),
                        per_share_value=round(sensitivity_value, 2),
                    )
                )
        reverse_dcf = _reverse_dcf(
            base_cashflow,
            current_price,
            total_shares,
            discount_rate,
            terminal_growth_rate,
        )
    except (OverflowError, ValueError):
        return DCFValuationResult(
            available=False,
            reason="DCF 计算结果不可用",
            basis=basis,
            fcfe_source=fcfe_source,
            confidence="low",
            confidence_score=confidence_score,
            data_quality_score=data_quality_score,
            applicability=applicability,
        )
    return DCFValuationResult(
        available=True,
        base_cashflow=round(base_cashflow, 2),
        discount_rate=round(discount_rate, 6),
        terminal_growth_rate=terminal_growth_rate,
        forecast_years=forecast_years,
        equity_value=base_scenario.equity_value,
        per_share_value=base_scenario.per_share_value,
        upside_pct=base_scenario.upside_pct,
        confidence=_confidence_text(confidence_score),
        confidence_score=confidence_score,
        data_quality_score=data_quality_score,
        value_range=[
            min(scenario.per_share_value for scenario in scenarios),
            max(scenario.per_share_value for scenario in scenarios),
        ],
        applicability=applicability,
        basis=basis,
        fcfe_source=fcfe_source,
        scenarios=scenarios,
        sensitivity=sensitivity,
        reverse_dcf=reverse_dcf,
    )
