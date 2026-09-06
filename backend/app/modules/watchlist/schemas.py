from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.market import normalize_code
from app.domain.stock import StockConcept
from app.financial_data.hk.service import normalize_hk_code

WatchlistMarket = Literal["cn", "hk"]

WatchlistAlertCondition = Literal[
    "price_above",
    "price_below",
    "change_pct_above",
    "change_pct_below",
]


class WatchlistItemCreate(BaseModel):
    market: WatchlistMarket = "cn"
    stock_code: str
    note: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def normalize_stock_code(self) -> Self:
        try:
            self.stock_code = (
                normalize_hk_code(self.stock_code)
                if self.market == "hk"
                else normalize_code(self.stock_code).raw
            )
        except ValueError:
            raise
        except Exception as error:
            raise ValueError(str(error)) from error
        return self

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        return value.strip()


class WatchlistAlertCreate(BaseModel):
    market: WatchlistMarket = "cn"
    condition: WatchlistAlertCondition
    threshold: float = Field(ge=-1_000_000, le=1_000_000)


class WatchlistAlert(BaseModel):
    id: int
    stock_code: str
    market: WatchlistMarket = "cn"
    condition: WatchlistAlertCondition
    threshold: float
    enabled: bool
    triggered: bool = False
    current_value: float | None = None
    created_at: str


class WatchlistItem(BaseModel):
    id: int
    stock_code: str
    market: WatchlistMarket = "cn"
    stock_name: str
    note: str
    created_at: str
    current_price: float | None = None
    change_pct: float | None = None
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    previous_close: float | None = None
    volume: float | None = None
    amount: float | None = None
    turnover_pct: float | None = None
    pe_ttm: float | None = None
    market_cap: float | None = None
    quote_source: str = ""
    concepts: list[StockConcept] = Field(default_factory=list)
    alerts: list[WatchlistAlert] = Field(default_factory=list)


class WatchlistResponse(BaseModel):
    items: list[WatchlistItem]
    source: str = ""
    quoted_at: str
