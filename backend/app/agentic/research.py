from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, AsyncContextManager, Protocol
from zoneinfo import ZoneInfo

from app.agentic.contracts import (
    MAX_AGENT_SUMMARY_LENGTH,
    AgentEvidence,
    AgentEvidenceInsufficientError,
    AgenticResearchResult,
    AgentResearchSpec,
    AgentRoundResult,
    EvidenceRequirement,
    render_agent_evidence,
)
from app.agentic.events import AgentEvent, AgentPlan, AgentPlanStep, AgentPlanStepUpdate

AgentEventCallback = Callable[[AgentEvent], Awaitable[None]]
_MARKET_TIMEZONE = ZoneInfo("Asia/Shanghai")
_DEFAULT_RECENCY_DAYS = 183


def build_research_system_prompt(
    spec: AgentResearchSpec,
    *,
    current_time: datetime | None = None,
) -> str:
    """为 Research Agent 注入运行时日期和通用检索约束。"""
    if current_time is None:
        resolved_time = datetime.now(_MARKET_TIMEZONE)
    elif current_time.tzinfo is None:
        resolved_time = current_time.replace(tzinfo=_MARKET_TIMEZONE)
    else:
        resolved_time = current_time.astimezone(_MARKET_TIMEZONE)
    resolved_date = resolved_time.date()
    sections = [
        spec.system_prompt.rstrip(),
        (
            "## 运行时日期与时间\n"
            f"- 当前时间（Asia/Shanghai）：{resolved_time.isoformat(sep=' ', timespec='seconds')}。"
            "所有‘当前’‘最新’‘今年’等相对时间都以此日期为准；用户明确指定的分析日期优先。\n"
            "- 不得沿用模型训练数据中的旧年份作为当前年份；历史年份只能用于趋势对比，并明确标注为历史数据。"
        ),
    ]
    if "web_search" in spec.tool_names:
        recency_start = resolved_date - timedelta(days=_DEFAULT_RECENCY_DAYS)
        sections.append(
            "## 网页检索式规则\n"
            f"- 默认最近半年指 {recency_start.isoformat()} 至 {resolved_date.isoformat()}；"
            "用户未指定时间时使用 time_range=half_year、language=zh。\n"
            "- 每个 query 只解决一个研究问题，使用‘核心实体 + 单一维度 + 地域/市场 + 资料类型 + 当前年份或最新’的简洁关键词组合。\n"
            "- 不要直接复制完整问题，不要把市场、技术、竞争、政策等多个维度塞进同一个 query，"
            "不要使用‘发展前景分析’这类宽泛词替代具体指标。\n"
            f"- 时效性 query 优先使用 {resolved_date.year}、‘最新’或当前季度；"
            "除非用户要求历史研究，不得主动加入更早年份。\n"
            "- 多次搜索必须覆盖不同维度、地域或来源类型，不得仅改写同义词重复搜索。\n"
            "- 检查结果标题、摘要和发布日期；若主要结果早于默认时间窗、偏离主题或缺少权威来源，"
            "应缩小研究维度并加入当前年份、官方、白皮书、研报、公告等来源词后重新搜索。"
        )
    return "\n\n".join(sections)


class AgentResearchSession(Protocol):
    async def run(
        self,
        message: str,
        allowed_tool_names: tuple[str, ...],
        event_callback: AgentEventCallback | None = None,
    ) -> AgentRoundResult: ...


class AgentResearchRuntime(Protocol):
    def open_session(
        self,
        spec: AgentResearchSpec,
        settings: Any = None,
    ) -> AsyncContextManager[AgentResearchSession]: ...


def _missing_requirements(
    requirements: tuple[EvidenceRequirement, ...],
    evidence: list[AgentEvidence],
) -> list[EvidenceRequirement]:
    successful_tools = {item.tool_name for item in evidence}
    return [
        requirement
        for requirement in requirements
        if not successful_tools.intersection(requirement.tool_names)
    ]


def _gap_tool_names(
    spec: AgentResearchSpec,
    missing: list[EvidenceRequirement],
) -> tuple[str, ...]:
    required_tools = {
        tool_name
        for requirement in missing
        for tool_name in requirement.tool_names
    }
    return tuple(tool_name for tool_name in spec.tool_names if tool_name in required_tools)


def _build_gap_message(
    original_message: str,
    first_result: AgentRoundResult,
    evidence: list[AgentEvidence],
    missing: list[EvidenceRequirement],
) -> str:
    labels = "、".join(item.label for item in missing)
    return "\n".join([
        f"原始调研任务：{original_message}",
        f"首轮调研摘要：{first_result.summary or '暂无结论'}",
        f"缺失证据维度：{labels}",
        "请仅围绕缺失维度继续调用允许的工具补齐证据。必须实际调用工具，不得使用常识补写。",
        "先检查已有工具参数，不得原样重复失败或低质量的查询；应根据缺失维度缩小范围并改进检索词。",
        "已有工具证据：",
        render_agent_evidence(evidence),
    ])


async def _emit(callback: AgentEventCallback | None, event: AgentEvent) -> None:
    if callback is not None:
        await callback(event)


async def _run_round(
    session: AgentResearchSession,
    message: str,
    allowed_tool_names: tuple[str, ...],
    event_callback: AgentEventCallback | None,
) -> AgentRoundResult:
    if event_callback is None:
        return await session.run(message, allowed_tool_names)
    return await session.run(
        message,
        allowed_tool_names,
        event_callback=event_callback,
    )


