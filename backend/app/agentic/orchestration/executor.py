from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable, Mapping
from dataclasses import dataclass, replace

from app.agentic.agents.contracts import AgentExecutionResult, AgentProfile
from app.agentic.agents.executor import agent_executor
from app.agentic.catalog import registry
from app.agentic.events import AgentEvent
from app.agentic.orchestration.contracts import AgentTask, ExecutionPlan
from app.agentic.orchestration.progress import build_task_progress_event
from app.agentic.orchestration.reviewer import is_usable_task_result
from app.agentic.protocol import AgentMessage
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.runtime.metrics import metrics
from app.agentic.runtime.settings import get_default_settings
from app.agentic.tools.cache import SharedToolCache
from app.domain.agent_llm import AsyncLLMClient
from app.domain.errors import UpstreamUnavailableError, log_internal_error
from app.domain.llm import is_llm_failure

logger = logging.getLogger(__name__)

# Dependency analyses are prepended to the task message, which is not covered by
# build_messages()' history compaction. Keep a bounded, fairly shared budget so
# two long upstream reports cannot crowd out the current task and tool evidence.
_MAX_DEPENDENCY_CONTEXT_CHARACTERS = 24_000
_DEPENDENCY_TRUNCATION_MARKER = "\n…（前置分析已按上下文预算截断）"
# 子任务消息里给 system prompt、Skill 规则、任务目标与工具结果预留的空间。
_PROMPT_RESERVED_CHARACTERS = 24_000
_MIN_DEPENDENCY_CONTEXT_CHARACTERS = 2_000


@dataclass(frozen=True, slots=True)
class _TaskCompleted:
    task_id: str
    result: AgentExecutionResult


def _render_dependency_context(
    dependency_results: list[AgentExecutionResult],
    max_characters: int,
) -> str:
    if not dependency_results:
        return ""
    headers = [f"### {result.display_name}\n" for result in dependency_results]
    separator_length = 2 * max(0, len(dependency_results) - 1)
    available = max(0, max_characters - sum(map(len, headers)) - separator_length)
    base_allowance, extra = divmod(available, len(dependency_results))
    parts: list[str] = []
    for index, (header, result) in enumerate(zip(headers, dependency_results)):
        allowance = base_allowance + int(index < extra)
        text = result.analysis
        if len(text) > allowance:
            keep = max(0, allowance - len(_DEPENDENCY_TRUNCATION_MARKER))
            text = (text[:keep] + _DEPENDENCY_TRUNCATION_MARKER)[:allowance]
        parts.append(header + text)
    return "\n\n".join(parts)


def _prompt_budget_for_dependencies(
    execution_context: AgentExecutionContext,
) -> int:
    """把整轮 prompt 上限换算成依赖上下文还能占多少字符。

    子任务消息 = system prompt（含 Skill 规则）+ 前置分析 + 任务目标。只靠
    ``_MAX_DEPENDENCY_CONTEXT_CHARACTERS`` 与 ``chat_max_tool_context_characters``
    两个上限时，``chat_max_prompt_characters`` 对这块完全不生效。
    """
    total_cap = int(
        getattr(execution_context.settings, "chat_max_prompt_characters", 0) or 0
    )
    if total_cap <= 0:
        return _MAX_DEPENDENCY_CONTEXT_CHARACTERS
    # 与执行器保留下限一致：依赖上下文被压到 0 等于让下游在无证据的情况下作答。
    remaining = total_cap - _PROMPT_RESERVED_CHARACTERS
    if remaining >= _MAX_DEPENDENCY_CONTEXT_CHARACTERS:
        return _MAX_DEPENDENCY_CONTEXT_CHARACTERS
    metrics.record_agentic_event("dependency_context_budget_reduced")
    return max(_MIN_DEPENDENCY_CONTEXT_CHARACTERS, remaining)


def _prepend_instruction(prompt: str, instruction: str) -> str:
    """Put a host-supplied directive in front of the Skill rules.

    The directive must come first: the Skill rules are long and the model reads
    the tool-selection prompt top-down.
    """
    if not instruction:
        return prompt
    return "\n\n".join(part for part in (instruction, prompt) if part)


def _build_professional_skill_prompt(
    profile: AgentProfile,
    execution_context: AgentExecutionContext | None,
) -> str:
    """Inject the Skill rules declared by a professional agent's profile.

    Professional sub-agents already receive the tools from their ``skill_names``;
    adding the same rules keeps their tool policy consistent with the general
    agent without going through the dynamic ``load_skill`` path.
    """
    skill_names = tuple(getattr(profile, "skill_names", ()) or ())
    if not skill_names:
        return ""
    settings = (
        execution_context.settings
        if execution_context is not None
        else get_default_settings()
    )
    if not getattr(settings, "chat_agent_skill_instructions_enabled", True):
        return ""
    prompt = registry.get_skill_instructions(skill_names, limit=len(skill_names))
    if prompt:
        metrics.record_agentic_event("agent_skill_instructions_injected")
    return prompt


