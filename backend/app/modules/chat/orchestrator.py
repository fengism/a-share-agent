from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Collection

from app.agentic.agents.catalog import select_agent_profiles
from app.agentic.agents.contracts import AgentExecutionResult
from app.agentic.bootstrap import register_all_capabilities
from app.agentic.catalog import registry
from app.agentic.events import AgentEvent
from app.agentic.orchestration.contracts import ExecutionPlan
from app.agentic.orchestration.executor import stream_execution_plan
from app.agentic.orchestration.planner import build_execution_plan
from app.agentic.orchestration.progress import (
    build_plan_event,
    build_step_progress_event,
)
from app.agentic.orchestration.reviewer import (
    build_retry_plan,
    review_execution_plan,
)
from app.agentic.orchestration.synthesis import stream_synthesis
from app.agentic.protocol import AgentMessage
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.tools.packs.stock.context import resolve_stock_context
from app.configuration import get_effective_settings
from app.core.metrics import metrics
from app.infrastructure.llm.runtime import borrow_async_openai_chat_runtime
from app.infrastructure.llm.tool_calling import AsyncLLMClient
from app.modules.chat.general_agent import stream_general_agent
from app.modules.chat.prompts import (
    DECISION_SYNTHESIS_PROMPT,
    DECISION_SYNTHESIS_PROMPT_REF,
)
from app.modules.chat.routing import (
    RoutingDecision,
    classify_message,
    classify_with_llm,
    extract_stock_codes,
    is_greeting_message,
    is_url_only_message,
)

logger = logging.getLogger(__name__)

_FAILURE_REASON_ID_SEPARATOR = "（错误编号："


def _summarize_failure_reasons(results: dict[str, AgentExecutionResult]) -> str:
    """全部 Agent 失败时，透出可操作的失败原因而非泛化提示。

    各 Agent 对同一根因（如 LLM 余额不足）的失败文案仅错误编号不同，
    按剥离编号后的文本去重；单一原因时保留编号便于日志关联，多个原因
    时拼接去编号后的要点。
    """
    ordered: list[str] = []
    for result in results.values():
        reason = next((error for error in reversed(result.errors) if error), None)
        if not reason:
            continue
        base = reason.split(_FAILURE_REASON_ID_SEPARATOR)[0]
        if not any(base == existing.split(_FAILURE_REASON_ID_SEPARATOR)[0] for existing in ordered):
            ordered.append(reason)
    if not ordered:
        return "当前分析未生成有效结果，请稍后重试"
    if len(ordered) == 1:
        return ordered[0]
    return "；".join(reason.split(_FAILURE_REASON_ID_SEPARATOR)[0] for reason in ordered)


