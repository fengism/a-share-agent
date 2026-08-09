from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.infrastructure.llm.prompting.schemas import PromptTrace


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


class IndustryChainMetric(BaseModel):
    label: str
    value: str
    period: str = ""
    growth: str = ""
    source: str = ""
    source_url: str = ""


class IndustryChainInsight(BaseModel):
    title: str
    detail: str = ""
    evidence: str = ""
    source: str = ""


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


class IndustryChainSource(BaseModel):
    title: str
    publisher: str = ""
    date: str = ""
    url: str = ""


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
    market_metrics: list[IndustryChainMetric] = Field(default_factory=list)
    competition: list[IndustryChainCompetitionGroup] = Field(default_factory=list)
    technology_routes: list[IndustryChainInsight] = Field(default_factory=list)
    upstream: list[IndustryChainNode] = Field(default_factory=list)
    midstream: list[IndustryChainNode] = Field(default_factory=list)
    downstream: list[IndustryChainNode] = Field(default_factory=list)
    drivers: list[str] = Field(default_factory=list)
    trends: list[IndustryChainInsight] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    capital_moves: list[IndustryChainInsight] = Field(default_factory=list)
    key_events: list[IndustryChainEvent] = Field(default_factory=list)
    key_stocks: list[IndustryChainNode] = Field(default_factory=list)
    sources: list[IndustryChainSource] = Field(default_factory=list)
    llm_review: str = ""
    charts: list[IndustryChainChart] = Field(default_factory=list)
    prompt_trace: PromptTrace | None = None
