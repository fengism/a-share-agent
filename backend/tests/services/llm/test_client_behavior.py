from types import SimpleNamespace

from app.services.llm import client


def test_openai_compatible_client_handles_missing_usage(monkeypatch):
    """OpenAICompatibleClient.chat should not fail when the provider omits usage."""

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))],
                usage=None,
            )

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAIClient:
        chat = FakeChat()

    monkeypatch.setattr(client, "OpenAI", lambda **kwargs: FakeOpenAIClient())

    llm = client.OpenAICompatibleClient(
        api_key="secret",
        base_url="https://example.com/v1",
        model="demo-model",
        timeout=33.0,
    )

    assert llm.chat([{"role": "user", "content": "hi"}]) == "hello"


def test_create_llm_client_passes_runtime_timeout(monkeypatch):
    """create_llm_client should pass llm_timeout_seconds to the underlying client."""
    captured = {}

    def fake_init(self, api_key: str, base_url: str, model: str, timeout: float):
        captured.update(
            {
                "api_key": api_key,
                "base_url": base_url,
                "model": model,
                "timeout": timeout,
            }
        )

    monkeypatch.setattr(client.OpenAICompatibleClient, "__init__", fake_init)

    settings = SimpleNamespace(
        llm_provider="openai",
        llm_api_key="secret",
        llm_base_url="",
        llm_model="",
        llm_timeout_seconds=45,
    )

    client._client_cache = None
    client._cache_key = None
    llm = client.create_llm_client(settings)

    assert llm is client._client_cache
    assert captured == {
        "api_key": "secret",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "timeout": 45.0,
    }


def test_create_openai_chat_runtime_uses_settings_timeout(monkeypatch):
    """create_openai_chat_runtime should propagate llm_timeout_seconds."""
    captured = {}

    monkeypatch.setattr(
        client,
        "OpenAI",
        lambda api_key, base_url, timeout: captured.update(
            {"api_key": api_key, "base_url": base_url, "timeout": timeout}
        ) or SimpleNamespace(),
    )

    settings = SimpleNamespace(
        llm_provider="openai",
        llm_api_key="secret",
        llm_base_url="",
        llm_model="",
        llm_timeout_seconds=25,
    )

    runtime = client.create_openai_chat_runtime(settings)

    assert runtime.model == "gpt-4o-mini"
    assert captured == {
        "api_key": "secret",
        "base_url": "https://api.openai.com/v1",
        "timeout": 25.0,
    }
