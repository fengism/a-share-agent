from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agentic.events import AgentEvent
from app.domain.prompting import PromptTrace


def _coerce_str_list(value: Any) -> Any:
    """LLM 常把列表字段写成整句字符串；宽容地包装为单元素列表。"""
    if isinstance(value, str):
        return [value] if value.strip() else []
    return value


_CLAIM_TYPE_ALIASES = {
    # LLM 偶发把证据基础词直接填进 claim_type；映射到最接近的合法枚举。
    "forecast": "inference",
    "prediction": "inference",
    "预测": "inference",
    "推断": "inference",
    "事实": "fact",
    "观点": "opinion",
}


def _normalize_claim_type(value: Any) -> Any:
    if isinstance(value, str):
        return _CLAIM_TYPE_ALIASES.get(value.strip().lower(), value)
    return value


class IndustryChainCitation(BaseModel):
    evidence_id: str
    quote: str = Field(default="", max_length=1500)
    source_url: str = Field(default="", description="服务端匹配原文所属 URL，不接受模型自报链接")
    location: str = Field(default="", max_length=200, description="原文页码/表格/章节；未核实则留空")


class IndustryChainClaim(BaseModel):
    citations: list[IndustryChainCitation] = Field(default_factory=list)
    verification_status: Literal["unverified", "quote_matched"] = "unverified"
    verification_notes: list[str] = Field(default_factory=list)
    evidence_basis: Literal["disclosed", "forecast", "inference", "opinion"] = "disclosed"

    @field_validator("verification_notes", "evidence_ids", mode="before", check_fields=False)
    @classmethod
    def _coerce_claim_str_lists(cls, value: Any) -> Any:
        # evidence_ids 定义在各子类上；check_fields=False 让基类校验器沿继承链生效。
        return _coerce_str_list(value)

    @field_validator("claim_type", mode="before", check_fields=False)
    @classmethod
    def _coerce_claim_type(cls, value: Any) -> Any:
        return _normalize_claim_type(value)


class IndustryChainNode(IndustryChainClaim):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    company: str | None = None
    code: str | None = None
    role: str = ""
    description: str = ""
    companies: list[str] = Field(default_factory=list)
    business_relevance: Literal["unverified", "concept", "business", "earnings"] = "unverified"
    revenue_share: str = ""
    revenue_period: str = ""
    benefit_path: str = ""
    realization_conditions: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    tracking_metrics: list[str] = Field(default_factory=list)
    market_share: str = ""
    metric: str = ""
    source: str = ""
    source_url: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    claim_type: Literal["fact", "inference", "opinion"] = "fact"
    confidence: Literal["high", "medium", "low"] = "medium"
    pe: str = ""
    pb: str = ""
    total_market_cap: str = ""
    pe_percentile: str = ""
    consensus_forecast: str = ""
    gross_margin: str = ""
    net_margin: str = ""
    moat: str = ""
    eps_elasticity: str = ""
    roe: str = Field(default="", description="净资产收益率（ROE），如 18.5%")
    growth_rate: str = Field(default="", description="业绩增速（营收/净利 YoY），如 营收+15.2% / 净利+28.0%")
    price_change: str = Field(default="", description="最新股价及涨跌幅，如 128.50 (+2.3%)")
    restricted_risk: str = Field(default="", description="限售解禁抛压风险提示")
    overseas_share: str = Field(default="", description="海外或出口业务营收占比及毛利率，如 94.8% (境外 · 毛利47.9%)")

    @field_validator(
        "companies", "realization_conditions", "invalidation_conditions", "tracking_metrics", mode="before"
    )
    @classmethod
    def _coerce_node_str_lists(cls, value: Any) -> Any:
        return _coerce_str_list(value)


class IndustryChainMetric(IndustryChainClaim):
    label: str
    value: str
    period: str = ""
    growth: str = ""
    metric_id: str = ""
    numeric_value: str = ""
    unit: str = ""
    region: str = ""
    statistical_scope: str = ""
    source: str = ""
    source_url: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    claim_type: Literal["fact", "inference", "opinion"] = "fact"
    confidence: Literal["high", "medium", "low"] = "medium"


class IndustryChainInsight(IndustryChainClaim):
    title: str
    detail: str = ""
    evidence: str = ""
    source: str = ""
    source_url: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    claim_type: Literal["fact", "inference", "opinion"] = "inference"
    confidence: Literal["high", "medium", "low"] = "medium"


class IndustryChainThesis(IndustryChainInsight):
    chain_path: list[str] = Field(default_factory=list, max_length=6)
    mechanism: str = ""
    conditions: list[str] = Field(default_factory=list)
    counter_evidence: str = ""
    invalidation: str = ""
    tracking_metrics: list[str] = Field(default_factory=list)
    beneficiaries: list[str] = Field(default_factory=list)

    @field_validator("chain_path", "conditions", "tracking_metrics", "beneficiaries", mode="before")
    @classmethod
    def _coerce_thesis_str_lists(cls, value: Any) -> Any:
        return _coerce_str_list(value)


class IndustryChainVerificationRepair(BaseModel):
    status: Literal["not_needed", "completed", "no_new_evidence", "failed"] = "not_needed"
    attempted_rounds: int = 0
    added_evidence_count: int = 0
    targets: list[str] = Field(default_factory=list)
    note: str = ""


class IndustryChainRelationship(IndustryChainInsight):
    driver: str = ""
    target_metric: str = ""
    time_lag: str = ""
    tracking_metrics: list[str] = Field(default_factory=list)
    source_node: str
    target_node: str
    relation_type: Literal["supply", "purchase", "substitute", "compete", "transmission"]
    impact_direction: Literal["positive", "negative", "mixed", "unknown"] = "unknown"
    conditions: list[str] = Field(default_factory=list)
    invalidation: str = ""


