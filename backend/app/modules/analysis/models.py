from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.agentic.events import AgentEvent
from app.domain.prompting import PromptTrace
from app.modules.analysis.provenance import AnalysisProvenance

InformationGrade = Literal["A", "B", "C", "unknown"]
AssessmentLevel = Literal["strong", "moderate", "weak", "unclear"]
AssessmentDirection = Literal["strengthening", "stable", "weakening", "unclear"]
RiskLevel = Literal["high", "medium", "low", "unknown"]
ScenarioName = Literal["bull", "base", "bear"]


class InformationQuality(BaseModel):
    grade: InformationGrade = "unknown"
    grade_rationale: str = ""
    evidence_confidence: float | None = Field(default=None, ge=0, le=1)
    investment_certainty: float | None = Field(default=None, ge=0, le=1)
    coverage_summary: str = ""
    limitations: list[str] = Field(default_factory=list)


class SegmentQuality(BaseModel):
    segment: str
    role: str = ""
    growth_quality: str = ""
    profitability_quality: str = ""
    recurrence: str = ""
    evidence_confidence: float | None = Field(default=None, ge=0, le=1)


class BusinessModelResearch(BaseModel):
    economic_engine: str = ""
    revenue_drivers: list[str] = Field(default_factory=list)
    segment_quality: list[SegmentQuality] = Field(default_factory=list)
    earnings_quality: str = ""
    operating_leverage: str = ""
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class MoatItem(BaseModel):
    moat_type: Literal[
        "brand_pricing",
        "switching_cost",
        "network_effect",
        "scale_advantage",
        "technology_ip",
        "other",
    ]
    evidence: list[str] = Field(default_factory=list)
    counterevidence: list[str] = Field(default_factory=list)
    strength: AssessmentLevel = "unclear"
    direction: AssessmentDirection = "unclear"
    durability: str = ""
    threats: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)


class MoatAssessment(BaseModel):
    moats: list[MoatItem] = Field(default_factory=list)
    overall_durability: str = ""
    key_threats: list[str] = Field(default_factory=list)


class ManagementAssessment(BaseModel):
    track_record: str = ""
    capital_allocation: str = ""
    shareholder_alignment: str = ""
    succession_or_key_person_risk: str = ""
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)


class IndustryPosition(BaseModel):
    secular_context: str = ""
    value_chain_position: str = ""
    growth_drivers: list[str] = Field(default_factory=list)
    competitive_position: str = ""
    technology_or_obsolescence_risk: str = ""
    concentration_risks: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)


class RiskCase(BaseModel):
    risk: str
    failure_path: str = ""
    probability: RiskLevel = "unknown"
    impact: RiskLevel = "unknown"
    time_horizon: str = ""
    leading_indicators: list[str] = Field(default_factory=list)
    mitigants: list[str] = Field(default_factory=list)
    scenario: Literal["bull", "base", "bear", "cross_scenario"] = "cross_scenario"


class InversionAnalysis(BaseModel):
    bear_case: str = ""
    risks: list[RiskCase] = Field(default_factory=list)
    bias_checks: list[str] = Field(default_factory=list)


class ValuationScenario(BaseModel):
    scenario: ScenarioName
    assumptions: list[str] = Field(default_factory=list)
    valuation_view: str = ""
    fair_value_range: tuple[float, float] | None = None
    key_drivers: list[str] = Field(default_factory=list)
    invalidating_conditions: list[str] = Field(default_factory=list)


class ValuationScenarios(BaseModel):
    bull: ValuationScenario
    base: ValuationScenario
    bear: ValuationScenario

    @model_validator(mode="after")
    def validate_scenario_names(self) -> "ValuationScenarios":
        expected = (("bull", self.bull), ("base", self.base), ("bear", self.bear))
        mismatches = [key for key, scenario in expected if scenario.scenario != key]
        if mismatches:
            raise ValueError(f"估值情景名称与字段不一致：{', '.join(mismatches)}")
        return self


class ValuationFramework(BaseModel):
    method_summary: str = ""
    current_valuation: str = ""
    assumptions: list[str] = Field(default_factory=list)
    scenarios: ValuationScenarios | None = None
    margin_of_safety: str = ""
    limitations: list[str] = Field(default_factory=list)


class InvestorActionPlan(BaseModel):
    new_investor_action: Literal["buy", "watch", "avoid", "insufficient_evidence"] = "insufficient_evidence"
    holder_action: Literal["hold", "add", "reduce", "exit", "insufficient_evidence"] = "insufficient_evidence"
    rationale: str = ""
    buy_or_add_range: tuple[float, float] | None = None
    add_triggers: list[str] = Field(default_factory=list)
    sell_triggers: list[str] = Field(default_factory=list)
    thesis_breakers: list[str] = Field(default_factory=list)
    monitoring_metrics: list[str] = Field(default_factory=list)


class DataGap(BaseModel):
    topic: str
    missing_data: str = ""
    decision_impact: str = ""
    follow_up: str = ""


class InvestmentResearchFramework(BaseModel):
    information_quality: InformationQuality = Field(default_factory=InformationQuality)
    business_model: BusinessModelResearch = Field(default_factory=BusinessModelResearch)
    moat: MoatAssessment = Field(default_factory=MoatAssessment)
    management: ManagementAssessment = Field(default_factory=ManagementAssessment)
    industry_position: IndustryPosition = Field(default_factory=IndustryPosition)
    inversion: InversionAnalysis = Field(default_factory=InversionAnalysis)
    valuation: ValuationFramework = Field(default_factory=ValuationFramework)
    actions: InvestorActionPlan = Field(default_factory=InvestorActionPlan)
    data_gaps: list[DataGap] = Field(default_factory=list)


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
    report_id: str | None = None
    generated_at: str | None = None
    provenance: AnalysisProvenance | None = None
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
    research_framework: InvestmentResearchFramework | None = None
    prompt_trace: PromptTrace | None = None
    agent_trace: list[AgentEvent] = Field(default_factory=list)