def _build_task_message(
    task: AgentTask,
    message: str,
    task_results: Mapping[str, AgentExecutionResult],
    *,
    max_dependency_characters: int = _MAX_DEPENDENCY_CONTEXT_CHARACTERS,
) -> str:
    parts = [message]
    dependency_results = [
        task_results[dependency]
        for dependency in task.dependencies
        if dependency in task_results
    ]
    if dependency_results:
        context = _render_dependency_context(dependency_results, max_dependency_characters)
        parts.append(f"## 已完成的前置分析\n{context}")

    if task.repair_context:
        parts.append(
            "## 上一轮分析（本轮需要修复）\n"
            "以下是你上一轮已经给出的分析。其中仍然成立的结论必须保留，不要整段重新推导；"
            "只需补齐缺失的数据证据并修正不成立的结论。\n\n"
            f"{task.repair_context}"
        )

    is_retry_or_special = (
        "修复" in task.objective
        or "上一轮" in task.objective
        or "重试" in task.objective
    )
    if dependency_results or task.repair_context or is_retry_or_special:
        parts.append(f"## 当前任务指示与要求\n{task.objective}")

    return "\n\n".join(parts)


async def stream_execution_plan(
    agents: Mapping[str, AgentProfile],
    plan: ExecutionPlan,
    message: str,
    history: list[AgentMessage] | None,
    llm_client: AsyncLLMClient,
    model: str,
    results: dict[str, AgentExecutionResult],
    temperature: float = 0.1,
    *,
    attempt: int = 1,
    execution_context: AgentExecutionContext | None = None,
    task_instruction: Callable[[AgentTask], str] | None = None,
) -> AsyncGenerator[AgentEvent, None]:
    """Run every pending task of ``plan``.

    ``task_instruction`` lets the host prepend a per-task directive to the tool
    selection prompt (e.g. "resolve this ambiguous target first"). It stays a
    callable so the core never hardcodes host-side tool or product names: the
    host decides which tasks qualify.
    """
    queue: asyncio.Queue[AgentEvent | _TaskCompleted] = asyncio.Queue()
    tool_cache = (
        execution_context.tool_cache
        if execution_context is not None
        else SharedToolCache()
    )
    max_dependency_characters = _MAX_DEPENDENCY_CONTEXT_CHARACTERS
    if execution_context is not None:
        max_dependency_characters = min(
            max_dependency_characters,
            execution_context.settings.chat_max_tool_context_characters,
            _prompt_budget_for_dependencies(execution_context),
        )
    tasks_by_id = {task.task_id: task for task in plan.tasks}
    reuse_ids = set(plan.reuse_task_ids)
    pending = {task.task_id: task for task in plan.tasks if task.task_id not in reuse_ids}
    running: dict[str, asyncio.Task] = {}
    finished = set(reuse_ids)
    task_results = {
        task.task_id: results[task.agent_name]
        for task in plan.tasks
        if task.task_id in reuse_ids and task.agent_name in results
    }
    usable = {
        task_id for task_id, result in task_results.items()
        if is_usable_task_result(tasks_by_id[task_id], result)
    }
    # 先清除本轮待重算的旧结果，防止重试失败或依赖阻塞时泄露陈旧成功状态。
    for task in pending.values():
        results.pop(task.agent_name, None)

    async def run_one(task: AgentTask) -> None:
        await queue.put(build_task_progress_event(task, "running", attempt=attempt))
        await queue.put(AgentEvent(type="status", content=f"{task.display_name}处理中…"))
        try:
            profile = agents[task.agent_name]
            result = await agent_executor.run(
                profile,
                _build_task_message(
                    task, message, task_results,
                    max_dependency_characters=max_dependency_characters,
                ),
                history,
                llm_client,
                model,
                event_queue=queue,
                task_id=task.task_id,
                attempt=attempt,
                tool_cache=tool_cache,
                allowed_tool_names=task.allowed_tools,
                temperature=temperature,
                tool_selection_prompt=_prepend_instruction(
                    _build_professional_skill_prompt(profile, execution_context),
                    task_instruction(task) if task_instruction is not None else "",
                ),
                require_tool_evidence=bool(task.allowed_tools),
                execution_context=execution_context,
            )
        except asyncio.CancelledError:
            raise
        except UpstreamUnavailableError as exc:
            # Agent 层抛出的上游不可用已记完整日志并携带面向用户的文案
            # （如 LLM 连接失败），直接透传，避免二次脱敏掩盖真实原因。
            logger.warning(
                "Agentic task %s 上游不可用: %s",
                task.agent_name,
                exc,
            )
            detail = str(exc)
            result = AgentExecutionResult(
                agent_name=task.agent_name,
                display_name=task.display_name,
                analysis=detail,
                status="failed",
                errors=[detail],
                retryable=not is_llm_failure(exc),
                termination_reason=(
                    "generation_timeout" if isinstance(exc, TimeoutError)
                    else "generation_error" if is_llm_failure(exc) else "execution_error"
                ),
            )
        except Exception as exc:
            _, detail = log_internal_error(
                logger,
                f"Agentic task {task.agent_name}",
                exc,
                f"{task.display_name}暂时不可用",
            )
            result = AgentExecutionResult(
                agent_name=task.agent_name,
                display_name=task.display_name,
                analysis=detail,
                status="failed",
                errors=[detail],
                retryable=not is_llm_failure(exc),
                termination_reason=(
                    "generation_timeout" if isinstance(exc, TimeoutError)
                    else "generation_error" if is_llm_failure(exc) else "execution_error"
                ),
            )
        outcome = result.outcome
        result = replace(result, status=outcome.status,
                         retryable=result.retryable and not outcome.reason.fatal,
                         opinion=None if outcome.status == "failed" else result.opinion)
        if result.status == "failed":
            detail = result.errors[0] if result.errors else f"{task.display_name}执行失败"
            await queue.put(
                build_task_progress_event(
                    task,
                    "failed",
                    detail=detail,
                    attempt=attempt,
                )
            )
            status_content = f"{task.display_name}执行失败…"
        else:
            detail = "部分完成" if result.status == "partial" else "分析完成"
            await queue.put(
                build_task_progress_event(
                    task,
                    "degraded" if result.status == "partial" else "completed",
                    detail=detail,
                    attempt=attempt,
                )
            )
            status_content = f"{task.display_name}{'部分完成' if result.status == 'partial' else '已完成'}…"
        await queue.put(AgentEvent(type="status", content=status_content))
        await queue.put(_TaskCompleted(task_id=task.task_id, result=result))

    try:
        while pending or running:
            ready = [
                task
                for task in pending.values()
                if set(task.dependencies) <= finished
            ]
            for task in ready:
                pending.pop(task.task_id)
                blocked = [dependency for dependency in task.dependencies if dependency not in usable]
                if blocked:
                    names = "、".join(tasks_by_id[dependency].display_name for dependency in blocked)
                    detail = f"前置分析未有效完成（{names}），未执行{task.display_name}"
                    result = AgentExecutionResult(
                        termination_reason="dependency_unavailable",
                        agent_name=task.agent_name,
                        display_name=task.display_name,
                        analysis="",
                        status="failed",
                        errors=[detail],
                        retryable=all(
                            task_results[dependency].retryable
                            for dependency in blocked if dependency in task_results
                        ),
                    )
                    task_results[task.task_id] = result
                    results[task.agent_name] = result
                    finished.add(task.task_id)
                    yield build_task_progress_event(task, "failed", detail=detail, attempt=attempt)
                else:
                    running[task.task_id] = asyncio.create_task(run_one(task))

            # 回收「已结束但没发出 _TaskCompleted」的任务（被取消的，或内部抛了
            # CancelledError 的）。此前它们的 key 会永久留在 running 里：
            # while pending or running 永不退出，生成器空等在 queue.get() 上，整个
            # 请求占满 max_concurrent_chat_total / per_user 两个额度直到外层 300s
            # 超时；而 finished 里也缺它们，依赖它们的 task 永远进不了 ready。
            reconciled = False
            for task_id, running_task in list(running.items()):
                if not running_task.done():
                    continue
                if not (running_task.cancelled() or running_task.exception() is not None):
                    continue  # 正常完成的正在排队等自己的 _TaskCompleted
                running.pop(task_id)
                task = tasks_by_id[task_id]
                result = AgentExecutionResult(
                    agent_name=task.agent_name,
                    display_name=task.display_name,
                    analysis="",
                    status="failed",
                    errors=[f"{task.display_name}执行被中断"],
                    retryable=False,
                )
                task_results[task_id] = result
                results[task.agent_name] = result
                finished.add(task_id)
                reconciled = True
                yield build_task_progress_event(
                    task, "failed", detail="执行被中断", attempt=attempt
                )
            if reconciled:
                # finished 变了，依赖它的任务可能刚变成 ready：重算一轮再决定。
                continue

            if not running:
                if ready:
                    continue
                if pending:
                    # 还有任务没被依赖满足、也没有任何在跑：DAG 无法推进。
                    raise RuntimeError("执行计划没有可运行任务")
                break

            # 等待必须同时被「队列有事件」和「有任务结束」唤醒。run_one 对
            # CancelledError 是原样重抛、不发 _TaskCompleted 的，只等 queue.get()
            # 就会一直挂在上面，直到外层 300s 超时——而这段时间里请求占满了
            # max_concurrent_chat_total / per_user 两个额度。
            getter = asyncio.ensure_future(queue.get())
            try:
                done, _ = await asyncio.wait(
                    [getter, *running.values()],
                    return_when=asyncio.FIRST_COMPLETED,
                )
            finally:
                getter.cancel()
            if getter not in done:
                continue  # 有任务结束了，回循环顶部回收
            event = getter.result()
            if isinstance(event, _TaskCompleted):
                finished_task = running.pop(event.task_id, None)
                if finished_task is not None:
                    await finished_task
                finished.add(event.task_id)
                if is_usable_task_result(tasks_by_id[event.task_id], event.result):
                    usable.add(event.task_id)
                task_results[event.task_id] = event.result
                results[event.result.agent_name] = event.result
                continue
            yield event
    finally:
        for running_task in running.values():
            if not running_task.done():
                running_task.cancel()
        await asyncio.gather(*running.values(), return_exceptions=True)
