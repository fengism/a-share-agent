from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.market import normalize_code

WatchlistAlertCondition = Literal[
    "price_above",
    "price_below",
    "change_pct_above",
    "change_pct_below",
]


class WatchlistItemCreate(BaseModel):
    stock_code: str
    note: str = Field(default="", max_length=200)

    @field_validator("stock_code")
    @classmethod
    def validate_stock_code(cls, value: str) -> str:
        return normalize_code(value).raw

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        return value.strip()


class WatchlistAlertCreate(BaseModel):
    condition: WatchlistAlertCondition
    threshold: float = Field(ge=-1_000_000, le=1_000_000)


class WatchlistAlert(BaseModel):
    id: int
    stock_code: str
    condition: WatchlistAlertCondition
    threshold: float
    enabled: bool
    triggered: bool = False
    current_value: float | None = None
    created_at: str


class WatchlistItem(BaseModel):
    id: int
    stock_code: str
    stock_name: str
    note: str
    created_at: str
    current_price: float | None = None
    change_pct: float | None = None
    quote_source: str = ""
    alerts: list[WatchlistAlert] = Field(default_factory=list)


class WatchlistResponse(BaseModel):
    items: list[WatchlistItem]
    source: str = ""
    quoted_at: str
