from pydantic import BaseModel, Field


class ValuationPeer(BaseModel):
    """Purpose: 估值对比中的同业公司基本信息及估值倍数。"""

    name: str
    code: str
    pe_ttm: float | None = None
    pb: float | None = None
    ps_ttm: float | None = None


class StockValuation(BaseModel):
    """Purpose: 股票当前估值倍数及同行对比。"""

    code: str
    pe_ttm: float | None = None
    pb: float | None = None
    ps_ttm: float | None = None
    peers: list[ValuationPeer] = Field(default_factory=list)


class ValuationMultiples(BaseModel):
    """Purpose: 股票当前的估值倍数（PE/PB/PS/PEG）。"""

    pe_ttm: float | None = None
    pb: float | None = None
    ps_ttm: float | None = None
    peg: float | None = None


class ValuationPercentiles(BaseModel):
    """Purpose: 股票估值倍数在近三年的百分位排名。"""

    pe_3y: float | None = None
    pb_3y: float | None = None
    ps_3y: float | None = None


class ValuationFundamentals(BaseModel):
    """Purpose: 估值分析所引用的基本面财务数据。"""

    revenue: float | None = None
    revenue_yoy: float | None = None
    net_profit: float | None = None
    net_profit_yoy: float | None = None
    non_net_profit: float | None = None
    non_net_profit_yoy: float | None = None
    shareholders_equity: float | None = None
    operating_cashflow: float | None = None


class ValuationProfile(BaseModel):
    """Purpose: 估值画像（分类、标签及适用估值方法的理由）。"""

    category: str
    label: str
    rationale: list[str] = Field(default_factory=list)


class ValuationMethodResult(BaseModel):
    """Purpose: 单种估值方法（相对估值/绝对估值等）的结果。"""

    method: str
    available: bool
    target_multiple: float | None = None
    equity_value: float | None = None
    per_share_value: float | None = None
    upside_pct: float | None = None
    confidence: str | None = None
    confidence_score: float | None = None
    weight: float | None = None
    value_range: list[float] | None = None
    applicability: str | None = None
    basis: str | None = None
    reason: str | None = None


class DCFValuationResult(BaseModel):
    """Purpose: DCF（现金流折现）估值方法的结果。"""

    method: str = "DCF"
    available: bool
    base_cashflow: float | None = None
    discount_rate: float | None = None
    terminal_growth_rate: float | None = None
    forecast_years: int = 5
    equity_value: float | None = None
    per_share_value: float | None = None
    upside_pct: float | None = None
    confidence: str | None = None
    confidence_score: float | None = None
    weight: float | None = None
    value_range: list[float] | None = None
    applicability: str | None = None
    basis: str | None = None
    reason: str | None = None


class InstitutionForecast(BaseModel):
    """Purpose: 机构对某项财务指标的预测统计（最小值/均值/最大值及机构数）。"""

    metric: str
    year: str
    institution_count: float | None = None
    min_value: float | None = None
    mean_value: float | None = None
    max_value: float | None = None
    industry_avg: float | None = None
    unit: str | None = None


class ValuationPeerSummary(BaseModel):
    """Purpose: 同业估值汇总，包括中位数、同业数量和对等公司列表。"""

    pe_median: float | None = None
    pb_median: float | None = None
    ps_median: float | None = None
    peer_count: int = 0
    peers: list[ValuationPeer] = Field(default_factory=list)


class ValuationDetail(BaseModel):
    """Purpose: 估值分析详情，整合估值倍数、百分位、基本面、同业、多种估值方法结果及机构预测。"""

    code: str
    report_date: str | None = None
    current_price: float | None = None
    market_cap: float | None = None
    total_shares: float | None = None
    industry: str | None = None
    multiples: ValuationMultiples
    percentiles: ValuationPercentiles
    fundamentals: ValuationFundamentals
    peer_summary: ValuationPeerSummary
    fair_values: dict[str, ValuationMethodResult | DCFValuationResult]
    blended_fair_value: float | None = None
    fair_value_range: list[float] | None = None
    valuation_view: str | None = None
    valuation_summary: str | None = None
    profile: ValuationProfile | None = None
    method_weights: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    institution_forecasts: list[InstitutionForecast] = Field(default_factory=list)
