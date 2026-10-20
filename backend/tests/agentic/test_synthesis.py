"""综合阶段的输入预算分配与流式出口。

`build_synthesis_input` 是纯预算数学（guidance 占 1/3、覆盖限制 1/4、问题 1/4、其余按
Agent 均分），此前完全没测——分配算错的表现是「某个维度的分析被静默截成半句话」，
而不是报错。`stream_synthesis` 有 8 个出口，其中 3 个是降级路径。
"""

from __future__ import annotations

import pytest

from app.agentic.agents.contracts import AgentExecutionResult
from app.agentic.orchestration.opinions import AgentOpinion
from app.agentic.orchestration.synthesis import (
    _MAX_SYNTHESIS_WARNINGS,
    _SYNTHESIS_FALLBACK_WARNING,
    _SYNTHESIS_INPUT_WARNING,
    _SYNTHESIS_STREAM_INTERRUPTED_WARNING,
    build_synthesis_input,
    stream_synthesis,
)
from app.domain.llm import LLMRetryableError


def _result(name: str, analysis: str = "分析正文", *, status: str = "completed",
            warnings: tuple[str, ...] = (), opinion: AgentOpinion | None = None) -> AgentExecutionResult:
    return AgentExecutionResult(
        agent_name=name, display_name=f"{name}维度", analysis=analysis,
        status=status,  # type: ignore[arg-type]
        warnings=list(warnings), opinion=opinion,
    )


def _results(*names: str, analysis: str = "分析正文") -> dict[str, AgentExecutionResult]:
    return {name: _result(name, analysis) for name in names}


# --- 输入预算 --------------------------------------------------------------


def test_empty_results_still_render_the_question():
    content, truncated = build_synthesis_input("用户问题", {}, max_characters=1_000)
    assert "用户问题" in content
    assert truncated is False


def test_every_analysis_is_kept_when_the_budget_is_generous():
    content, truncated = build_synthesis_input("问题", _results("a", "b"), max_characters=10_000)

    assert "a维度" in content and "b维度" in content
    assert truncated is False
    assert content.count("分析正文") == 2


def test_budget_is_shared_fairly_between_agents():
    long = "字" * 5_000
    content, truncated = build_synthesis_input(
        "问题", _results("a", "b", analysis=long), max_characters=1_000,
    )

    assert truncated is True
    assert len(content) <= 1_000
    assert content.count("字") >= 200, "两个维度都该分到预算，不能被第一个吃光"


def test_remaining_characters_are_distributed_to_the_first_agents():
    """除不尽的余数按顺序各多给 1 个字符，保证总长贴着上限。"""
    content, _ = build_synthesis_input("问题", _results("a", "b", "c"), max_characters=900)
    assert len(content) <= 900


def test_guidance_and_coverage_and_question_have_independent_caps():
    opinion = AgentOpinion(
        agent_name="technical", display_name="技术", signal="bullish",
        confidence=0.8, risk_level="none",
    )
    content, truncated = build_synthesis_input(
        "问" * 5_000,
        {"technical": _result("technical", opinion=opinion)},
        max_characters=800,
        coverage_warnings=("覆盖不足" * 500,),
    )

    assert truncated is True
    assert len(content) <= 800
    assert "Agent 分歧摘要" in content
    assert "分析覆盖限制" in content


def test_tiny_budget_never_produces_a_negative_allowance():
    content, truncated = build_synthesis_input(
        "问题", _results("a", "b", "c", analysis="字" * 5_000), max_characters=1,
    )

    assert truncated is True
    assert content == "" or len(content) <= 256


def test_minimum_budget_is_floored_at_256():
    content, _ = build_synthesis_input("问题", _results("a"), max_characters=1)
    assert len(content) <= 256


# --- 流式出口 --------------------------------------------------------------


class _Stream:
    def __init__(self, chunks: list[dict], error: BaseException | None = None) -> None:
        self._chunks = chunks
        self._error = error

    async def __call__(self, *args, **kwargs):
        for chunk in self._chunks:
            yield chunk
        if self._error is not None:
            raise self._error


