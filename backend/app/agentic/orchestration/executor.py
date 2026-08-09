from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Mapping
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.agentic.agents.contracts import AgentExecutionResult, AgentProfile
from app.agentic.agents.executor import SharedToolCache, agent_executor
from app.agentic.events import AgentEvent
from app.agentic.orchestration.contracts import AgentTask, ExecutionPlan
from app.agentic.orchestration.progress import build_task_progress_event
from app.agentic.protocol import AgentMessage
from app.core.errors import log_internal_error

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
    llm_client: AsyncOpenAI,
    model: str,
    results: dict[str, AgentExecutionResult],
    temperature: float = 0.1,
    *,
    attempt: int = 1,
) -> AsyncGenerator[AgentEvent, None]:
    queue: asyncio.Queue[AgentEvent | _TaskCompleted] = asyncio.Queue()
    tool_cache = SharedToolCache()
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
            )
        except asyncio.CancelledError:
            raise
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
        for task in running.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(*running.values(), return_exceptions=True)
