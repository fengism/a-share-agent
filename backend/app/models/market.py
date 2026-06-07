from typing import Dict, List

from pydantic import BaseModel, Field



class IndexItem(BaseModel):
    """Purpose: 单个市场指数的行情数据项。"""
    code: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    amount: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    amplitude: float | None = None
    pre_close: float | None = None


class MarketIndices(BaseModel):
    """Purpose: 市场概览数据，包含日期、各指数行情及数据来源和两市总成交额。"""
    date: str | None = None
    indices: list[IndexItem]
    source: str | None = None
    total_amount: float = 0.0           # 两市成交额（亿元）

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


class MarketVolume(BaseModel):
    """Purpose: 市场成交额数据，包含当日、前一日和60日均值。"""
    date: str | None = None
    amount: float | None = None
    amount_before_one_day: float | None = None
    amount_average_60_day: float | None = None

    def to_str(self):
        """Format market volume summary as human-readable string.

        Return:
            包含日期、当日成交额、前一日成交额和60日均值的格式化字符串。
        """
        return f"大盘成交额 {self.date}: {self.amount} (前一日: {self.amount_before_one_day}, 60日平均: {self.amount_average_60_day})"

    


