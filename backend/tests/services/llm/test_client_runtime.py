from types import SimpleNamespace

from app.services.llm import client


def test_create_openai_chat_runtime_uses_provider_defaults(monkeypatch):
    """create_openai_chat_runtime should derive base_url and model from settings/provider defaults."""
    captured = {}

    monkeypatch.setattr(
        client,
        "OpenAI",
        lambda api_key, base_url, timeout, http_client: captured.update(
            {"api_key": api_key, "base_url": base_url, "timeout": timeout, "trust_env": http_client.trust_env}
        ) or SimpleNamespace(),
    )

    settings = SimpleNamespace(
        llm_provider="openai",
        llm_api_key="secret",
        llm_base_url="",
        llm_model="",
    )

    runtime = client.create_openai_chat_runtime(settings)

    assert runtime.model == "gpt-4o-mini"
    assert captured == {
        "api_key": "secret",
        "base_url": "https://api.openai.com/v1",
        "timeout": 120.0,
        "trust_env": False,
    }