class IndustryChainCompetitionGroup(BaseModel):
    market: str
    summary: str = ""
    companies: list[IndustryChainNode] = Field(default_factory=list)


class IndustryChainEvent(IndustryChainClaim):
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
    material_type: Literal["discovery", "body", "structured", "unknown"] = "unknown"


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


class IndustryChainValueDistribution(BaseModel):
    """价值链价值量（BOM）与利润池分配。"""

    segment: str = Field(default="", description="环节或核心零部件/组件名称")
    cost_share: str = Field(default="", description="单机/系统价值量或 BOM 成本占比，如 35%")
    gross_margin_range: str = Field(default="", description="毛利率区间，如 40%~50%")
    profit_share: str = Field(default="", description="产业链利润池占比或定性分布")
    pricing_power: Literal["high", "medium", "low", "unverified"] = "unverified"
    detail: str = Field(default="", description="成本构成、议价权及技术门槛简述")


class IndustryChainCycleAnalysis(BaseModel):
    """产业链供需周期与顺价机制定位。"""

    stage: str = Field(default="", description="周期所处阶段，如主动补库/产能出清/供需紧平衡")
    capacity_utilization: str = Field(default="", description="行业产能利用率或开工率")
    expansion_lead_time: str = Field(default="", description="扩产建设与认证壁垒周期，如 12-18 个月")
    inflection_point: str = Field(default="", description="供需缺口或景气拐点推演")
    pass_through_ability: str = Field(default="", description="成本顺价传导能力与毛利率弹性")


class IndustryChainExpectationDivergence(BaseModel):
    """市场一致预期 vs 本次研究分歧（预期差推演）。"""

    topic: str = Field(default="", description="预期差主题，如出海增速/渗透率节奏/替代路线")
    consensus: str = Field(default="", description="市场主流一致预期")
    divergence: str = Field(default="", description="本次研究审慎/独立推断")
    catalyst_trigger: str = Field(default="", description="预期差验证的核心观测指标与时间窗口")


class IndustryChainChart(BaseModel):
    title: str = ""
    description: str = ""
    type: str = ""
    option: dict[str, Any] = Field(default_factory=dict)


class IndustryChainChangeItem(BaseModel):
    category: Literal["chain", "company", "market", "event", "driver", "risk", "summary"]
    change_type: Literal["added", "removed", "updated"]
    title: str
    detail: str = ""
    before: str = ""
    after: str = ""
    change_basis: Literal["fact", "observation", "evidence", "text"] = "text"
    numeric_delta: str = ""
    percentage_delta: str = ""


class IndustryChainChangeSet(BaseModel):
    previous_archive_id: str = ""
    comparable: bool = True
    comparison_note: str = ""
    has_changes: bool = False
    added_count: int = 0
    removed_count: int = 0
    updated_count: int = 0
    items: list[IndustryChainChangeItem] = Field(default_factory=list)


class IndustryChainOpportunity(BaseModel):
    name: str
    code: str = ""
    role: str = ""
    prosperity_score: int = 0
    earnings_score: int = 0
    valuation_score: int = 0
    catalyst_score: int = 0
    evidence_score: int = 0
    risk_score: int = 0
    total_score: int = 0
    scoring_version: int = 1
    score_kind: Literal["research_completeness"] = "research_completeness"
    completeness_score: int = 0
    fundamental_status: Literal["not_evaluated"] = "not_evaluated"
    rationale: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class IndustryChainTopicResolution(BaseModel):
    requested_name: str = ""
    normalized_name: str = ""
    aliases: list[str] = Field(default_factory=list)
    matched_sectors: list[str] = Field(default_factory=list)
    possible_topics: list[str] = Field(default_factory=list)
    boundary_note: str = ""


class IndustryChainAnalysisMetadata(BaseModel):
    total_duration_ms: int = 0
    research_duration_ms: int = 0
    synthesis_duration_ms: int = 0
    draft_duration_ms: int = 0
    verification_duration_ms: int = 0
    finalization_duration_ms: int = 0
    archive_duration_ms: int = 0
    cache_hits: list[str] = Field(default_factory=list)
    cache_misses: list[str] = Field(default_factory=list)
    failed_dimensions: list[str] = Field(default_factory=list)
    successful_dimensions: list[str] = Field(default_factory=list)
    agent_evidence_count: int = 0
    public_item_count: int = 0
    independent_source_count: int = 0


class IndustryChainResult(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    schema_version: int = 1
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    summary: str = ""
    positioning: str = ""
    research_theses: list[IndustryChainThesis] = Field(default_factory=list)
    verification_repair: IndustryChainVerificationRepair = Field(default_factory=IndustryChainVerificationRepair)
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
    agent_trace: list[AgentEvent] = Field(default_factory=list)
    changes: IndustryChainChangeSet = Field(default_factory=IndustryChainChangeSet)
    opportunities: list[IndustryChainOpportunity] = Field(default_factory=list)
    relationships: list[IndustryChainRelationship] = Field(default_factory=list)
    value_distribution: list[IndustryChainValueDistribution] = Field(default_factory=list)
    cycle_analysis: IndustryChainCycleAnalysis = Field(default_factory=IndustryChainCycleAnalysis)
    expectation_divergences: list[IndustryChainExpectationDivergence] = Field(default_factory=list)
    topic_resolution: IndustryChainTopicResolution = Field(default_factory=IndustryChainTopicResolution)
    analysis_metadata: IndustryChainAnalysisMetadata = Field(default_factory=IndustryChainAnalysisMetadata)
