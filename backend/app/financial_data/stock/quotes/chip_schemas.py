"""个股筹码分布响应模型。"""

from pydantic import BaseModel, Field


class ChipCostRange(BaseModel):
    """指定比例筹码覆盖的成本区间。"""

    low: float
    high: float


class ChipHistogramItem(BaseModel):
    """单个价格网格上的筹码占比。"""

    price: float
    ratio: float = Field(ge=0, le=1)


class ChipDistribution(BaseModel):
    """基于历史日 K 与换手率在本地估算的筹码分布。"""

    code: str
    as_of_date: str
    source: str = "local"
    price: float
    profit_ratio: float = Field(ge=0, le=1)
    avg_cost: float
    cost_90: ChipCostRange
    cost_70: ChipCostRange
    concentration_90: float | None = None
    concentration_70: float | None = None
    peak_price: float
    histogram: list[ChipHistogramItem] = Field(default_factory=list)