@dataclass(slots=True)
class _ResearchProgress:
    spec: AgentResearchSpec
    callback: AgentEventCallback | None
    step_status: dict[str, str] = field(init=False)
    requirements_by_tool: dict[str, tuple[EvidenceRequirement, ...]] = field(init=False)

    def __post_init__(self) -> None:
        self.step_status = {
            requirement.key: "pending"
            for requirement in self.spec.requirements
        }
        self.requirements_by_tool = {
            tool_name: tuple(
                requirement
                for requirement in self.spec.requirements
                if tool_name in requirement.tool_names
            )
            for tool_name in self.spec.tool_names
        }

    async def start(self) -> None:
        await _emit(self.callback, AgentEvent(
            type="plan",
            plan=AgentPlan(
                summary=f"{self.spec.display_name}将按证据维度推进调研",
                steps=[
                    AgentPlanStep(
                        id=requirement.key,
                        title=requirement.label,
                        description=f"使用 {' / '.join(requirement.tool_names)} 收集证据",
                        agent_name=self.spec.name,
                    )
                    for requirement in self.spec.requirements
                ],
            ),
        ))
        await _emit(self.callback, AgentEvent(
            type="status",
            content=f"{self.spec.display_name}正在规划并调用工具收集证据…",
        ))

    async def forward_event(self, event: AgentEvent) -> None:
        if event.type == "tool_call" and event.tool_call is not None:
            tool_name = event.tool_call.function.name
            for requirement in self.requirements_by_tool.get(tool_name, ()):
                if self.step_status[requirement.key] == "pending":
                    self.step_status[requirement.key] = "running"
                    await _emit(self.callback, AgentEvent(
                        type="plan_step",
                        plan_step=AgentPlanStepUpdate(
                            step_id=requirement.key,
                            status="running",
                            detail=f"正在调用 {tool_name}",
                        ),
                    ))
        await _emit(self.callback, event)
        if event.type == "tool_result" and event.tool_result is not None and not event.tool_result.is_error:
            tool_name = event.tool_result.name
            for requirement in self.requirements_by_tool.get(tool_name, ()):
                if self.step_status[requirement.key] != "completed":
                    self.step_status[requirement.key] = "completed"
                    await _emit(self.callback, AgentEvent(
                        type="plan_step",
                        plan_step=AgentPlanStepUpdate(
                            step_id=requirement.key,
                            status="completed",
                            detail=f"已通过 {tool_name} 获取证据",
                        ),
                    ))

    async def sync_completed_steps(self, evidence: list[AgentEvidence]) -> None:
        successful_tools = {item.tool_name for item in evidence}
        for requirement in self.spec.requirements:
            if (
                self.step_status[requirement.key] != "completed"
                and successful_tools.intersection(requirement.tool_names)
            ):
                self.step_status[requirement.key] = "completed"
                await _emit(self.callback, AgentEvent(
                    type="plan_step",
                    plan_step=AgentPlanStepUpdate(
                        step_id=requirement.key,
                        status="completed",
                        detail="已获取满足要求的工具证据",
                    ),
                ))

    async def mark_failed(self, missing: list[EvidenceRequirement]) -> None:
        for requirement in missing:
            self.step_status[requirement.key] = "failed"
            await _emit(self.callback, AgentEvent(
                type="plan_step",
                plan_step=AgentPlanStepUpdate(
                    step_id=requirement.key,
                    status="failed",
                    detail="未获取到满足要求的工具证据",
                ),
            ))


async def _collect_round_result(
    result: AgentRoundResult,
    evidence: list[AgentEvidence],
    summaries: list[str],
    progress: _ResearchProgress,
) -> None:
    evidence.extend(result.evidence)
    await progress.sync_completed_steps(evidence)
    if result.summary.strip():
        summaries.append(result.summary.strip())


async def run_agentic_research(
    spec: AgentResearchSpec,
    message: str,
    runtime: AgentResearchRuntime,
    settings: Any = None,
    event_callback: AgentEventCallback | None = None,
) -> AgenticResearchResult:
    evidence: list[AgentEvidence] = []
    summaries: list[str] = []
    progress = _ResearchProgress(spec, event_callback)
    await progress.start()
    round_callback = progress.forward_event if event_callback is not None else None

    async with runtime.open_session(spec, settings=settings) as session:
        first_result = await _run_round(
            session,
            message,
            spec.tool_names,
            round_callback,
        )
        await _collect_round_result(first_result, evidence, summaries, progress)

        missing = _missing_requirements(spec.requirements, evidence)
        if missing:
            await _emit(event_callback, AgentEvent(
                type="status",
                content=f"首轮证据仍缺少 {'、'.join(item.label for item in missing)}，正在补充调研…",
            ))
            gap_result = await _run_round(
                session,
                _build_gap_message(message, first_result, evidence, missing),
                _gap_tool_names(spec, missing),
                round_callback,
            )
            await _collect_round_result(gap_result, evidence, summaries, progress)

    missing = _missing_requirements(spec.requirements, evidence)
    if missing:
        await progress.mark_failed(missing)
        labels = "、".join(item.label for item in missing)
        raise AgentEvidenceInsufficientError(f"Agent 调研证据不足：{labels}")

    await _emit(event_callback, AgentEvent(type="done"))

    return AgenticResearchResult(
        summary="\n\n".join(summaries)[:MAX_AGENT_SUMMARY_LENGTH],
        evidence=tuple(evidence),
    )
