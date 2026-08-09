from typing import TypeAlias

from pydantic import BaseModel, Field

MacroValue: TypeAlias = str | int | float | None


class MacroIndicator(BaseModel):
    latest: dict[str, MacroValue] | None = None
    trend: list[dict[str, MacroValue]] = Field(default_factory=list)


class MacroAllDataResponse(BaseModel):
    prices: dict[str, MacroIndicator] = Field(default_factory=dict)
    sentiment: dict[str, MacroIndicator] = Field(default_factory=dict)
    monetary: dict[str, MacroIndicator] = Field(default_factory=dict)
    rates: dict[str, MacroIndicator] = Field(default_factory=dict)
    growth: dict[str, MacroIndicator] = Field(default_factory=dict)
    trade: dict[str, MacroIndicator] = Field(default_factory=dict)
