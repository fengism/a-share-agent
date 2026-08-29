"""个股分析各阶段的业务执行函数。"""

from __future__ import annotations

from typing import Any

from app.agentic.public import AgentEventCallback
from app.configuration.schema import Settings
from app.infrastructure.llm.prompting import run_structured_prompt
from app.infrastructure.llm.sync_client import create_llm_client
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
        **research.render_prompt_context(),
    }


async def generate_analysis_result(
    code: str,
    prompt_context: dict[str, Any],
    settings: Settings,
) -> AnalysisResult:
    prompt_run = await run_structured_prompt(
        ANALYSIS_PROMPT_SPEC,
        prompt_context,
        settings=settings,
        client=create_llm_client(settings),
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
