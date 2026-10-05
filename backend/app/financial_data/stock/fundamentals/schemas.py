from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FinancialStatementRow(BaseModel):
    """字段由财报类型与上游数据源共同决定的单期财报。"""

    model_config = ConfigDict(extra="allow")


class FinancialMetrics(BaseModel):
    """股票财务指标集合。"""

    code: str
    latest_report_date: str | None = None
    metrics: dict[str, float | None]


class RevenueBreakdownItem(BaseModel):
    """单个产品、业务或地区的营收与毛利构成。"""

    id: str | None = None
    class_name: str
    is_sub_item: bool | None = None
    revenue: float | None = None
    cost: float | None = None
    gross_profit: float | None = None
    revenue_share_pct: float | None = None
    gross_margin_pct: float | None = None


class RevenueBreakdown(BaseModel):
    """最新披露口径下的营收与毛利构成；上游不提供报告期。

    A 股来自新浪 ``getGrossRevenue``（金额+占比）；港股来自同花顺 F10 主营构成
    分析，静态页面**只有占比、没有金额**，因此港股的 revenue/cost/gross_profit
    一律为空——不按占比反推金额，那会把编造值当成披露值。
    """

    code: str
    symbol: str
    name: str = ""
    source: Literal["sina", "ths"] = "sina"
    # 同花顺口径的金额单位随公司报表币种而定（人民币/港元都有），无法统一断言，
    # 因此允许为空；A 股仍固定为 CNY_yuan。
    amount_unit: Literal["CNY_yuan"] | None = "CNY_yuan"
    amount_unit_inferred: bool = True
    by_product: list[RevenueBreakdownItem] = Field(default_factory=list)
    by_business: list[RevenueBreakdownItem] = Field(default_factory=list)
    by_region: list[RevenueBreakdownItem] = Field(default_factory=list)


class StockCompareItem(BaseModel):
    code: str
    name: str = ""
    price: float | None = None
    change_pct: float | None = None
    pe_ttm: float | None = None
    pb: float | None = None
    ps_ttm: float | None = None
    market_cap: float | None = None
    turnover_pct: float | None = None
    industry: str | None = None
    revenue: float | None = None
    net_profit: float | None = None
    roe: float | None = None
    info_error: str | None = None
