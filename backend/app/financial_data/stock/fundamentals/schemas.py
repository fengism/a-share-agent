from pydantic import BaseModel, ConfigDict


class FinancialStatementRow(BaseModel):
    """字段由财报类型与上游数据源共同决定的单期财报。"""

    model_config = ConfigDict(extra="allow")


class FinancialMetrics(BaseModel):
    """股票财务指标集合。"""

    code: str
    latest_report_date: str | None = None
    metrics: dict[str, float | None]


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
