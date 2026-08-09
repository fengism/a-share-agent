from typing import Literal

from pydantic import BaseModel, Field

from app.infrastructure.llm.prompting.schemas import PromptTrace


class FactorAnalysis(BaseModel):
    score: int = Field(ge=1, le=10)
    summary: str
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    trend: str | None = None
    support_level: float | None = None
    resistance_level: float | None = None
    key_signals: list[str] = Field(default_factory=list)
    market_mood: str | None = None
    heat_level: str | None = None


class AnalysisResult(BaseModel):
    stock_code: str
    stock_name: str
    analysis_date: str
    current_price: float
    fundamental: FactorAnalysis
    technical: FactorAnalysis
    sentiment: FactorAnalysis
    valuation_view: str | None = None
    fair_value_range: tuple[float, float] | None = None
    blended_fair_value: float | None = None
    overall_rating: int = Field(ge=1, le=10)
    overall_summary: str
    estimated_price_range: tuple[float, float]
    signal: Literal["strong_buy", "buy", "hold", "sell", "strong_sell"]
    confidence: float = Field(ge=0, le=1)
    key_factors: list[str] = Field(default_factory=list)
    risk_warnings: list[str] = Field(default_factory=list)
    prompt_trace: PromptTrace | None = None
