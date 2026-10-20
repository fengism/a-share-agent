"""LLM 调用失败时的六条出口。

这段（executor.py 的 ``except Exception`` 块）此前完全没有覆盖，而它是「用户到底
看到什么」的唯一决定点：同一个上游故障，在 require_tool_evidence 打开/关闭、流式/
非流式、连接类/格式类/超时类下会走向六个不同分支。搞错一个，根因就会被伪装成
「调研证据不足」，把排查引到完全错误的方向。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.agentic.agents.contracts import AgentProfile
from app.agentic.agents.executor import AgentExecutor
from app.agentic.catalog import registry
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.tools.contracts import ToolPolicy
from app.configuration import get_settings
from app.domain.errors import UpstreamUnavailableError
from app.domain.llm import LLMGenerationTimeoutError, LLMInvalidResponseError

_TOOL = "fail_tool"
_DEFINITION = {
    "type": "function",
    "function": {
        "name": _TOOL,
        "description": "d",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


class _ConnectionError(Exception):
    """openai/litellm 的连接类异常按类名识别，不需要真的依赖 SDK。"""


_ConnectionError.__name__ = "APIConnectionError"


class _RaisingCompletions:
    def __init__(self, exc: BaseException) -> None:
        self._exc = exc
        self.calls = 0

    async def __call__(self, client, **kwargs):
        self.calls += 1
        raise self._exc


def _profile() -> AgentProfile:
    return AgentProfile(
        name="fail-agent",
        display_name="失败",
        description="d",
        system_prompt="s",
        tool_names=(_TOOL,),
        max_rounds=3,
    )


def _install(monkeypatch, exc: BaseException) -> _RaisingCompletions:
    completions = _RaisingCompletions(exc)
    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", completions)
    monkeypatch.setattr(registry, "get_tool_definitions_for", lambda names: [_DEFINITION])
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: ToolPolicy(cache_ttl_seconds=0))
    monkeypatch.setattr(registry, "get_tool", lambda name: None)
    return completions


async def _run(**kwargs) -> Any:
    return await AgentExecutor().run(
        _profile(),
        "问题",
        None,
        object(),
        "m",
        execution_context=AgentExecutionContext(settings=get_settings()),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_evidence_required_without_evidence_degrades_to_gap_report(monkeypatch):
    """需要证据却没拿到时，不能把 LLM 故障直接抛给用户，要给出取证缺口说明。

    注意终止原因：这里**保留**真实根因（generation_error），只有原本没有具体原因
    （""/stop/tool_calls）时才降级成 insufficient_evidence。否则监控会把一次网关
    故障统计成「取证不足」，把排查引到错误方向。
    """
    _install(monkeypatch, RuntimeError("boom"))

    result = await _run(require_tool_evidence=True)

    assert result.status == "failed"
    assert result.termination_reason == "generation_error"
    assert any("未获取有效工具证据" in error for error in result.errors)
    # 根因不是「证据不足」，所以不该被上游当作可重试的取证失败。
    assert result.retryable is False


@pytest.mark.asyncio
async def test_generation_timeout_keeps_its_own_termination_reason(monkeypatch):
    """超时不是「证据不足」：终止原因必须保留，否则监控会把容量问题看成取证问题。"""
    _install(monkeypatch, LLMGenerationTimeoutError("生成超时"))

    result = await _run(require_tool_evidence=True)

    assert result.termination_reason == "generation_timeout"
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_generation_timeout_is_reraised_when_evidence_not_required(monkeypatch):
    _install(monkeypatch, LLMGenerationTimeoutError("生成超时"))

    with pytest.raises(LLMGenerationTimeoutError):
        await _run(require_tool_evidence=False)


@pytest.mark.asyncio
async def test_connection_failure_becomes_a_retryable_upstream_error(monkeypatch):
    """网关不可达是可重试的上游故障，不能被包装成业务失败。"""
    _install(monkeypatch, _ConnectionError("connection refused"))

    with pytest.raises(UpstreamUnavailableError) as excinfo:
        await _run(require_tool_evidence=False)

    assert "LLM 服务连接失败" in str(excinfo.value)


@pytest.mark.asyncio
async def test_invalid_response_is_not_retryable(monkeypatch):
    """响应格式不对是配置问题，重试只会重复失败。"""
    _install(monkeypatch, LLMInvalidResponseError("bad payload"))

    result = await _run(require_tool_evidence=False)

    assert result.status == "failed"
    assert result.retryable is False
    assert result.termination_reason == "invalid_response"
    assert "格式异常" in result.analysis


@pytest.mark.asyncio
async def test_generic_failure_reports_the_detail_as_analysis(monkeypatch):
    _install(monkeypatch, RuntimeError("boom"))

    result = await _run(require_tool_evidence=False)

    assert result.status == "failed"
    assert result.retryable is False
    assert result.analysis
    assert result.termination_reason == "generation_error"


@pytest.mark.asyncio
async def test_streaming_failure_emits_an_error_event(monkeypatch):
    """流式模式下失败必须发事件：否则前端只看到「没有任何输出」。"""
    _install(monkeypatch, RuntimeError("boom"))
    events = []

    async def drain() -> None:
        async for event in AgentExecutor().stream(
            _profile(),
            "问题",
            None,
            object(),
            "m",
            execution_context=AgentExecutionContext(settings=get_settings()),
        ):
            events.append(event)

    await drain()

    assert [event.type for event in events].count("error") == 1
    assert events[-1].type == "done"


@pytest.mark.asyncio
async def test_rate_limit_status_code_is_classified(monkeypatch):
    """429 要走 rate_limited，而不是笼统的 generation_error。"""

    class _RateLimited(RuntimeError):
        status_code = 429

    _install(monkeypatch, _RateLimited("slow down"))

    result = await _run(require_tool_evidence=False)

    assert result.termination_reason == "rate_limited"


@pytest.mark.asyncio
async def test_answer_without_evidence_is_marked_insufficient(monkeypatch):
    """没有异常、但要求证据却一次工具都没调：这才是真正的「取证不足」。"""
    calls = {"n": 0}

    async def no_tool_answer(client, **kwargs):
        calls["n"] += 1
        return {"choices": [{"message": {"content": "我觉得不错", "tool_calls": []},
                             "finish_reason": "stop"}]}

    monkeypatch.setattr("app.agentic.agents.executor.create_chat_completion", no_tool_answer)
    monkeypatch.setattr(registry, "get_tool_definitions_for", lambda names: [_DEFINITION])
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: ToolPolicy(cache_ttl_seconds=0))
    monkeypatch.setattr(registry, "get_tool", lambda name: None)

    result = await _run(require_tool_evidence=True, require_tool_first_round=False)

    assert result.status == "failed"
    assert result.termination_reason == "insufficient_evidence"
    assert result.analysis == ""
    assert any("未获取有效工具证据" in error for error in result.errors)
