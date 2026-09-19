from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Mapping
from dataclasses import dataclass

from app.agentic.agents.contracts import AgentExecutionResult, AgentProfile
from app.agentic.agents.executor import agent_executor
from app.agentic.events import AgentEvent
from app.agentic.orchestration.contracts import AgentTask, ExecutionPlan
from app.agentic.orchestration.progress import build_task_progress_event
from app.agentic.protocol import AgentMessage
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.tools.cache import SharedToolCache
from app.core.errors import log_internal_error
from app.core.exceptions import UpstreamUnavailableError
from app.infrastructure.llm.tool_calling import AsyncLLMClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _TaskCompleted:
    task_id: str
    result: AgentExecutionResult


def _build_task_message(
    task: AgentTask,
    message: str,
    task_results: Mapping[str, AgentExecutionResult],
) -> str:
    dependency_results = [
        task_results[dependency]
        for dependency in task.dependencies
        if dependency in task_results
    ]
    if not dependency_results:
        return message
    context = "\n\n".join(
        f"### {result.display_name}\n{result.analysis}"
        for result in dependency_results
    )
    return (
        f"{message}\n\n"
        f"## 已完成的前置分析\n{context}\n\n"
        f"## 当前任务\n{task.objective}"
    )


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
) -> AsyncGenerator[AgentEvent, None]:
    queue: asyncio.Queue[AgentEvent | _TaskCompleted] = asyncio.Queue()
    tool_cache = (
        execution_context.tool_cache
        if execution_context is not None
        else SharedToolCache()
    )
    pending = {task.task_id: task for task in plan.tasks}
    running: dict[str, asyncio.Task] = {}
    completed: set[str] = set()
    task_results: dict[str, AgentExecutionResult] = {}

    async def run_one(task: AgentTask) -> None:
        profile = agents[task.agent_name]
        await queue.put(build_task_progress_event(task, "running", attempt=attempt))
        await queue.put(AgentEvent(type="status", content=f"{task.display_name}处理中…"))
        try:
            result = await agent_executor.run(
                profile,
                _build_task_message(task, message, task_results),
                history,
                llm_client,
                model,
                event_queue=queue,
                tool_cache=tool_cache,
                allowed_tool_names=task.allowed_tools,
                temperature=temperature,
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
            )
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
                    "completed",
                    detail=detail,
                    attempt=attempt,
                )
            )
            status_content = f"{task.display_name}已完成…"
        await queue.put(AgentEvent(type="status", content=status_content))
        await queue.put(_TaskCompleted(task_id=task.task_id, result=result))

    try:
        while pending or running:
            ready = [
                task
                for task in pending.values()
                if set(task.dependencies) <= completed
            ]
            for task in ready:
                pending.pop(task.task_id)
                running[task.task_id] = asyncio.create_task(run_one(task))

            if not running:
                raise RuntimeError("执行计划没有可运行任务")

            event = await queue.get()
            if isinstance(event, _TaskCompleted):
                finished_task = running.pop(event.task_id)
                await finished_task
                completed.add(event.task_id)
                task_results[event.task_id] = event.result
                results[event.result.agent_name] = event.result
                continue
            yield event
    finally:
        for running_task in running.values():
            if not running_task.done():
                running_task.cancel()
        await asyncio.gather(*running.values(), return_exceptions=True)
