"""流式分支：正文增量过滤、流中断的抢救与安全边界。

这段此前完全没覆盖，而它决定两件事：
1. 不可撤回的流式正文里能不能出现工具调用标记（出现过真实事故）；
2. 流在收到终止帧之前断掉时，**绝不能**执行半截 tool_calls——参数可能是不完整的 JSON，
   按它去查数据等于拿模型幻觉当输入。
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
from app.domain.llm import LLMRetryableError

_TOOL = "stream_tool"
_DEFINITION = {
    "type": "function",
    "function": {
        "name": _TOOL,
        "description": "d",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


def _chunk(content: str = "", *, finish: str | None = None, tool_calls: Any = None) -> dict:
    delta: dict[str, Any] = {}
    if content:
        delta["content"] = content
    if tool_calls is not None:
        delta["tool_calls"] = tool_calls
    payload: dict[str, Any] = {"choices": [{"delta": delta}]}
    if finish is not None:
        payload["choices"][0]["finish_reason"] = finish
    return payload


def _tool_call_delta(index: int = 0) -> list[dict]:
    return [{
        "index": index,
        "id": f"call_{index}",
        "type": "function",
        "function": {"name": _TOOL, "arguments": "{}"},
    }]


def _profile() -> AgentProfile:
    return AgentProfile(
        name="stream-agent",
        display_name="流式",
        description="d",
        system_prompt="s",
        tool_names=(_TOOL,),
        max_rounds=2,
    )


def _install(monkeypatch, chunks: list[dict], *, fail_after: int | None = None) -> list[str]:
    executed: list[str] = []

    async def fake_stream(*args, **kwargs):
        for index, chunk in enumerate(chunks):
            if fail_after is not None and index >= fail_after:
                raise LLMRetryableError("upstream hiccup")
            yield chunk

    async def fake_execute(call, allowed_names=None, execution_context=None, arguments=None):
        executed.append(call.id)
        from app.agentic.protocol import ToolResultInfo

        return ToolResultInfo(
            tool_call_id=call.id, name=call.function.name, content='{"ok":true,"data":{"v":1}}',
        )

    monkeypatch.setattr("app.agentic.agents.executor.stream_chat_completion", fake_stream)
    monkeypatch.setattr(registry, "get_tool_definitions_for", lambda names: [_DEFINITION])
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: ToolPolicy(cache_ttl_seconds=0))
    monkeypatch.setattr(registry, "get_tool", lambda name: None)
    monkeypatch.setattr(registry, "execute_tool", fake_execute)
    return executed


async def _run_stream() -> tuple[list, Any]:
    events = []

    async def drain():
        async for event in AgentExecutor().stream(
            _profile(),
            "问题",
            None,
            object(),
            "m",
            execution_context=AgentExecutionContext(settings=get_settings()),
            require_tool_first_round=False,
        ):
            events.append(event)

    await drain()
    return events, events[-1] if events else None


def _text(events: list) -> str:
    return "".join(event.content for event in events if event.type == "text")


@pytest.mark.asyncio
async def test_normal_stream_publishes_text_and_finishes(monkeypatch):
    _install(monkeypatch, [
        _chunk("结论："),
        _chunk("估值合理。", finish="stop"),
    ])

    events, last = await _run_stream()

    assert "结论：" in _text(events)
    assert last.type == "done"


@pytest.mark.asyncio
async def test_tool_markup_never_reaches_the_stream(monkeypatch):
    """模型把工具调用写成正文标记时，不能推给用户（真实事故：用户收到一串 DSML）。"""
    _install(monkeypatch, [
        _chunk('<|DSML|invoke name="get_stock_kline">{"code":"600519"}</|DSML|invoke>'),
        _chunk("最终结论。", finish="stop"),
    ])

    events, last = await _run_stream()

    published = _text(events)
    assert "DSML" not in published
    assert "最终结论" in published
    assert last.type == "done"


@pytest.mark.asyncio
async def test_stream_eof_without_terminal_frame_never_executes_tools(monkeypatch):
    """没有终止帧就断流：半截 tool_calls 一律不执行，按 stream_error 收尾。"""
    executed = _install(monkeypatch, [
        _chunk("我先查一下。"),
        _chunk(tool_calls=_tool_call_delta()),  # 没有任何 finish_reason
    ])

    events, last = await _run_stream()

    assert executed == []
    assert last.type == "done"


@pytest.mark.asyncio
async def test_retryable_error_after_clean_text_is_salvaged(monkeypatch):
    """已经产出可读结论时，上游抖动应当保住这段正文而不是整轮失败。"""
    _install(
        monkeypatch,
        [_chunk("结论：估值合理。")],
        fail_after=1,
    )

    events, last = await _run_stream()

    assert "估值合理" in _text(events)
    assert last.type == "done"


async def _fast_sleep(*_args, **_kwargs):
    pass


@pytest.mark.asyncio
async def test_retryable_error_without_text_fails_loudly(monkeypatch):
    """一个字都没产出时必须报错，不能静默结束成空回答。"""
    monkeypatch.setattr("asyncio.sleep", _fast_sleep)
    _install(monkeypatch, [], fail_after=0)

    events, last = await _run_stream()

    assert any(event.type == "error" for event in events)
    assert last.type == "done"


@pytest.mark.asyncio
async def test_stream_interruption_retries_and_succeeds(monkeypatch):
    """流式生成中途中断（如 upstream SSE stream ended），重试后成功输出最终答案。"""
    monkeypatch.setattr("asyncio.sleep", _fast_sleep)
    stream_calls = 0

    async def flaky_stream(*args, **kwargs):
        nonlocal stream_calls
        stream_calls += 1
        if stream_calls == 1:
            yield {"choices": [{"delta": {"reasoning_content": "尝试1的思考片段"}, "index": 0}]}
            raise LLMRetryableError("upstream SSE stream ended before a terminal event")
        yield {"choices": [{"delta": {"reasoning_content": "尝试2的思考片段"}, "index": 0}]}
        yield _chunk("结论：重试后成功产出完整分析。", finish="stop")

    monkeypatch.setattr("app.agentic.agents.executor.stream_chat_completion", flaky_stream)
    monkeypatch.setattr(registry, "get_tool_definitions_for", lambda names: [_DEFINITION])
    monkeypatch.setattr(registry, "get_tool_policy", lambda name: ToolPolicy(cache_ttl_seconds=0))
    monkeypatch.setattr(registry, "get_tool", lambda name: None)

    events, last = await _run_stream()

    assert stream_calls == 2
    assert "重试后成功产出完整分析" in _text(events)
    assert last.type == "done"

    # 验证两次尝试的思考块具有独立的 block_id 与 attempt，中间有重试状态通知
    reasoning_events = [e for e in events if e.type == "reasoning"]
    assert len(reasoning_events) == 2
    first_block = reasoning_events[0].reasoning_source
    second_block = reasoning_events[1].reasoning_source
    assert first_block is not None and second_block is not None
    assert first_block.block_id != second_block.block_id
    assert first_block.attempt == 1
    assert second_block.attempt == 2
    assert any("正在重试" in (e.content or "") for e in events if e.type == "status")


def test_normalize_sse_stream_ended_error():
    """验证 OpenAI/第三方兼容网关的 SSE 异常流中断被准确归一化为可重试上游错误。"""
    from openai import APIError
    from app.infrastructure.llm.adapters import normalize_retryable_llm_error
    from app.domain.llm import LLMUpstreamResponseError

    err = APIError("upstream SSE stream ended before a terminal event", request=None, body=None)
    normalized = normalize_retryable_llm_error(err)
    assert isinstance(normalized, LLMUpstreamResponseError)
