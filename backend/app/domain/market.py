from pydantic import BaseModel


class IndexItem(BaseModel):
    """单个市场指数的行情数据项。"""

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
    """市场概览数据。"""

    date: str | None = None
    indices: list[IndexItem]
    source: str | None = None
    total_amount: float = 0.0


class MarketVolume(BaseModel):
    """市场成交额数据。"""

    date: str | None = None
    amount: float | None = None
    amount_before_one_day: float | None = None
    amount_average_60_day: float | None = None

    def to_str(self) -> str:
        return (
            f"大盘成交额 {self.date}: {self.amount} "
            f"(前一日: {self.amount_before_one_day}, 60日平均: {self.amount_average_60_day})"
        )


class KlineItem(BaseModel):
    """单根 K 线行情数据。"""

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
    """统一的股票与指数 K 线数据集。"""

    code: str
    period: str
    adjust: str
    source: str | None = None
    adjustment_verified: bool = False
    items: list[KlineItem]
