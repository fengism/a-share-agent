from __future__ import annotations

from collections import Counter
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
from app.agentic.events import (
    AgentEvent,
    AgentPlan,
    AgentPlanStep,
    AgentPlanStepUpdate,
    AgentResearchRound,
    auditable_agent_event,
)
from app.agentic.tools.serialization import has_meaningful_tool_content

AgentEventCallback = Callable[[AgentEvent], Awaitable[None]]
_MARKET_TIMEZONE = ZoneInfo("Asia/Shanghai")
_DEFAULT_RECENCY_DAYS = 183
_FOLLOWUP_TOOL_CALL_RESERVE = 8


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
    sections.append(
        "## 数据源权威性与冲突处理\n"
        "- 官方财报与结构化接口（如 analyze_financials, get_stock_info, get_stock_valuation_detail 等）是定量财务事实的最高准绳。\n"
        "- 若搜索结果（web_search / iwencai_search）或网页抓取（fetch_url）中的二手财务数据与财报接口返回的财务指标（营收、归母净利、扣非净利、毛利率、资产负债率、EPS、分部数据等）存在差异或冲突，必须无条件以财报接口数据为准，严禁采用搜索引擎摘要或第三方非标网页数据覆盖财报接口数据。\n"
        "- 网页搜索与外部资料仅用于获取行业趋势、商业护城河背景、产业链地位和舆情定性资料，不用于替代定量财务数据。"
    )
    return "\n\n".join(sections)


