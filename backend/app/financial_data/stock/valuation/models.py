"""估值流程内部数据模型。"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class _MultipleMethodContext:
    """Purpose: 倍数法估值方法的目标倍数、依据、置信度与适用性上下文。"""

    target: float | None = None
    basis: str | None = None
    confidence: float = 0.0
    applicability: str = ""
    current_multiple: float | None = None


@dataclass
class _ValuationBases:
    """Purpose: 估值计算共享的盈利、收入、现金流年化与 TTM 基础数据。"""

    net_profit_annualized: float | None = None
    revenue_annualized: float | None = None
    operating_cashflow_annualized: float | None = None
    capital_expenditure_ttm: float | None = None
    net_borrowing_ttm: float | None = None
    net_profit_ttm: float | None = None
    revenue_ttm: float | None = None
    normalized_net_profit: float | None = None
    normalized_revenue: float | None = None
    normalized_roe: float | None = None
    normalized_net_margin: float | None = None
    normalized_basis: str | None = None
    normalized_growth_rate: float | None = None
    normalized_growth_basis: str | None = None
    normalized_growth_quality: float = 0.2
    balance_sheet_quality: float = 0.2
    net_profit_source: str = "unavailable"
    revenue_source: str = "unavailable"
    operating_cashflow_source: str = "unavailable"
    capital_expenditure_source: str = "unavailable"
    net_borrowing_source: str = "unavailable"


@dataclass
class _PegContext:
    """Purpose: PEG 估值方法使用的增长率、依据与当前 PEG 上下文。"""

    growth_rate: float | None = None
    growth_basis: str | None = None
    confidence: float = 0.0
    current_peg: float | None = None


@dataclass
class _WeightedValuationOutputs:
    """Purpose: 加权估值产物（权重、综合公允价值、区间、观点、摘要）。"""

    method_weights: dict[str, float] = field(default_factory=dict)
    blended_fair_value: float | None = None
    fair_value_range: list[float] | None = None
    method_dispersion: float | None = None
    valuation_view: str | None = None
    valuation_summary: str | None = None
