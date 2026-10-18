from typing import Literal

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
    industry: str | None = None  # 所属行业
    strategies: list[str] = Field(default_factory=list)  # 命中的策略名
    signal_types: list[str] = Field(default_factory=list)  # trend/breakout/reversal 等信号族
    signal_date: str = ""  # 最近一次入场信号日期
    signal_age_days: int | None = None  # 信号距今交易日数
    score: float = 0.0  # 最终评分 = 信号分 + 质量分
    signal_score: float = 0.0  # 策略信号分
    quality_score: float = 0.0  # 技术/估值/行业质量分
    fundamental_score: float = 0.0  # 财务基本面分（ROE/增长/负债/现金流）
    theme_score: float = 0.0  # 热门题材加分
    themes: list[str] = Field(default_factory=list)  # 命中的热门题材/行业
    sector_strength: float | None = None  # 行业当日中位涨幅（%）
    risk_flags: list[str] = Field(default_factory=list)  # 风险提示
    reason: str = ""  # 一句话入选理由


class PotentialDailyResult(BaseModel):
    """一个交易日的潜力股挖掘结果。"""

    date: str
    generated_at: str
    universe_size: int = 0  # 过滤风控后的候选池大小
    evaluated: int = 0  # 实际完成历史数据评估的股票数
    failed_count: int = 0
    market_regime: Literal["bull", "bear", "neutral"] = "neutral"
    market_note: str | None = None  # 市场环境说明
    market_emotion: Literal["strong", "neutral", "weak"] = "neutral"
    advance_ratio: float | None = None  # 上涨家数占比
    limit_up_count: int = 0
    limit_down_count: int = 0
    median_change_pct: float | None = None  # 全市场中位涨幅
    hot_themes: list[str] = Field(default_factory=list)  # 当日热门题材
    items: list[PotentialStockItem] = Field(default_factory=list)


class PotentialDateItem(BaseModel):
    """可用结果日期索引项。"""

    date: str
    count: int = 0


class PotentialPerformanceItem(BaseModel):
    """潜力股单只标的的前瞻表现。"""

    code: str
    name: str
    industry: str | None = None
    entry_price: float | None = None
    exit_price: float | None = None
    return_pct: float | None = None
    benchmark_return_pct: float | None = None
    excess_return_pct: float | None = None
    max_return_pct: float | None = None
    max_drawdown_pct: float | None = None


class PotentialPerformanceSummary(BaseModel):
    """某个挖掘日期在指定持有期内的整体表现。"""

    date: str
    days: int
    generated_at: str
    item_count: int = 0
    evaluated_count: int = 0
    win_rate: float | None = None
    average_return_pct: float | None = None
    median_return_pct: float | None = None
    average_excess_pct: float | None = None
    benchmark_return_pct: float | None = None
    message: str | None = None
    items: list[PotentialPerformanceItem] = Field(default_factory=list)


class PotentialRunStatus(BaseModel):
    """手动触发的潜力股挖掘任务状态（后台异步执行）。"""

    running: bool = False
    status: str = "idle"  # idle / running / completed / failed
    date: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
