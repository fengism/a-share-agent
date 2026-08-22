from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.prompting import PromptTrace


class IndustryChainNode(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    company: str | None = None
    code: str | None = None
    role: str = ""
    description: str = ""
    companies: list[str] = Field(default_factory=list)
    market_share: str = ""
    metric: str = ""
    source: str = ""
    source_url: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    claim_type: Literal["fact", "inference", "opinion"] = "fact"
    confidence: Literal["high", "medium", "low"] = "medium"


class IndustryChainMetric(BaseModel):
    label: str
    value: str
    period: str = ""
    growth: str = ""
    source: str = ""
    source_url: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    claim_type: Literal["fact", "inference", "opinion"] = "fact"
    confidence: Literal["high", "medium", "low"] = "medium"


class IndustryChainInsight(BaseModel):
    title: str
    detail: str = ""
    evidence: str = ""
    source: str = ""
    source_url: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    claim_type: Literal["fact", "inference", "opinion"] = "inference"
    confidence: Literal["high", "medium", "low"] = "medium"


class IndustryChainCompetitionGroup(BaseModel):
    market: str
    summary: str = ""
    companies: list[IndustryChainNode] = Field(default_factory=list)


class IndustryChainEvent(BaseModel):
    date: str = ""
    title: str
    impact: str = ""
    source: str = ""
    source_url: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    claim_type: Literal["fact", "inference", "opinion"] = "fact"
    confidence: Literal["high", "medium", "low"] = "medium"


class IndustryChainSource(BaseModel):
    title: str
    publisher: str = ""
    date: str = ""
    url: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class IndustryChainEvidence(BaseModel):
    evidence_id: str
    tool_name: str
    provider: str = ""
    arguments: str = ""
    title: str = ""
    source_urls: list[str] = Field(default_factory=list)
    published_at: str = ""
    fetched_at: str = ""
    truncated: bool = False
    content_preview: str = ""
    status: Literal["success", "error"] = "success"
    error_message: str = ""


class IndustryChainEvidenceStats(BaseModel):
    total_count: int = 0
    unique_count: int = 0
    selected_count: int = 0
    omitted_count: int = 0
    failed_count: int = 0
    prompt_characters: int = 0


class IndustryChainCoverage(BaseModel):
    market: Literal["complete", "partial", "missing"] = "missing"
    competition: Literal["complete", "partial", "missing"] = "missing"
    technology: Literal["complete", "partial", "missing"] = "missing"
    chain: Literal["complete", "partial", "missing"] = "missing"
    companies: Literal["complete", "partial", "missing"] = "missing"
    events: Literal["complete", "partial", "missing"] = "missing"


class IndustryChainConflict(BaseModel):
    topic: str
    values: list[str] = Field(default_factory=list)
    reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class IndustryChainChart(BaseModel):
    title: str = ""
    description: str = ""
    type: str = ""
    option: dict[str, Any] = Field(default_factory=dict)


class IndustryChainResult(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    schema_version: int = 1
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    summary: str = ""
    positioning: str = ""
    summary_evidence_ids: list[str] = Field(default_factory=list)
    positioning_evidence_ids: list[str] = Field(default_factory=list)
    market_metrics: list[IndustryChainMetric] = Field(default_factory=list)
    competition: list[IndustryChainCompetitionGroup] = Field(default_factory=list)
    technology_routes: list[IndustryChainInsight] = Field(default_factory=list)
    upstream: list[IndustryChainNode] = Field(default_factory=list)
    midstream: list[IndustryChainNode] = Field(default_factory=list)
    downstream: list[IndustryChainNode] = Field(default_factory=list)
    drivers: list[str] = Field(default_factory=list)
    driver_insights: list[IndustryChainInsight] = Field(default_factory=list)
    trends: list[IndustryChainInsight] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    risk_insights: list[IndustryChainInsight] = Field(default_factory=list)
    capital_moves: list[IndustryChainInsight] = Field(default_factory=list)
    key_events: list[IndustryChainEvent] = Field(default_factory=list)
    key_stocks: list[IndustryChainNode] = Field(default_factory=list)
    sources: list[IndustryChainSource] = Field(default_factory=list)
    llm_review: str = ""
    charts: list[IndustryChainChart] = Field(default_factory=list)
    prompt_trace: PromptTrace | None = None
    quality_status: Literal["complete", "degraded"] = "complete"
    archive_status: Literal["none", "saved", "failed"] = "none"
    archive_id: str = ""
    warnings: list[str] = Field(default_factory=list)
    research_scope: dict[str, str] = Field(default_factory=dict)
    evidence_catalog: list[IndustryChainEvidence] = Field(default_factory=list)
    evidence_stats: IndustryChainEvidenceStats = Field(default_factory=IndustryChainEvidenceStats)
    coverage: IndustryChainCoverage = Field(default_factory=IndustryChainCoverage)
    missing_evidence: list[str] = Field(default_factory=list)
    conflicts: list[IndustryChainConflict] = Field(default_factory=list)
