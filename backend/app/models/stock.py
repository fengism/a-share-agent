from pydantic import BaseModel


class StockConcept(BaseModel):
    code: str
    name: str


class StockConceptInfo(BaseModel):
    concepts: list[StockConcept]
    first_concept: StockConcept | None = None
    second_concept: StockConcept | None = None


class StockSearchItem(BaseModel):
    code: str
    name: str
    price: float | None = None
    change_pct: float | None = None


class StockBasicInfo(BaseModel):
    code: str
    name: str
    listing_date: str | None = None  # 上市日期
    total_shares: float | None = None  # 总股单位：股
    circulating_shares: float | None = None  # 流通股单位：股
    pe_ttm: float | None = None  # PE 值
    pe_static: float | None = None  # 静态PE
    pb: float | None = None  # PB 值
    market_cap: float | None = None  # 市值单位：元
    float_market_cap: float | None = None  # 流通市值单位：元
    turnover_pct: float | None = None  # 换手率：%
    first_industry: StockConcept | None = None  # 第一级行业分类
    second_industry: StockConcept | None = None  # 第二级行业分类
    current_price: float | None = None  # 当前价格
    concepts: list[StockConcept] | None = None  # 概念
    

class KlineItem(BaseModel):
    code: str = ""
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: float
    amount: float
    amplitude: float | None = None
    turnover_pct: float | None = None
    change_pct: float | None = None
    pre_close: float | None = None


class KlineData(BaseModel):
    code: str
    period: str
    adjust: str
    items: list[KlineItem]


class IntradayItem(BaseModel):
    time: str
    price: float
    avg_price: float | None = None
    volume: float | None = None
    amount: float | None = None
    change_pct: float | None = None


class IntradayData(BaseModel):
    code: str
    prev_close: float | None = None
    items: list[IntradayItem]


class FinancialMetrics(BaseModel):
    code: str
    latest_report_date: str | None = None
    metrics: dict[str, float | None]


class ValuationPeer(BaseModel):
    name: str
    code: str
    pe_ttm: float | None = None
    pb: float | None = None
    ps_ttm: float | None = None


class ValuationMultiples(BaseModel):
    pe_ttm: float | None = None
    pb: float | None = None
    ps_ttm: float | None = None
    peg: float | None = None


class ValuationPercentiles(BaseModel):
    pe_3y: float | None = None
    pb_3y: float | None = None
    ps_3y: float | None = None


class ValuationFundamentals(BaseModel):
    revenue: float | None = None
    revenue_yoy: float | None = None
    net_profit: float | None = None
    net_profit_yoy: float | None = None
    non_net_profit: float | None = None
    non_net_profit_yoy: float | None = None
    shareholders_equity: float | None = None
    operating_cashflow: float | None = None


class ValuationProfile(BaseModel):
    category: str
    label: str
    rationale: list[str] = []


class ValuationMethodResult(BaseModel):
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
    metric: str
    year: str
    institution_count: float | None = None
    min_value: float | None = None
    mean_value: float | None = None
    max_value: float | None = None
    industry_avg: float | None = None
    unit: str | None = None


class ValuationPeerSummary(BaseModel):
    pe_median: float | None = None
    pb_median: float | None = None
    ps_median: float | None = None
    peer_count: int = 0
    peers: list[ValuationPeer] = []


class ValuationDetail(BaseModel):
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
    method_weights: dict[str, float] = {}
    notes: list[str] = []
    institution_forecasts: list[InstitutionForecast] = []
