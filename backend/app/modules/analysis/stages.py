"""个股分析各阶段的业务执行函数。"""

from __future__ import annotations

from typing import Any

from app.agentic.public import AgentEventCallback
from app.configuration.schema import Settings
from app.core.market import is_hk_code
from app.infrastructure.llm.policy import generation_scope
from app.infrastructure.llm.prompting import run_structured_prompt
from app.infrastructure.llm.streaming import streaming_llm_client
from app.modules.analysis import research as analysis_research
from app.modules.analysis.models import AnalysisResult
from app.modules.analysis.prompts import ANALYSIS_PROMPT_SPEC, apply_evidence_gap_degradation


async def research_stock(
    code: str,
    analysis_date: str,
    settings: Settings,
    event_callback: AgentEventCallback | None = None,
):
    return await analysis_research.research_stock(
        code,
        analysis_date,
        settings=settings,
        event_callback=event_callback,
    )


def build_prompt_context(code: str, analysis_date: str, research: Any) -> dict[str, Any]:
    return {
        "stock_code": code,
        "analysis_date": analysis_date,
        "market": "hk" if is_hk_code(code) else "cn",
        **research.render_prompt_context(),
    }


async def generate_analysis_result(
    code: str,
    prompt_context: dict[str, Any],
    settings: Settings,
) -> AnalysisResult:
    timeout = settings.analysis_llm_timeout_seconds
    report_settings = settings.model_copy(update={"llm_timeout_seconds": min(settings.llm_timeout_seconds, timeout)})
    async with generation_scope(report_settings, timeout_seconds=timeout, label="模型报告生成"):
        async with streaming_llm_client(
            report_settings, max_tokens=settings.analysis_llm_max_completion_tokens,
        ) as client:
            prompt_run = await run_structured_prompt(
                ANALYSIS_PROMPT_SPEC,
                prompt_context,
                settings=report_settings,
                async_client=client,
                timeout_seconds=timeout,
                temperature=settings.llm_temperature,
            )
    gap_labels = tuple(
        str(item)
        for item in prompt_context.get("agent_evidence_gap_labels", ())
        if str(item).strip()
    )
    prompt_value = apply_evidence_gap_degradation(prompt_run.value, gap_labels)
    result = AnalysisResult.model_validate(
        {
            **prompt_value.model_dump(),
            "prompt_trace": prompt_run.trace,
        }
    )
    if result.stock_code != code:
        return result.model_copy(update={"stock_code": code})
    return result


__all__ = ["build_prompt_context", "generate_analysis_result", "research_stock"]
