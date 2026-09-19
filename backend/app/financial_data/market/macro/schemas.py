from typing import TypeAlias

from pydantic import BaseModel, Field

MacroValue: TypeAlias = str | int | float | None


class MacroIndicator(BaseModel):
    latest: dict[str, MacroValue] | None = None
    trend: list[dict[str, MacroValue]] = Field(default_factory=list)
    source: str | None = None
    source_api: str | None = None
    latest_period: str | None = None
    is_fallback: bool = False
    is_stale: bool = False
    field_periods: dict[str, str] = Field(default_factory=dict)
    stale_fields: list[str] = Field(default_factory=list)


class MacroAllDataResponse(BaseModel):
    prices: dict[str, MacroIndicator] = Field(default_factory=dict)
    sentiment: dict[str, MacroIndicator] = Field(default_factory=dict)
    monetary: dict[str, MacroIndicator] = Field(default_factory=dict)
    rates: dict[str, MacroIndicator] = Field(default_factory=dict)
    growth: dict[str, MacroIndicator] = Field(default_factory=dict)
    trade: dict[str, MacroIndicator] = Field(default_factory=dict)


class MacroUsDataResponse(BaseModel):
    indicators: dict[str, MacroIndicator] = Field(default_factory=dict)
    updated_at: str | None = None
    refreshing: bool = False
    failed_indicators: dict[str, str] = Field(default_factory=dict)


class TreasuryYieldPoint(BaseModel):
    date: str = ""
    cn_2y: float | None = None
    cn_5y: float | None = None
    cn_10y: float | None = None
    cn_30y: float | None = None
    cn_10y_2y: float | None = None
    cn_gdp_growth: float | None = None
    us_2y: float | None = None
    us_5y: float | None = None
    us_10y: float | None = None
    us_30y: float | None = None
    us_10y_2y: float | None = None
    us_gdp_growth: float | None = None
    spread_10y: float | None = None
    spread_2y: float | None = None


class TreasuryTermStructure(BaseModel):
    tenor: str
    cn_yield: float | None = None
    us_yield: float | None = None
    spread: float | None = None


class TreasuryLatest(BaseModel):
    date: str = ""
    china_date: str = ""
    us_date: str = ""
    china_10y_yield: float | None = None
    china_2y_yield: float | None = None
    china_5y_yield: float | None = None
    china_30y_yield: float | None = None
    china_10y_2y_spread: float | None = None
    us_10y_yield: float | None = None
    us_2y_yield: float | None = None
    us_5y_yield: float | None = None
    us_30y_yield: float | None = None
    us_10y_2y_spread: float | None = None
    us_china_10y_spread: float | None = None
    us_china_spread_status: str = ""
    us_yield_curve_status: str = ""


class TreasuryCurve(BaseModel):
    history: list[TreasuryYieldPoint] = Field(default_factory=list)
    term_structure: list[TreasuryTermStructure] = Field(default_factory=list)
    total_count: int = 0


class TreasuryYieldsResponse(TreasuryCurve):
    latest: TreasuryLatest = Field(default_factory=TreasuryLatest)


class FxQuote(BaseModel):
    name: str
    code: str
    value: float | None = None
    change: float | None = None
    change_pct: float | None = None


class DollarAndFx(BaseModel):
    dxy: FxQuote | None = None
    usd_cnh: FxQuote | None = None
    usd_cny: FxQuote | None = None


class CentralBankPolicyRates(BaseModel):
    china_lpr_1y: str
    china_lpr_5y: str
    us_fed_funds_rate: str


class MarketImplications(BaseModel):
    us_10y_impact: str
    us_china_spread_impact: str
    dxy_cnh_impact: str


class CrudeOilQuote(BaseModel):
    symbol: str
    name: str
    price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    unit: str = ""
    date: str = ""


class CrudeOilHistoryPoint(BaseModel):
    date: str
    sc_close: float | None = None
    wti_close: float | None = None
    brent_close: float | None = None


class CrudeOilData(BaseModel):
    sc0: CrudeOilQuote | None = None
    wti: CrudeOilQuote | None = None
    brent: CrudeOilQuote | None = None
    history: list[CrudeOilHistoryPoint] = Field(default_factory=list)


class GlobalMacroRatesResponse(BaseModel):
    timestamp: str
    dollar_and_fx: DollarAndFx = Field(default_factory=DollarAndFx)
    treasury_yields_and_spreads: TreasuryLatest = Field(default_factory=TreasuryLatest)
    treasury_curve: TreasuryCurve = Field(default_factory=TreasuryCurve)
    central_bank_policy_rates: CentralBankPolicyRates
    market_implications: MarketImplications
    crude_oil: CrudeOilData | None = None


class CommodityItem(BaseModel):
    symbol: str
    name: str
    contract: str
    category: str
    unit: str
    latest_price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    high: float | None = None
    low: float | None = None
    open: float | None = None
    prev_settle: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    date: str | None = None
    description: str
    related_chains: list[str] = Field(default_factory=list)


class CommoditiesResponse(BaseModel):
    query: str
    total_count: int
    items: list[CommodityItem] = Field(default_factory=list)


class CustomsMonthSummary(BaseModel):
    """海关进出口月度总况（金额单位：亿美元）。"""

    month: str = ""
    report_date: str = ""
    export_val: float = Field(default=0, description="当月出口金额（亿美元）")
    import_val: float = Field(default=0, description="当月进口金额（亿美元）")
    trade_balance: float = Field(default=0, description="当月贸易差额（亿美元，出口-进口）")
    balance_status: str = ""
    export_yoy_pct: float = Field(default=0, description="当月出口同比（%）")
    import_yoy_pct: float = Field(default=0, description="当月进口同比（%）")
    export_accumulate: float = Field(default=0, description="累计出口金额（亿美元）")
    import_accumulate: float = Field(default=0, description="累计进口金额（亿美元）")
    export_accumulate_yoy_pct: float = Field(default=0, description="累计出口同比（%）")
    import_accumulate_yoy_pct: float = Field(default=0, description="累计进口同比（%）")


class CustomsCommodityProfile(BaseModel):
    category: str
    commodity: str
    trade_type: str
    unit: str
    description: str
    key_target_markets: str
    related_a_stocks: list[str] = Field(default_factory=list)
    industry_chains: list[str] = Field(default_factory=list)


class CustomsInvestmentImplications(BaseModel):
    export_driver: str
    substitute_driver: str


class CustomsTradeDataResponse(BaseModel):
    query: str
    latest_month_summary: CustomsMonthSummary = Field(default_factory=CustomsMonthSummary)
    recent_12m_macro_trend: list[CustomsMonthSummary] = Field(default_factory=list)
    matched_commodity_profiles: list[CustomsCommodityProfile] = Field(default_factory=list)
    investment_implications: CustomsInvestmentImplications


class SgeGoldHistoryPoint(BaseModel):
    date: str
    open: float
    close: float
    low: float
    high: float
    change: float | None = None
    change_pct: float | None = None


class SgeGoldResponse(BaseModel):
    symbol: str
    name: str
    unit: str
    source: str
    latest: SgeGoldHistoryPoint | None = None
    history: list[SgeGoldHistoryPoint] = Field(default_factory=list)
    updated_at: str
    is_stale: bool = False