def _chunk(content: str = "", finish: str | None = None) -> dict:
    payload: dict = {"choices": [{"delta": {"content": content} if content else {}}]}
    if finish is not None:
        payload["choices"][0]["finish_reason"] = finish
    return payload


async def _collect(monkeypatch, results, chunks, *, error=None, **kwargs) -> list:
    monkeypatch.setattr(
        "app.agentic.orchestration.synthesis.stream_chat_completion",
        _Stream(chunks, error),
    )
    events = []
    async for event in stream_synthesis(
        "问题", results, object(), "m", system_prompt="sys", **kwargs,
    ):
        events.append(event)
    return events


def _text(events: list) -> str:
    return "".join(event.content for event in events if event.type == "text")


@pytest.mark.asyncio
async def test_successful_synthesis_finishes_completed(monkeypatch):
    events = await _collect(monkeypatch, _results("a"), [_chunk("综合结论。"), _chunk("", "stop")])

    assert "综合结论" in _text(events)
    assert events[-1].type == "done"
    assert events[-1].status == "completed"
    assert events[-1].warnings == []


@pytest.mark.asyncio
async def test_truncated_input_is_reported(monkeypatch):
    events = await _collect(
        monkeypatch, _results("a", analysis="字" * 5_000),
        [_chunk("结论。"), _chunk("", "stop")],
        max_input_characters=500,
    )

    assert _SYNTHESIS_INPUT_WARNING in events[-1].warnings
    assert events[-1].status == "partial"


@pytest.mark.asyncio
async def test_stream_interruption_keeps_what_was_published(monkeypatch):
    events = await _collect(
        monkeypatch, _results("a"), [_chunk("已生成的一半。")], error=LLMRetryableError("hiccup"),
    )

    assert "已生成的一半" in _text(events)
    assert _SYNTHESIS_STREAM_INTERRUPTED_WARNING in events[-1].warnings


@pytest.mark.asyncio
async def test_output_with_tool_markup_is_flagged(monkeypatch):
    events = await _collect(
        monkeypatch, _results("a"),
        [_chunk('<|DSML|invoke name="x">{}</|DSML|invoke>'), _chunk("", "stop")],
    )

    assert any("未执行的工具调用标记" in warning for warning in events[-1].warnings)
    assert "DSML" not in _text(events)


@pytest.mark.asyncio
async def test_length_finish_adds_a_warning(monkeypatch):
    events = await _collect(monkeypatch, _results("a"), [_chunk("半句"), _chunk("", "length")])

    assert any("长度" in warning for warning in events[-1].warnings)
    assert events[-1].status == "partial"


@pytest.mark.asyncio
async def test_empty_output_falls_back_to_raw_analyses(monkeypatch):
    events = await _collect(monkeypatch, _results("a", "维度结论"), [_chunk("", "stop")])

    assert _SYNTHESIS_FALLBACK_WARNING in events[-1].warnings
    assert "维度结论" in _text(events)
    assert events[-1].status == "partial"


@pytest.mark.asyncio
async def test_no_usable_output_at_all_reports_failure(monkeypatch):
    events = await _collect(monkeypatch, {}, [_chunk("", "stop")])

    assert any(event.type == "error" for event in events)
    assert events[-1].type == "done"
    assert events[-1].status == "failed"


@pytest.mark.asyncio
async def test_partial_source_gets_a_warning_even_without_other_warnings(monkeypatch):
    events = await _collect(
        monkeypatch,
        {"a": _result("a", status="partial")},
        [_chunk("结论。"), _chunk("", "stop")],
    )

    assert any("未完整完成" in warning for warning in events[-1].warnings)


@pytest.mark.asyncio
async def test_warning_count_is_bounded(monkeypatch):
    results = {
        f"a{index}": _result(f"a{index}", warnings=(f"告警{index}",))
        for index in range(20)
    }
    events = await _collect(monkeypatch, results, [_chunk("结论。"), _chunk("", "stop")])

    assert len(events[-1].warnings) <= _MAX_SYNTHESIS_WARNINGS
