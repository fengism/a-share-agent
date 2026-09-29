import json
from typing import Any, Literal, cast
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from app.agentic.protocol import ToolCallInfo, ToolResultInfo
from app.agentic.runtime.tool_budget import budget_rejection_message

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


class AgentReasoningSource(BaseModel):
    block_id: str
    source: str = "模型"
    stage: Literal["agent", "synthesis"] = "agent"
    turn: int = Field(default=1, ge=1)
    task_id: str | None = None
    attempt: int = Field(default=1, ge=1)


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
    phase: Literal["research", "verification_repair"] | None = None
    content: str | None = None
    plan: AgentPlan | None = None
    plan_step: AgentPlanStepUpdate | None = None
    research_round: AgentResearchRound | None = None
    tool_call: ToolCallInfo | None = None
    tool_result: ToolResultInfo | None = None
    tool_result_summary: AgentToolResultSummary | None = None
    error: str | None = None
    reasoning_content: str | None = None
    reasoning_source: AgentReasoningSource | None = None
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


# 只允许用 reason 枚举映射文案，不透传 message 原文：message 里含有模型自己
# 传入的键名（如「包含未声明参数：<任意字符串>」），直接展示等于把不受控输入
# 打到界面上。field/detail 由 validate_value 填充，只来自 schema 或白名单。
_INVALID_ARGUMENT_LABELS: dict[str, str] = {
    "invalid_json": "参数不是合法 JSON",
    "type_mismatch": "参数类型不正确",
    "missing_required": "缺少必填参数",
    "unexpected_parameter": "包含未声明参数",
    "enum": "参数取值不在允许范围",
    "const_mismatch": "参数取值不符合约定",
    "min_items": "数组项数不足",
    "max_items": "数组项数超限",
    "duplicate_items": "数组存在重复项",
    "min_length": "参数长度不足",
    "max_length": "参数长度超限",
    "pattern": "参数格式不正确",
    "invalid_date": "日期格式不正确",
    "invalid_url": "URL 格式不正确",
    "not_finite": "数值必须是有限值",
    "below_minimum": "参数数值过小",
    "above_maximum": "参数数值过大",
    "below_exclusive_minimum": "参数数值过小",
    "above_exclusive_maximum": "参数数值过大",
    "not_multiple_of": "参数数值必须是指定步长的倍数",
}


