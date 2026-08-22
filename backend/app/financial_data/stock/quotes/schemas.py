from pydantic import BaseModel


class IntradayItem(BaseModel):
    """单条分时行情数据点。"""

    time: str
    price: float
    avg_price: float | None = None
    volume: float | None = None
    amount: float | None = None
    change_pct: float | None = None


class IntradayData(BaseModel):
    """股票分时行情数据集。"""

    code: str
    source: str = ""
    prev_close: float | None = None
    items: list[IntradayItem]
