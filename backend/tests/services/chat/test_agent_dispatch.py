import pytest
from unittest.mock import patch

from app.models.chat import ChatStreamDelta


@pytest.mark.asyncio
async def test_run_chat_agent_dispatches_to_orchestrator_when_enabled():
    """When multi_agent_enabled=True, run_chat_agent delegates to Orchestrator."""
    from app.services.chat.agent import run_chat_agent

    async def fake_run(msg, hist):
        yield ChatStreamDelta(type="text", content="test")

    mock_orch = type("Orch", (), {"run": staticmethod(fake_run)})()

    with patch("app.services.chat.agent.get_settings") as mock_settings:
        mock_settings.return_value = type("S", (), {"multi_agent_enabled": True})()
        with patch("app.services.chat.orchestrator.Orchestrator", return_value=mock_orch):
            results = []
            async for delta in run_chat_agent("hello", None):
                results.append(delta)
            assert len(results) == 1
            assert results[0].type == "text"
            assert results[0].content == "test"


@pytest.mark.asyncio
async def test_run_chat_agent_dispatches_to_legacy_when_disabled():
    """When multi_agent_enabled=False, run_chat_agent uses legacy agent."""
    from app.services.chat.agent import run_chat_agent

    async def fake_legacy(msg, hist):
        yield ChatStreamDelta(type="text", content="legacy")

    with patch("app.services.chat.agent.get_settings") as mock_settings:
        mock_settings.return_value = type("S", (), {"multi_agent_enabled": False})()
        with patch("app.services.chat.agent._run_legacy_agent", fake_legacy):
            results = []
            async for delta in run_chat_agent("hello", None):
                results.append(delta)
            assert len(results) == 1
            assert results[0].content == "legacy"