class Orchestrator:
    def __init__(
        self,
        agent_names: Collection[str] | None = None,
        skill_names: Collection[str] | None = None,
        allowed_tool_names: Collection[str] | None = None,
        require_tool_evidence: bool = False,
        execution_context: AgentExecutionContext | None = None,
    ):
        register_all_capabilities()
        selected_skills = None if skill_names is None else set(skill_names)
        self.skill_names = [
            skill.name
            for skill in registry.list_skills()
            if selected_skills is None or skill.name in selected_skills
        ]
        self.allowed_tool_names = (
            registry.get_tool_names_for_skills(self.skill_names)
            if allowed_tool_names is None
            else list(dict.fromkeys(allowed_tool_names))
        )
        self.sub_agents = select_agent_profiles(agent_names)
        self.require_tool_evidence = require_tool_evidence
        self.execution_context = execution_context

    def _early_general_tool_names(self, message: str) -> list[str] | None:
        # 仅当消息本身就是链接时才走通用 Agent 快速路径；链接+问题的混合消息
        # 交由正常路由，避免专业 Agent 被整体跳过
        if is_url_only_message(message):
            return [
                name
                for name in ("web_search", "fetch_url", "fetch_urls", "analyze_twitter_user")
                if name in self.allowed_tool_names
            ]
        if is_greeting_message(message):
            return []
        return None

    async def _stream_general_response(
        self,
        message: str,
        history: list[AgentMessage] | None,
        tool_names: Collection[str],
    ) -> AsyncGenerator[AgentEvent, None]:
        async for delta in stream_general_agent(
            message,
            history,
            tool_names=tool_names,
            skill_names=self.skill_names,
            require_tool_evidence=self.require_tool_evidence and bool(tool_names),
            execution_context=self.execution_context,
        ):
            yield delta

    async def _refine_decision(
        self,
        message: str,
        decision: RoutingDecision,
        llm_client: AsyncLLMClient,
        model: str,
    ) -> RoutingDecision:
        if not decision.needs_llm_classification:
            return decision
        try:
            refined = await self._llm_classify(message, llm_client, model)
            logger.info("LLM classify: agents=%s", refined.agents)
            return refined
        except Exception as exc:
            logger.warning("LLM classify failed, using all agents: %s", exc)
            return RoutingDecision(
                agents=list(self.sub_agents),
                needs_llm_classification=False,
                reasoning="模型路由失败，回退到全部专业 Agent",
            )

    async def _stream_orchestrated_response(
        self,
        message: str,
        history: list[AgentMessage] | None,
        decision: RoutingDecision,
        llm_client: AsyncLLMClient,
        model: str,
        temperature: float,
        stock_context: str = "",
    ) -> AsyncGenerator[AgentEvent, None]:
        plan = build_execution_plan(
            decision.agents,
            self.sub_agents,
            allowed_tool_names=self.allowed_tool_names,
            reasoning=decision.reasoning,
        )
        if not plan.tasks:
            async for delta in self._stream_general_response(
                message,
                history,
                self.allowed_tool_names,
            ):
                yield delta
            return
        logger.info(
            "Execution plan: tasks=%s, reasoning=%s",
            plan.agent_names,
            plan.reasoning,
        )

        yield build_plan_event(plan)
        yield AgentEvent(type="status", content="正在进行多维度分析…")

        enriched_message = (stock_context + "\n\n" + message) if stock_context else message

        results: dict[str, AgentExecutionResult] = {}
        async for delta in self._run_plan_with_review(
            plan,
            enriched_message,
            history,
            llm_client,
            model,
            results,
            temperature,
        ):
            yield delta

        usable_results = {
            name: result
            for name, result in results.items()
            if result.status != "failed" and result.analysis.strip()
        }
        if not usable_results:
            yield AgentEvent(type="error", error=_summarize_failure_reasons(results))
            yield AgentEvent(type="done", status="failed")
            return

        if len(usable_results) == 1:
            result = next(iter(usable_results.values()))
            yield AgentEvent(type="text", content=result.analysis)
            yield AgentEvent(
                type="done",
                status=result.status,
                warnings=result.warnings,
            )
            return

        yield AgentEvent(type="status", content="正在综合各维度结论…")
        async for event in self._synthesize(
            message,
            usable_results,
            llm_client,
            model,
            temperature,
        ):
            yield event

    async def run(
        self,
        message: str,
        history: list[AgentMessage] | None = None,
        *,
        initial_decision: RoutingDecision | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """多 Agent 编排主流程：路由 → 并发执行子 Agent → 综合分析。"""
        early_tool_names = self._early_general_tool_names(message)
        if early_tool_names is not None:
            async for delta in self._stream_general_response(message, history, early_tool_names):
                yield delta
            return

        decision = initial_decision or self._keyword_classify(message)
        logger.info("Keyword classify: agents=%s", decision.agents)

        if not decision.agents:
            async for delta in self._stream_general_response(
                message,
                history,
                self.allowed_tool_names,
            ):
                yield delta
            return

        settings = (
            self.execution_context.settings
            if self.execution_context is not None
            else get_effective_settings()
        )
        async with borrow_async_openai_chat_runtime(settings) as runtime:
            llm_client = runtime.client
            model = runtime.model
            # 路由精调（一次 LLM 调用）与股票上下文解析（网络请求）并行执行
            decision, stock_context = await asyncio.gather(
                self._refine_decision(message, decision, llm_client, model),
                self._resolve_stocks(message),
            )
            async for delta in self._stream_orchestrated_response(
                message,
                history,
                decision,
                llm_client,
                model,
                settings.llm_temperature,
                stock_context=stock_context,
            ):
                yield delta

    async def _resolve_stocks(self, message: str) -> str:
        try:
            resolved = await resolve_stock_context(message, extract_stock_codes(message))
        except Exception:
            logger.warning("股票上下文解析失败，使用原始消息继续", exc_info=True)
            return ""
        return str(resolved)

    def _keyword_classify(self, message: str) -> RoutingDecision:
        return classify_message(message, self.sub_agents)

    async def _llm_classify(self, message: str, llm_client: AsyncLLMClient, model: str) -> RoutingDecision:
        return await classify_with_llm(message, llm_client, model, self.sub_agents)

    async def _run_sub_agents_streaming(
        self, plan: ExecutionPlan, message: str,
        history: list[AgentMessage] | None,
        llm_client: AsyncLLMClient, model: str,
        results: dict[str, AgentExecutionResult],
        temperature: float = 0.1,
        *,
        attempt: int = 1,
    ) -> AsyncGenerator[AgentEvent, None]:
        async for delta in stream_execution_plan(
            self.sub_agents,
            plan,
            message,
            history,
            llm_client,
            model,
            results,
            temperature,
            attempt=attempt,
            execution_context=self.execution_context,
        ):
            yield delta

    async def _run_plan_with_review(
        self, plan: ExecutionPlan, message: str,
        history: list[AgentMessage] | None,
        llm_client: AsyncLLMClient, model: str,
        results: dict[str, AgentExecutionResult],
        temperature: float = 0.1,
    ) -> AsyncGenerator[AgentEvent, None]:
        async for delta in self._run_sub_agents_streaming(
            plan,
            message,
            history,
            llm_client,
            model,
            results,
            temperature,
        ):
            yield delta

        review = review_execution_plan(plan, results)
        if not review.should_retry:
            return

        logger.warning(
            "Execution plan review requested retry: tasks=%s, issues=%s",
            review.retry_task_ids,
            [issue.reason for issue in review.issues],
        )
        metrics.record_agentic_event("review_retry")
        retry_issues = {
            issue.task_id: issue.reason
            for issue in review.issues
            if issue.retryable
        }
        for task_id in review.retry_task_ids:
            yield build_step_progress_event(
                task_id,
                "failed",
                detail=retry_issues.get(task_id, "任务需要重试"),
            )
        yield AgentEvent(type="status", content="部分分析未完成，正在进行一次重试…")
        retry_plan = build_retry_plan(plan, review)
        async for delta in self._run_sub_agents_streaming(
            retry_plan,
            message,
            history,
            llm_client,
            model,
            results,
            temperature,
            attempt=2,
        ):
            yield delta

        final_review = review_execution_plan(plan, results)
        if final_review.issues:
            logger.warning(
                "Execution plan completed with review issues: %s",
                [issue.reason for issue in final_review.issues],
            )
            for issue in final_review.issues:
                if issue.retryable:
                    yield build_step_progress_event(
                        issue.task_id,
                        "failed",
                        detail=issue.reason,
                        attempt=2,
                    )

    async def _synthesize(self, message: str, results: dict[str, AgentExecutionResult],
                          llm_client: AsyncLLMClient, model: str,
                          temperature: float = 0.1) -> AsyncGenerator[AgentEvent, None]:
        async for event in stream_synthesis(
            message,
            results,
            llm_client,
            model,
            system_prompt=DECISION_SYNTHESIS_PROMPT,
            prompt_ref=DECISION_SYNTHESIS_PROMPT_REF,
            temperature=temperature,
            max_completion_tokens=(
                self.execution_context.settings.chat_max_completion_tokens
                if self.execution_context is not None
                else None
            ),
            max_input_characters=(
                self.execution_context.settings.chat_max_synthesis_characters
                if self.execution_context is not None
                else 60_000
            ),
        ):
            yield event
