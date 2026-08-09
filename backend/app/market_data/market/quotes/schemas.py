from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MarketVolumeSeriesItem(BaseModel):
    date: str
    volume: float = 0.0
    amount: float = 0.0


class ThsHotStock(BaseModel):
    model_config = ConfigDict(extra="allow")

    rank: int | None = None
    code: str = ""
    name: str = ""
    change_pct: float | None = None
    hot_value: float | None = None
    concept_tag: str = ""
    pop_tag: str = ""


class ThsHotPlate(BaseModel):
    model_config = ConfigDict(extra="allow")

    rank: int | None = None
    code: str = ""
    name: str = ""
    change_pct: float | None = None
    hot_value: float | None = None
    hot_tag: str = ""
    tag: Any = ""


class DragonTigerItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str = ""
    name: str = ""
    trade_date: str = ""
    close: float | None = None
    change_pct: float | None = None
    turnover_pct: float | None = None
    net_amount: float | None = None
    buy_amount: float | None = None
    sell_amount: float | None = None
    deal_amount: float | None = None
    total_amount: float | None = None
    net_amount_rate: float | None = None
    deal_amount_rate: float | None = None
    reason: str = ""
    explain: str = ""
    d1_chg: float | None = None
    d2_chg: float | None = None
    d5_chg: float | None = None

    @field_validator("reason", "explain", mode="before")
    @classmethod
    def normalize_nullable_descriptions(cls, value):
        return value or ""


class DragonTigerDetail(BaseModel):
    side: Literal["buy", "sell"]
    code: str
    operate_name: str
    buy_amount: float | None
    sell_amount: float | None
    net_amount: float | None
    buy_ratio: float | None
    sell_ratio: float | None


class IndustryRankItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    rank: int | None = None
    name: str = ""
    change_pct: float | None = None
    code: str = ""
    up_count: int | None = None
    down_count: int | None = None
    leader: str = ""
    leader_change: float | None = None


class IndustryRankings(BaseModel):
    sectors: list[IndustryRankItem] = Field(default_factory=list)
    total: int = 0


class HsgtFlowPoint(BaseModel):
    time: str
    hgt: float | None = None
    sgt: float | None = None
    total: float | None = None


class HsgtFlowResponse(BaseModel):
    updated_at: str = ""
    unit: str = "亿元"
    points: list[HsgtFlowPoint] = Field(default_factory=list)


class HsgtFlowHistoryItem(BaseModel):
    date: str
    updated_at: str = ""
    points: list[HsgtFlowPoint] = Field(default_factory=list)


class MarketStatistics(BaseModel):
    """Purpose: 市场统计数据，包括板块涨跌榜、涨跌家数、涨停跌停列表和股票涨幅分布。"""
    date: str | None = None
    source: str | None = None

    # 板块涨幅榜
    top_sectors: List[Dict] = Field(default_factory=list)     # 涨幅前5板块
    bottom_sectors: List[Dict] = Field(default_factory=list)  # 跌幅前5板块

    # 涨跌股票榜
    up_count: int = 0                   # 上涨家数
    down_count: int = 0                 # 下跌家数
    flat_count: int = 0                 # 平盘家数
    limit_up_count: int = 0             # 涨停家数
    limit_down_count: int = 0           # 跌停家数
    total_stocks: int = 0               # 总股票数
    limit_up_stocks: List[Dict] = Field(default_factory=list)  # 涨停股票列表
    limit_down_stocks: List[Dict] = Field(default_factory=list)  # 跌停股票列表

    # 股票涨幅分布
    stock_pct_distribution: List[Dict] = Field(default_factory=list)  # 股票涨幅分布
