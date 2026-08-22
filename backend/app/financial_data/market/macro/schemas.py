from typing import TypeAlias

from pydantic import BaseModel, Field

MacroValue: TypeAlias = str | int | float | None


class MacroIndicator(BaseModel):
    latest: dict[str, MacroValue] | None = None
    trend: list[dict[str, MacroValue]] = Field(default_factory=list)
    source: str | None = None
    source_api: str | None = None
    latest_period: str | None = None
    is_fallback: bool = False
    is_stale: bool = False
    field_periods: dict[str, str] = Field(default_factory=dict)
    stale_fields: list[str] = Field(default_factory=list)


class MacroAllDataResponse(BaseModel):
    prices: dict[str, MacroIndicator] = Field(default_factory=dict)
    sentiment: dict[str, MacroIndicator] = Field(default_factory=dict)
    monetary: dict[str, MacroIndicator] = Field(default_factory=dict)
    rates: dict[str, MacroIndicator] = Field(default_factory=dict)
    growth: dict[str, MacroIndicator] = Field(default_factory=dict)
    trade: dict[str, MacroIndicator] = Field(default_factory=dict)


class MacroUsDataResponse(BaseModel):
    indicators: dict[str, MacroIndicator] = Field(default_factory=dict)
    updated_at: str | None = None
    refreshing: bool = False
    failed_indicators: dict[str, str] = Field(default_factory=dict)
