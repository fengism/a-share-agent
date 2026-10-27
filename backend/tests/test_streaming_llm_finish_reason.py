"""验证 StreamingLLMClient 在各种模型 finish_reason 与 Token 截断下的健壮性。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.infrastructure.llm.adapters import LLMInvalidResponseError
from app.infrastructure.llm.streaming import StreamingLLMClient


async def _mock_stream(chunks):
    for c in chunks:
        yield c


@pytest.mark.asyncio
async def test_streaming_client_accepts_standard_stop():
    chunks = [
        {"choices": [{"delta": {"content": '{"ok": '}}]},
        {"choices": [{"delta": {"content": "true}"}, "finish_reason": "stop"}]},
    ]
    with patch("app.infrastructure.llm.streaming.stream_chat_completion", return_value=_mock_stream(chunks)):
        client = StreamingLLMClient(AsyncMock(), "test-model", max_tokens=1000)
        res = await client.chat_result([{"role": "user", "content": "hi"}], json_format=True)
        assert res.text == '{"ok": true}'
        assert res.finish_reason == "stop"


@pytest.mark.asyncio
async def test_streaming_client_accepts_end_turn_and_eos():
    for reason in ("end_turn", "eos", "stop_sequence"):
        chunks = [
            {"choices": [{"delta": {"content": '{"test": 1}'}, "finish_reason": reason}]},
        ]
        with patch("app.infrastructure.llm.streaming.stream_chat_completion", return_value=_mock_stream(chunks)):
            client = StreamingLLMClient(AsyncMock(), "test-model", max_tokens=1000)
            res = await client.chat_result([{"role": "user", "content": "hi"}], json_format=True)
            assert res.text == '{"test": 1}'
            assert res.finish_reason == reason


@pytest.mark.asyncio
async def test_streaming_client_diagnoses_token_length_truncation():
    chunks = [
        {"choices": [{"delta": {"content": '{"cut_off": '}}]},
        {"choices": [{"delta": {}, "finish_reason": "length"}], "usage": {"completion_tokens": 100}},
    ]
    with patch("app.infrastructure.llm.streaming.stream_chat_completion", return_value=_mock_stream(chunks)):
        client = StreamingLLMClient(AsyncMock(), "test-model", max_tokens=100)
        with pytest.raises(LLMInvalidResponseError, match="Token 上限被截断"):
            await client.chat_result([{"role": "user", "content": "hi"}], json_format=True)


@pytest.mark.asyncio
async def test_streaming_client_tolerates_none_finish_reason_when_json_is_valid():
    chunks = [
        {"choices": [{"delta": {"content": '{"valid": true}'}}]},
    ]
    with patch("app.infrastructure.llm.streaming.stream_chat_completion", return_value=_mock_stream(chunks)):
        client = StreamingLLMClient(AsyncMock(), "test-model", max_tokens=1000)
        res = await client.chat_result([{"role": "user", "content": "hi"}], json_format=True)
        assert res.text == '{"valid": true}'


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["", "null", "NULL", "none", "  "])
async def test_streaming_client_treats_empty_finish_reason_as_missing(reason):
    """部分兼容网关（vLLM/llama.cpp 等）用空串或字符串 "null" 表示无结束原因。

    这类响应内容可能已经完整，按缺失处理交给 JSON 完整性校验，而不是判成
    "输出未正常结束" 直接丢弃。
    """
    chunks = [
        {"choices": [{"delta": {"content": '{"valid": true}'}, "finish_reason": reason}]},
    ]
    with patch("app.infrastructure.llm.streaming.stream_chat_completion", return_value=_mock_stream(chunks)):
        client = StreamingLLMClient(AsyncMock(), "test-model", max_tokens=1000)
        res = await client.chat_result([{"role": "user", "content": "hi"}], json_format=True)
        assert res.text == '{"valid": true}'
        assert res.finish_reason is None


@pytest.mark.asyncio
async def test_streaming_client_still_rejects_empty_finish_reason_with_truncated_json():
    chunks = [
        {"choices": [{"delta": {"content": '{"cut_off": '}, "finish_reason": ""}]},
    ]
    with patch("app.infrastructure.llm.streaming.stream_chat_completion", return_value=_mock_stream(chunks)):
        client = StreamingLLMClient(AsyncMock(), "test-model", max_tokens=1000)
        with pytest.raises(LLMInvalidResponseError, match="内容不完整"):
            await client.chat_result([{"role": "user", "content": "hi"}], json_format=True)


@pytest.mark.asyncio
async def test_streaming_client_normalizes_uppercase_success_reason():
    chunks = [
        {"choices": [{"delta": {"content": '{"ok": 1}'}, "finish_reason": "STOP"}]},
    ]
    with patch("app.infrastructure.llm.streaming.stream_chat_completion", return_value=_mock_stream(chunks)):
        client = StreamingLLMClient(AsyncMock(), "test-model", max_tokens=1000)
        res = await client.chat_result([{"role": "user", "content": "hi"}], json_format=True)
        assert res.finish_reason == "stop"
