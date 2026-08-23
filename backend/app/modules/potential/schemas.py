from pydantic import BaseModel, Field


class PotentialStockItem(BaseModel):
    """每日潜力股挖掘结果中的单只股票。"""

    code: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    market_cap: float | None = None  # 亿元
    turnover_pct: float | None = None
    amount: float | None = None  # 亿元
    strategies: list[str] = Field(default_factory=list)  # 命中的策略名
    signal_date: str = ""  # 最近一次入场信号日期
    signal_age_days: int | None = None  # 信号距今交易日数
    score: float = 0.0


class PotentialDailyResult(BaseModel):
    """一个交易日的潜力股挖掘结果。"""

    date: str
    generated_at: str
    universe_size: int = 0  # 过滤风控后的候选池大小
    evaluated: int = 0  # 实际完成历史数据评估的股票数
    failed_count: int = 0
    items: list[PotentialStockItem] = Field(default_factory=list)


class PotentialDateItem(BaseModel):
    """可用结果日期索引项。"""

    date: str
    count: int = 0
