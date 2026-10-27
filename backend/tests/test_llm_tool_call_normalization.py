"""LLM 响应归一化：legacy ``function_call`` 与 Azure 端点识别。

两条都是"静默失效"类问题：老网关只回 ``message.function_call``（OpenAI tools 之前
的协议）时，此前被完全丢弃——模型等于调了工具但什么也没发生；Azure 侧只认
``.openai.azure.com``，中国区与新版 AI Services 端点会被误判成非官方通道。
"""

from __future__ import annotations

import pytest

from app.configuration.provider_catalog import PROVIDER_DEFAULTS
from app.domain.agent_llm import (
    ChatCompletionStreamNormalizer,
    normalize_chat_completion,
)
from app.infrastructure.llm.capabilities import resolve_llm_capabilities


def _azure(base_url: str):
    defaults = PROVIDER_DEFAULTS["azure"]
    return resolve_llm_capabilities(
        provider="azure",
        api_mode=str(defaults["api_mode"]),
        model="azure/gpt-4o",
        base_url=base_url,
        api_version=str(defaults.get("api_version", "")),
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "https://my-resource.openai.azure.com",
        "https://my-resource.openai.azure.cn",
        "https://my-resource.services.ai.azure.com",
        "https://my-resource.cognitiveservices.azure.com",
    ],
)
def test_azure_sovereign_and_new_endpoints_are_official(base_url: str) -> None:
    capabilities = _azure(base_url)
    assert capabilities.streaming_tool_calls is True
    assert capabilities.parallel_tool_calls is True
    assert capabilities.supports_named_tool_choice is True


@pytest.mark.parametrize(
    "base_url",
    [
        "https://my-resource.openai.azure.com.evil.com",
        "https://notazure.example.com",
        "http://my-resource.openai.azure.com",
    ],
)
def test_azure_lookalike_endpoints_stay_non_official(base_url: str) -> None:
    capabilities = _azure(base_url)
    assert capabilities.streaming_tool_calls is False
    assert capabilities.supports_named_tool_choice is False


def test_legacy_function_call_becomes_tool_calls() -> None:
    turn = normalize_chat_completion({
        "choices": [{
            "message": {
                "content": "",
                "function_call": {"name": "get_quote", "arguments": '{"code":"600519"}'},
            },
            "finish_reason": "function_call",
        }],
    })
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].function.name == "get_quote"
    assert turn.tool_calls[0].function.arguments == '{"code":"600519"}'


def test_native_tool_calls_win_over_legacy_field() -> None:
    turn = normalize_chat_completion({
        "choices": [{
            "message": {
                "content": "",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "native_tool", "arguments": "{}"},
                }],
                "function_call": {"name": "legacy_tool", "arguments": "{}"},
            },
            "finish_reason": "tool_calls",
        }],
    })
    assert [call.function.name for call in turn.tool_calls] == ["native_tool"]


def test_legacy_function_call_without_name_is_ignored() -> None:
    """名称缺失不能造出一个注定失败的工具调用。"""
    turn = normalize_chat_completion({
        "choices": [{
            "message": {"content": "", "function_call": {"arguments": "{}"}},
            "finish_reason": "function_call",
        }],
    })
    assert turn.tool_calls == ()


def test_legacy_streaming_function_call_accumulates_fragments() -> None:
    """流式分片只带参数片段（不含 name），必须逐片合并。"""
    normalizer = ChatCompletionStreamNormalizer()
    normalizer.add({"choices": [{"delta": {"function_call": {"name": "get_quote", "arguments": '{"code":'}}}]})
    normalizer.add({"choices": [{"delta": {"function_call": {"arguments": '"600519"}'}}}]})
    normalizer.add({"choices": [{"delta": {}, "finish_reason": "function_call"}]})

    turn = normalizer.finish()
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].function.name == "get_quote"
    assert turn.tool_calls[0].function.arguments == '{"code":"600519"}'
