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
