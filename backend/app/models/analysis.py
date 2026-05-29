from pydantic import BaseModel, Field


class FactorAnalysis(BaseModel):
    score: int = Field(ge=1, le=10)
    summary: str
    strengths: list[str] = []
    risks: list[str] = []
    trend: str | None = None
    support_level: float | None = None
    resistance_level: float | None = None
    key_signals: list[str] = []
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
    signal: str  # strong_buy | buy | hold | sell | strong_sell
    confidence: float = Field(ge=0, le=1)
    key_factors: list[str] = []
    risk_warnings: list[str] = []


class AnalysisStage(BaseModel):
    stage: int
    name: str
    status: str  # started | completed | failed
    detail: str | None = None
    duration_ms: int | None = None


class AnalysisProgress(BaseModel):
    type: str  # stage_started | stage_completed | stage_failed | complete | error | cached
    stage: AnalysisStage | None = None
    total_stages: int = 4
    result: AnalysisResult | None = None
    error: str | None = None


class AnalysisHistoryItem(BaseModel):
    stock_code: str
    stock_name: str
    analysis_date: str
    current_price: float | None = None
    overall_rating: int | None = None
    signal: str | None = None
    confidence: float | None = None
