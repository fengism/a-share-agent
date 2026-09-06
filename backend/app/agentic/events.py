import json
from typing import Any, Literal, cast
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from app.agentic.protocol import ToolCallInfo, ToolResultInfo

AgentPlanStepStatus = Literal[
    "pending",
    "running",
    "completed",
    "degraded",
    "failed",
    "cancelled",
]
AgentExecutionStatus = Literal["completed", "partial", "failed"]
AgentResearchRoundStatus = Literal["running", "completed", "degraded"]


class AgentToolSource(BaseModel):
    title: str = ""
    url: str
    domain: str = ""


class AgentToolResultSummary(BaseModel):
    summary: str
    status: Literal["success", "error", "skipped"] = "success"
    sources: list[AgentToolSource] = Field(default_factory=list, max_length=5)
    metadata: dict[str, str] = Field(default_factory=dict)


class AgentPlanStep(BaseModel):
    id: str
    title: str
    description: str | None = None
    agent_name: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    status: AgentPlanStepStatus = "pending"
    detail: str | None = None
    attempt: int = Field(default=0, ge=0)


class AgentPlan(BaseModel):
    summary: str | None = None
    steps: list[AgentPlanStep] = Field(default_factory=list)


class AgentPlanStepUpdate(BaseModel):
    step_id: str
    status: AgentPlanStepStatus
    detail: str | None = None
    attempt: int = Field(default=1, ge=1)


class AgentResearchRound(BaseModel):
    round_index: int = Field(ge=1)
    round_total: int = Field(ge=1)
    status: AgentResearchRoundStatus
    objective: str
    evidence_gaps: list[str] = Field(default_factory=list, max_length=32)
    tool_names: list[str] = Field(default_factory=list, max_length=32)
    tool_selection_reason: str = ""
    evidence_added: list[str] = Field(default_factory=list, max_length=32)
    judgment_basis: list[str] = Field(default_factory=list, max_length=32)
    conclusion: str = ""
    next_step: str = ""


class AgentEvent(BaseModel):
    type: Literal[
        "status",
        "plan",
        "round_started",
        "round_completed",
        "plan_step",
        "text",
        "reasoning",
        "tool_call",
        "tool_result",
        "error",
        "done",
    ]
    content: str | None = None
    plan: AgentPlan | None = None
    plan_step: AgentPlanStepUpdate | None = None
    research_round: AgentResearchRound | None = None
    tool_call: ToolCallInfo | None = None
    tool_result: ToolResultInfo | None = None
    tool_result_summary: AgentToolResultSummary | None = None
    error: str | None = None
    reasoning_content: str | None = None
    status: AgentExecutionStatus | None = None
    warnings: list[str] = Field(default_factory=list, max_length=16)


def _decoded_tool_result(content: str) -> Any:
    try:
        payload = json.loads(content)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict) and payload.get("ok") is True and "data" in payload:
        return payload["data"]
    return payload


def _collect_tool_sources(value: Any, sources: list[AgentToolSource], depth: int = 0) -> None:
    if depth > 5 or len(sources) >= 5:
        return
    if isinstance(value, list):
        for item in value:
            _collect_tool_sources(item, sources, depth + 1)
        return
    if not isinstance(value, dict):
        return
    raw_url = value.get("url")
    if isinstance(raw_url, str):
        try:
            parsed = urlsplit(raw_url)
        except ValueError:
            parsed = None
        if parsed is not None and parsed.scheme in {"http", "https"} and parsed.netloc:
            normalized_url = raw_url[:2048]
            if all(item.url != normalized_url for item in sources):
                sources.append(AgentToolSource(
                    title=str(value.get("title") or value.get("name") or "")[:300],
                    url=normalized_url,
                    domain=(parsed.hostname or "")[:255],
                ))
    for item in value.values():
        _collect_tool_sources(item, sources, depth + 1)


def _tool_result_summary(result: ToolResultInfo) -> AgentToolResultSummary:
    payload = _decoded_tool_result(result.content)
    error_code = ""
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        error_code = str(payload["error"].get("code") or "")[:80]
    if error_code == "tool_budget_exceeded":
        return AgentToolResultSummary(
            summary="工具调用额度已用尽，已基于现有结果继续分析",
            status="skipped",
        )
    if error_code == "duplicate_tool_call":
        return AgentToolResultSummary(
            summary="已跳过重复调用，继续使用已有结果",
            status="skipped",
        )
    if result.is_error:
        summary = {
            "invalid_arguments": "工具参数无效",
            "tool_unavailable": "工具暂时不可用",
            "execution_failed": "工具执行失败",
        }.get(error_code, "工具调用失败")
        return AgentToolResultSummary(summary=summary, status="error")

    data = payload
    count: int | None = None
    if isinstance(data, list):
        count = len(data)
    elif isinstance(data, dict):
        if isinstance(data.get("count"), int):
            count = data["count"]
        else:
            for key in ("results", "items", "records"):
                if isinstance(data.get(key), list):
                    count = len(data[key])
                    break
    sources: list[AgentToolSource] = []
    _collect_tool_sources(data, sources)
    metadata: dict[str, str] = {}
    if isinstance(data, dict):
        for key in ("source", "date", "analysis_date", "report_date", "period", "code", "name"):
            value = data.get(key)
            if isinstance(value, (str, int, float)) and str(value).strip():
                metadata[key] = str(value)[:160]
    if count is not None:
        summary = f"返回 {count} 条记录"
    elif sources:
        summary = f"获取 {len(sources)} 个来源"
    else:
        summary = "调用完成"
    return AgentToolResultSummary(summary=summary, sources=sources, metadata=metadata)


def auditable_agent_event(
    event: AgentEvent,
    *,
    include_text: bool = False,
    strip_tool_content: bool = True,
) -> AgentEvent | None:
    """Return the execution metadata safe to expose outside the Agent runtime."""
    if event.type == "reasoning" or (event.type == "text" and not include_text):
        return None
    update: dict[str, Any] = {}
    if event.reasoning_content is not None:
        update["reasoning_content"] = None
    if event.type == "tool_result" and event.tool_result is not None:
        update["tool_result_summary"] = _tool_result_summary(event.tool_result)
        if strip_tool_content:
            update["tool_result"] = event.tool_result.model_copy(update={"content": ""})
    return cast(AgentEvent, event.model_copy(update=update)) if update else event
