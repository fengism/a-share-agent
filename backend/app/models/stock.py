from pydantic import BaseModel


class StockConcept(BaseModel):
    """Purpose: 股票关联的行业/概念（带编码和名称的最小单元）。"""
    code: str
    name: str


class StockConceptInfo(BaseModel):
    """Purpose: 股票的行业/概念信息集合，包含一级和二级行业以及所有关联概念。"""
    concepts: list[StockConcept]
    first_concept: StockConcept | None = None
    second_concept: StockConcept | None = None


class StockSearchItem(BaseModel):
    """Purpose: 股票搜索结果中的单条记录。"""
    code: str
    name: str
    price: float | None = None
    change_pct: float | None = None


class StockBasicInfo(BaseModel):
    """Purpose: 股票的基础信息，包括上市信息、股本、估值指标、行业分类和当前价格。"""
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
    """Purpose: 单根 K 线（蜡烛图）的行情数据。"""
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
    """Purpose: 股票的 K 线数据集，包含股票代码、周期、复权方式和 K 线列表。"""
    code: str
    period: str
    adjust: str
    items: list[KlineItem]


class IntradayItem(BaseModel):
    """Purpose: 单条分时行情数据点。"""
    time: str
    price: float
    avg_price: float | None = None
    volume: float | None = None
    amount: float | None = None
    change_pct: float | None = None


class IntradayData(BaseModel):
    """Purpose: 股票分时行情数据集，包含前收价和分时点列表。"""
    code: str
    prev_close: float | None = None
    items: list[IntradayItem]


class FinancialMetrics(BaseModel):
    """Purpose: 股票财务指标集合，以字典形式存储各类指标值。"""
    code: str
    latest_report_date: str | None = None
    metrics: dict[str, float | None]


class ValuationPeer(BaseModel):
    """Purpose: 估值对比中的同业公司基本信息及估值倍数。"""
    name: str
    code: str
    pe_ttm: float | None = None
    pb: float | None = None
    ps_ttm: float | None = None


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
    rationale: list[str] = []


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
    peers: list[ValuationPeer] = []


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
    method_weights: dict[str, float] = {}
    notes: list[str] = []
    institution_forecasts: list[InstitutionForecast] = []
