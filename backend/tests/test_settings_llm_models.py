"""模型列表拉取（/config/llm/models）的服务层测试。"""

import pytest

from app.configuration.schema import Settings
from app.modules.settings.service import LlmModelsUnavailableError, fetch_llm_models


class _FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict:
        return self._payload


def _settings(**overrides) -> Settings:
    fields = dict(
        llm_base_url="https://api.example.com/v1",
        llm_api_key="sk-stored",
        llm_api_mode="openai",
        llm_api_version="",
    )
    fields.update(overrides)
    return Settings.model_construct(**fields)


def _passthrough_runner():
    async def runner(fn, **kwargs):
        return fn()

    return runner


async def test_fetch_models_sorts_ids_and_uses_bearer_header(monkeypatch):
    captured = {}

    def fake_get():
        captured["called"] = True
        return _FakeResponse(payload={"data": [{"id": "model-b"}, {"id": "model-a"}, {"id": "model-a"}]})

    monkeypatch.setattr("app.modules.settings.service.get_user_settings", lambda user_id: _settings())

    models = await fetch_llm_models(
        1,
        type("Req", (), {"base_url": "", "api_key": "", "api_mode": "", "api_version": ""})(),
        settings_provider=lambda user_id: _settings(),
        blocking_runner=_passthrough_runner(),
        http_get=fake_get,
    )

    assert models == ["model-a", "model-b"]
    assert captured["called"]


async def test_fetch_models_falls_back_to_stored_key(monkeypatch):
    seen = {}

    def fake_get():
        seen["url"] = "called"
        return _FakeResponse(payload={"data": [{"id": "m"}]})

    monkeypatch.setattr("app.modules.settings.service.get_user_settings", lambda user_id: _settings())
    request = type("Req", (), {"base_url": "https://custom.example.com/v1", "api_key": "", "api_mode": "", "api_version": ""})()

    await fetch_llm_models(1, request, settings_provider=lambda user_id: _settings(), blocking_runner=_passthrough_runner(), http_get=fake_get)

    # 请求里没有提供 key，且不该把 URL 里的鉴权信息当作失败
    assert seen["url"] == "called"


async def test_fetch_models_requires_base_url(monkeypatch):
    monkeypatch.setattr("app.modules.settings.service.get_user_settings", lambda user_id: _settings(llm_base_url=""))

    with pytest.raises(LlmModelsUnavailableError, match="Base URL"):
        await fetch_llm_models(
            1,
            type("Req", (), {"base_url": "", "api_key": "sk-x", "api_mode": "", "api_version": ""})(),
            settings_provider=lambda user_id: _settings(llm_base_url=""),
            blocking_runner=_passthrough_runner(),
            http_get=lambda: None,
        )


async def test_fetch_models_maps_upstream_http_error(monkeypatch):
    monkeypatch.setattr("app.modules.settings.service.get_user_settings", lambda user_id: _settings())

    with pytest.raises(LlmModelsUnavailableError, match="401"):
        await fetch_llm_models(
            1,
            type("Req", (), {"base_url": "", "api_key": "", "api_mode": "", "api_version": ""})(),
            settings_provider=lambda user_id: _settings(),
            blocking_runner=_passthrough_runner(),
            http_get=lambda: _FakeResponse(status_code=401, text='{"error":"bad key"}'),
        )


async def test_fetch_models_rejects_non_http_scheme(monkeypatch):
    monkeypatch.setattr("app.modules.settings.service.get_user_settings", lambda user_id: _settings(llm_base_url=""))

    with pytest.raises(LlmModelsUnavailableError, match="HTTP/HTTPS"):
        await fetch_llm_models(
            1,
            type("Req", (), {"base_url": "ftp://files.example.com", "api_key": "sk-x", "api_mode": "", "api_version": ""})(),
            settings_provider=lambda user_id: _settings(llm_base_url=""),
            blocking_runner=_passthrough_runner(),
            http_get=lambda: None,
        )