def _invalid_arguments_summary(payload: Any) -> str:
    """把受控的 reason/field/detail 组装成界面文案；信息缺失时退回通用文案。

    只读 ``data.argument_error`` 这个专属命名空间：该字段只有 ``Tool.execute``
    的契约校验分支会写，而 ``data`` 本身还会承载工具自报的原始返回。
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    diagnostics = data.get("argument_error") if isinstance(data, dict) else None
    if not isinstance(diagnostics, dict):
        return "工具参数无效"
    label = _INVALID_ARGUMENT_LABELS.get(str(diagnostics.get("reason") or ""))
    if label is None:
        return "工具参数无效"
    field = str(diagnostics.get("field") or "")
    detail = str(diagnostics.get("detail") or "")
    text = f"{label}：{field}" if field else label
    if detail:
        text = f"{text}（{detail}）" if field else f"{text}：{detail}"
    return text[:200]


def _tool_result_summary(result: ToolResultInfo) -> AgentToolResultSummary:
    payload = _decoded_tool_result(result.content)
    error_code = ""
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        error_code = str(payload["error"].get("code") or "")[:80]
    if error_code == "tool_budget_exceeded":
        data = payload.get("data") if isinstance(payload, dict) else None
        diagnostics = data.get("budget") if isinstance(data, dict) else None
        return AgentToolResultSummary(summary=budget_rejection_message(diagnostics), status="skipped")
    if error_code == "tool_context_budget_exhausted":
        return AgentToolResultSummary(
            summary="工具结果上下文预算已用尽，本次未实际执行",
            status="skipped",
        )
    if error_code == "duplicate_tool_call":
        return AgentToolResultSummary(
            summary="已跳过重复调用，继续使用已有结果",
            status="skipped",
        )
    if result.is_error:
        if error_code == "invalid_arguments":
            return AgentToolResultSummary(
                summary=_invalid_arguments_summary(payload),
                status="error",
            )
        summary = {
            "tool_unavailable": "工具暂时不可用",
            "execution_failed": "工具执行失败",
            "upstream_unavailable": "数据源暂不可用",
            "sandbox_unavailable": "沙盒服务不可用",
            "tool_queue_timeout": "工具并发额度已满，本次未执行",
        }.get(error_code, "工具调用失败")
        # Only publish allowlisted PDF diagnostics, never arbitrary provider error text.
        if result.name == "read_pdf" and isinstance(payload, dict):
            data = payload.get("data") if payload.get("ok") is False else payload
            reason = data.get("error_reason") if isinstance(data, dict) else None
            summary = {
                "pdf_browser_disabled": "网站要求访问验证，但浏览器抓取未启用",
                "pdf_browser_timeout": "网站访问验证或 PDF 下载超时",
                "pdf_browser_failed": "网站要求访问验证，浏览器重试未能下载 PDF",
                "pdf_not_pdf": "链接未返回 PDF 文件，请检查链接是否有效",
                "pdf_no_text": "指定页或续读位置未取得可读正文，请检查页码",
                "pdf_invalid_range": "PDF页码或续读参数无效",
                "pdf_window_changed": "PDF内容已变化，请重新读取该页窗口",
            }.get(str(reason), summary)
        if result.name == "web_fetch" and isinstance(payload, dict):
            data = payload.get("data") if payload.get("ok") is False else payload
            reason = data.get("error_reason") if isinstance(data, dict) else None
            summary = {
                "web_empty_body": "网页未返回正文",
                "web_insufficient_body": "网页正文过短，不能作为研究证据",
                "web_unreadable_body": "网页正文不可读，请更换原文来源",
                "web_script_shell": "网页仅返回脚本占位，需要浏览器读取",
                "web_challenge": "网页返回访问验证，未取得正文",
                "web_url_not_public": "目标地址指向内网，已拒绝抓取",
                "web_fetch_failed": "目标站点不可达或响应无效",
                "web_not_found": "目标页面不存在或已下线",
                "web_browser_failed": "HTTP 与浏览器两种方式均未取得正文",
            }.get(str(reason), summary)
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
    if result.name == "web_search" and isinstance(data, dict):
        # 映射到 source：前端已把该键渲染成「数据源」，且 engine 记录的是降级后
        # 真正应答的引擎，百度被拦回落 Bing 时前端能直接看出来。
        engine = data.get("engine")
        if isinstance(engine, str) and engine.strip():
            metadata["source"] = engine.strip()[:160]
    if result.name == "web_fetch" and isinstance(data, dict):
        mode = data.get("fetch_mode")
        quality = data.get("body_quality")
        if mode in {"http", "dynamic", "stealth"}:
            metadata["fetch_mode"] = mode
        if quality in {"usable", "unusable"}:
            metadata["body_quality"] = quality
        if isinstance(data.get("content"), str):
            metadata["content_characters"] = str(len(data["content"]))
    if result.name == "web_fetch" and metadata.get("body_quality") == "usable":
        summary = f"取得可读正文 {metadata.get('content_characters', '0')} 字（不等于事实核实）"
    elif count is not None:
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
    include_reasoning: bool = False,
    strip_tool_content: bool = True,
) -> AgentEvent | None:
    """Filter runtime events; chat may opt in to provider-returned reasoning.

    Research/report consumers keep the metadata-only default.
    """
    if (event.type == "reasoning" and not include_reasoning) or (event.type == "text" and not include_text):
        return None
    update: dict[str, Any] = {}
    if event.reasoning_content is not None and not include_reasoning:
        update["reasoning_content"] = None
    if event.type == "tool_result" and event.tool_result is not None:
        # Research -> pipeline -> workflow may apply redaction more than once.
        # Do not overwrite a computed summary by re-parsing the already emptied body.
        if event.tool_result.content or event.tool_result_summary is None:
            update["tool_result_summary"] = _tool_result_summary(event.tool_result)
        if strip_tool_content:
            update["tool_result"] = event.tool_result.model_copy(update={"content": ""})
    return cast(AgentEvent, event.model_copy(update=update)) if update else event
