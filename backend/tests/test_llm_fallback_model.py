from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.configuration.schema import Settings
from app.infrastructure.llm.completion import (
    _apply_fallback_model_if_available,
    _is_quota_or_rate_limit,
    create_chat_completion,
    stream_chat_completion,
)


def _settings(**kwargs) -> Settings:
    defaults = {
        "llm_provider": "openai",
        "llm_api_mode": "openai",
        "llm_base_url": "https://api.example.com/v1",
        "llm_model": "main-model",
        "llm_fallback_model": "fallback-model",
        "llm_max_attempts": 2,
    }
    defaults.update(kwargs)
    return Settings(**defaults)


def test_is_quota_or_rate_limit():
    class DummyError(Exception):
        def __init__(self, msg, status_code=None):
            super().__init__(msg)
            self.status_code = status_code

    assert _is_quota_or_rate_limit(DummyError("rate limit exceeded", status_code=429))
    assert _is_quota_or_rate_limit(DummyError('{"error":{"message":"quota exceeded"}}', status_code=400))
    assert _is_quota_or_rate_limit(DummyError("insufficient_quota"))
    assert _is_quota_or_rate_limit(DummyError("Too Many Requests"))
    assert not _is_quota_or_rate_limit(DummyError("internal server error", status_code=500))
    assert not _is_quota_or_rate_limit(DummyError("connection reset by peer"))


def test_apply_fallback_model_not_configured():
    settings = _settings(llm_fallback_model="")
    kwargs = {"model": "main-model"}
    err = Exception("quota exceeded")
    applied = _apply_fallback_model_if_available(
        err, kwargs, settings=settings, metric_stage="test", transient_attempt=1
    )
    assert not applied
    assert kwargs["model"] == "main-model"


def test_apply_fallback_model_already_on_fallback():
    settings = _settings(llm_fallback_model="fallback-model")
    kwargs = {"model": "fallback-model"}
    err = Exception("quota exceeded")
    applied = _apply_fallback_model_if_available(
        err, kwargs, settings=settings, metric_stage="test", transient_attempt=1
    )
    assert not applied


def test_apply_fallback_model_on_429():
    settings = _settings(llm_fallback_model="fallback-model")
    kwargs = {"model": "main-model", "temperature": 0.5}
    err = Exception("quota exceeded")
    applied = _apply_fallback_model_if_available(
        err, kwargs, settings=settings, metric_stage="test", transient_attempt=1
    )
    assert applied
    assert kwargs["model"] == "fallback-model"


@pytest.mark.asyncio
async def test_create_chat_completion_falls_back_on_429():
    settings = _settings(llm_model="main-model", llm_fallback_model="fallback-model")
    mock_client = MagicMock()

    class Error429(Exception):
        status_code = 429

    success_response = MagicMock()
    success_response.choices = [MagicMock(message=MagicMock(content="hello from fallback"))]
    success_response.usage = None

    # First call with main-model raises 429; second call with fallback-model succeeds
    calls = []

    async def mock_create(**kwargs):
        calls.append(kwargs.get("model"))
        if kwargs.get("model") == "main-model":
            raise Error429("rate limit / quota exceeded")
        return success_response

    mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

    with patch("app.infrastructure.llm.completion.call_settings", return_value=settings):
        response = await create_chat_completion(mock_client, model="main-model")
        assert response == success_response
        assert calls == ["main-model", "fallback-model"]


@pytest.mark.asyncio
async def test_stream_chat_completion_falls_back_on_429():
    settings = _settings(llm_model="main-model", llm_fallback_model="fallback-model")
    mock_client = MagicMock()

    class Error429(Exception):
        status_code = 429

    chunk = MagicMock()
    chunk.choices = [MagicMock(delta=MagicMock(content="token"))]

    async def fake_stream():
        yield chunk

    calls = []

    async def mock_create(**kwargs):
        calls.append(kwargs.get("model"))
        if kwargs.get("model") == "main-model":
            raise Error429("quota exceeded")
        return fake_stream()

    mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

    with patch("app.infrastructure.llm.completion.call_settings", return_value=settings):
        chunks = []
        async for c in stream_chat_completion(mock_client, model="main-model"):
            chunks.append(c)
        assert chunks == [chunk]
        assert calls == ["main-model", "fallback-model"]