class AgentResearchSession(Protocol):
    async def run(
        self,
        message: str,
        allowed_tool_names: tuple[str, ...],
        event_callback: AgentEventCallback | None = None,
        tool_call_reserve: int = 0,
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
    return [
        requirement
        for requirement in requirements
        if not any(requirement.accepts(item) for item in evidence)
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
    discovery_tools = {"web_search", "iwencai_search"}
    if required_tools.intersection({"fetch_url", "fetch_urls"}):
        required_tools.update(discovery_tools.intersection(spec.tool_names))
    return tuple(tool_name for tool_name in spec.tool_names if tool_name in required_tools)


def _build_gap_message(
    original_message: str,
    previous_result: AgentRoundResult,
    evidence: list[AgentEvidence],
    missing: list[EvidenceRequirement],
    round_index: int = 2,
) -> str:
    labels = "、".join(item.label for item in missing)
    round_desc = f"第 {round_index} 轮" if round_index > 1 else "本轮"
    return "\n".join([
        f"原始调研任务：{original_message}",
        f"前序调研摘要：{previous_result.summary or '暂无结论'}",
        f"缺失证据维度（{round_desc}）：{labels}",
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
    *,
    tool_call_reserve: int = 0,
) -> AgentRoundResult:
    if event_callback is None:
        return await session.run(
            message,
            allowed_tool_names,
            tool_call_reserve=tool_call_reserve,
        )
    return await session.run(
        message,
        allowed_tool_names,
        event_callback=event_callback,
        tool_call_reserve=tool_call_reserve,
    )


@dataclass(slots=True)
class _ResearchProgress:
    spec: AgentResearchSpec
    callback: AgentEventCallback | None
    step_status: dict[str, str] = field(init=False)
    requirements_by_tool: dict[str, tuple[EvidenceRequirement, ...]] = field(init=False)
    tool_arguments: dict[str, str] = field(init=False)
    audit_events: list[AgentEvent] = field(init=False)

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
        self.tool_arguments = {}
        self.audit_events = []

    async def emit(self, event: AgentEvent) -> None:
        public_event = auditable_agent_event(event)
        if public_event is None:
            return
        self.audit_events.append(public_event)
        await _emit(self.callback, public_event)

    async def start(self) -> None:
        await self.emit(AgentEvent(
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
        await self.emit(AgentEvent(
            type="status",
            content=f"{self.spec.display_name}正在规划并调用工具收集证据…",
        ))

    async def forward_event(self, event: AgentEvent) -> None:
        if event.type == "tool_call" and event.tool_call is not None:
            tool_name = event.tool_call.function.name
            self.tool_arguments[event.tool_call.id] = event.tool_call.function.arguments
            for requirement in self.requirements_by_tool.get(tool_name, ()):
                if self.step_status[requirement.key] == "pending":
                    self.step_status[requirement.key] = "running"
                    await self.emit(AgentEvent(
                        type="plan_step",
                        plan_step=AgentPlanStepUpdate(
                            step_id=requirement.key,
                            status="running",
                            detail=f"正在调用 {tool_name}",
                        ),
                    ))
        await self.emit(event)
        if (
            event.type == "tool_result"
            and event.tool_result is not None
            and not event.tool_result.is_error
            and has_meaningful_tool_content(event.tool_result.content)
        ):
            tool_name = event.tool_result.name
            candidate = AgentEvidence(
                tool_call_id=event.tool_result.tool_call_id,
                tool_name=tool_name,
                arguments=self.tool_arguments.get(event.tool_result.tool_call_id, "{}"),
                content=event.tool_result.content,
            )
            for requirement in self.requirements_by_tool.get(tool_name, ()):
                if self.step_status[requirement.key] != "completed" and requirement.accepts(candidate):
                    self.step_status[requirement.key] = "completed"
                    await self.emit(AgentEvent(
                        type="plan_step",
                        plan_step=AgentPlanStepUpdate(
                            step_id=requirement.key,
                            status="completed",
                            detail=f"已通过 {tool_name} 获取证据",
                        ),
                    ))

    async def sync_completed_steps(self, evidence: list[AgentEvidence]) -> None:
        for requirement in self.spec.requirements:
            if (
                self.step_status[requirement.key] != "completed"
                and any(requirement.accepts(item) for item in evidence)
            ):
                self.step_status[requirement.key] = "completed"
                await self.emit(AgentEvent(
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
            await self.emit(AgentEvent(
                type="plan_step",
                plan_step=AgentPlanStepUpdate(
                    step_id=requirement.key,
                    status="failed",
                    detail="未获取到满足要求的工具证据",
                ),
            ))

    async def mark_degraded(self, missing: list[EvidenceRequirement]) -> None:
        for requirement in missing:
            self.step_status[requirement.key] = "degraded"
            await self.emit(AgentEvent(
                type="plan_step",
                plan_step=AgentPlanStepUpdate(
                    step_id=requirement.key,
                    status="degraded",
                    detail="未获取到满足门槛的正文证据，已按数据缺口降级",
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


def _round_objective(
    round_index: int,
    requirements: list[EvidenceRequirement],
) -> str:
    labels = "、".join(item.label for item in requirements)
    if round_index == 1:
        return f"建立{labels}的完整证据基线"
    return f"补齐{labels}的证据缺口"


def _round_tool_selection_reason(
    round_index: int,
    requirements: list[EvidenceRequirement],
) -> str:
    labels = "、".join(item.label for item in requirements)
    if round_index == 1:
        return "选择覆盖全部证据维度的可用工具，先建立完整证据基线"
    return f"仅选择可覆盖{labels}的工具，避免重复首轮已完成的检索"


def _round_evidence_added(result: AgentRoundResult) -> list[str]:
    counts = Counter(item.tool_name for item in result.evidence)
    return [f"{tool_name}：{count} 条" for tool_name, count in counts.items()]


def _round_judgment_basis(
    result: AgentRoundResult,
    missing_before: list[EvidenceRequirement],
    missing_after: list[EvidenceRequirement],
) -> list[str]:
    missing_after_keys = {item.key for item in missing_after}
    satisfied = [
        item.label for item in missing_before if item.key not in missing_after_keys
    ]
    basis = [f"本轮新增 {len(result.evidence)} 条有效工具证据"]
    if satisfied:
        basis.append(f"本轮满足证据维度：{'、'.join(satisfied)}")
    if missing_after:
        basis.append(f"仍缺少证据维度：{'、'.join(item.label for item in missing_after)}")
    else:
        basis.append("全部证据维度已满足")
    return basis


def _round_next_step(
    missing: list[EvidenceRequirement],
    *,
    can_continue: bool,
    made_progress: bool,
) -> str:
    if not missing:
        return "证据维度已满足，结束自适应调研"
    labels = "、".join(item.label for item in missing)
    if not made_progress and not can_continue:
        return f"本轮未缩小证据缺口，停止空转并记录数据缺口：{labels}"
    if can_continue:
        return f"下一轮聚焦补齐：{labels}"
    return f"已达到最大轮次，记录数据缺口：{labels}"


async def _emit_round_started(
    progress: _ResearchProgress,
    *,
    round_index: int,
    round_total: int,
    requirements: list[EvidenceRequirement],
    tool_names: tuple[str, ...],
) -> AgentResearchRound:
    research_round = AgentResearchRound(
        round_index=round_index,
        round_total=round_total,
        status="running",
        objective=_round_objective(round_index, requirements),
        evidence_gaps=[item.label for item in requirements],
        tool_names=list(tool_names),
        tool_selection_reason=_round_tool_selection_reason(round_index, requirements),
    )
    await progress.emit(AgentEvent(
        type="round_started",
        research_round=research_round,
    ))
    return research_round


async def _emit_round_completed(
    progress: _ResearchProgress,
    started: AgentResearchRound,
    result: AgentRoundResult,
    missing_before: list[EvidenceRequirement],
    missing_after: list[EvidenceRequirement],
    *,
    can_continue: bool,
    made_progress: bool,
) -> None:
    await progress.emit(AgentEvent(
        type="round_completed",
        research_round=started.model_copy(update={
            "status": (
                "completed"
                if not missing_after or (can_continue and made_progress)
                else "degraded"
            ),
            "evidence_gaps": [item.label for item in missing_after],
            "evidence_added": _round_evidence_added(result),
            "judgment_basis": _round_judgment_basis(
                result, missing_before, missing_after
            ),
            "conclusion": result.summary.strip()[:2000],
            "next_step": _round_next_step(
                missing_after,
                can_continue=can_continue,
                made_progress=made_progress,
            ),
        }),
    ))


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
    round_callback = progress.forward_event

    max_rounds = max(1, spec.max_rounds)
    initial_requirements = list(spec.requirements)

    async with runtime.open_session(spec, settings=settings) as session:
        first_round = await _emit_round_started(
            progress,
            round_index=1,
            round_total=max_rounds,
            requirements=initial_requirements,
            tool_names=spec.tool_names,
        )
        last_result = await _run_round(
            session,
            message,
            spec.tool_names,
            round_callback,
            tool_call_reserve=_FOLLOWUP_TOOL_CALL_RESERVE if max_rounds > 1 else 0,
        )
        await _collect_round_result(last_result, evidence, summaries, progress)

        missing = _missing_requirements(spec.requirements, evidence)
        await _emit_round_completed(
            progress,
            first_round,
            last_result,
            initial_requirements,
            missing,
            can_continue=bool(missing and max_rounds > 1),
            made_progress=bool(last_result.evidence),
        )
        current_round = 2

        while missing and current_round <= max_rounds:
            missing_before = list(missing)
            missing_count_before = len(missing_before)
            await progress.emit(AgentEvent(
                type="status",
                content=f"第 {current_round - 1} 轮证据仍缺少 {'、'.join(item.label for item in missing_before)}，正在进行第 {current_round} 轮自适应补充调研…",
            ))
            allowed_tools = _gap_tool_names(spec, missing_before)
            started_round = await _emit_round_started(
                progress,
                round_index=current_round,
                round_total=max_rounds,
                requirements=missing_before,
                tool_names=allowed_tools,
            )
            gap_result = await _run_round(
                session,
                _build_gap_message(
                    message,
                    last_result,
                    evidence,
                    missing_before,
                    round_index=current_round,
                ),
                allowed_tools,
                round_callback,
                tool_call_reserve=(
                    _FOLLOWUP_TOOL_CALL_RESERVE if current_round < max_rounds else 0
                ),
            )
            await _collect_round_result(gap_result, evidence, summaries, progress)
            last_result = gap_result
            missing = _missing_requirements(spec.requirements, evidence)
            made_progress = len(missing) < missing_count_before
            can_continue = bool(
                missing and made_progress and current_round < max_rounds
            )
            await _emit_round_completed(
                progress,
                started_round,
                gap_result,
                missing_before,
                missing,
                can_continue=can_continue,
                made_progress=made_progress,
            )

            # 若本轮未获取到任何新的补充证据，说明剩余维度无法通过现有工具继续获取，适时停止避免空转
            if not made_progress:
                break
            current_round += 1

    missing = _missing_requirements(spec.requirements, evidence)
    fatal_missing = [item for item in missing if item.fatal]
    degraded_missing = [item for item in missing if not item.fatal]
    if fatal_missing:
        await progress.mark_failed(fatal_missing)
    if degraded_missing:
        await progress.mark_degraded(degraded_missing)
    if fatal_missing:
        labels = "、".join(item.label for item in fatal_missing)
        raise AgentEvidenceInsufficientError(f"Agent 调研证据不足：{labels}")
    if missing:
        await progress.emit(AgentEvent(
            type="status",
            content=(
                f"未能核验 {'、'.join(item.label for item in missing)}，"
                "将按证据不足降级生成并记录数据缺口。"
            ),
        ))

    await progress.emit(AgentEvent(type="done"))

    return AgenticResearchResult(
        summary="\n\n".join(summaries)[:MAX_AGENT_SUMMARY_LENGTH],
        evidence=tuple(evidence),
        evidence_gaps=tuple(item.label for item in missing),
        execution_trace=tuple(progress.audit_events),
    )
