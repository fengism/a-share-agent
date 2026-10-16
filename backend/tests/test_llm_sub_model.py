"""简单任务子模型：仅在配置 llm_sub_model 时替换 model，其余路由不变。"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from app.configuration.schema import Settings
from app.infrastructure.llm import adapters
from app.infrastructure.llm import streaming as streaming_module
from app.infrastructure.llm.runtime import borrow_async_openai_chat_runtime
from app.infrastructure.llm.spec import apply_task_model, task_uses_sub_model
from app.infrastructure.llm.sync_client import create_llm_client, llm_chat


def _settings(**overrides) -> Settings:
    return Settings(llm_api_key="test-key", **overrides)


def test_simple_task_swaps_to_sub_model() -> None:
    settings = _settings(llm_model="main-model", llm_sub_model="sub-model")
    assert apply_task_model(settings, simple=True).llm_model == "sub-model"
    assert apply_task_model(settings, simple=False).llm_model == "main-model"


def test_simple_task_keeps_main_model_when_sub_model_unset() -> None:
    settings = _settings(llm_model="main-model", llm_sub_model="")
    assert apply_task_model(settings, simple=True).llm_model == "main-model"


def test_simple_task_ignores_identical_sub_model() -> None:
    settings = _settings(llm_model="main-model", llm_sub_model="main-model")
    assert apply_task_model(settings, simple=True).llm_model == "main-model"


def test_sub_model_keeps_provider_and_credentials() -> None:
    settings = _settings(llm_model="main-model", llm_sub_model="sub-model", llm_base_url="https://api.example.com")
    simple = apply_task_model(settings, simple=True)
    assert simple.llm_model == "sub-model"
    assert simple.llm_provider == settings.llm_provider
    assert simple.llm_base_url == "https://api.example.com"
    assert simple.llm_api_key == "test-key"


def test_create_llm_client_routes_by_task() -> None:
    settings = _settings(llm_model="main-model", llm_sub_model="sub-model")
    assert create_llm_client(settings, simple=True).model == "sub-model"
    assert create_llm_client(settings, simple=False).model == "main-model"


async def test_borrow_runtime_routes_by_task() -> None:
    settings = _settings(llm_model="main-model", llm_sub_model="sub-model")
    async with borrow_async_openai_chat_runtime(settings, simple=True) as runtime:
        assert runtime.model == "sub-model"
    async with borrow_async_openai_chat_runtime(settings) as runtime:
        assert runtime.model == "main-model"


def test_task_uses_sub_model_reports_actual_swap() -> None:
    swapped = _settings(llm_model="main-model", llm_sub_model="sub-model")
    assert task_uses_sub_model(swapped, task="macro_item") is True
    assert task_uses_sub_model(swapped, simple=True) is True
    # 未配置子模型 / 子模型与主模型同名：不会真的切换
    assert task_uses_sub_model(_settings(llm_model="main-model"), task="macro_item") is False
    assert task_uses_sub_model(
        _settings(llm_model="main-model", llm_sub_model="main-model"), task="macro_item"
    ) is False


class _ManagedCompletion:
    def __init__(self, model: str) -> None:
        self.model = model
        self.calls: list[str] = []

    async def chat_result(self, messages: list[dict], temperature: float = 0.1, json_format: bool = False):
        if self.model == "sub-model":
            raise RuntimeError("sub model down")
        return adapters.LLMCompletion(text="ok", usage=None, model=self.model)


async def test_sub_model_failure_falls_back_to_main_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """子模型报错时回退主模型重试一次，简单任务不至于整体失败。"""
    models: list[str] = []

    @asynccontextmanager
    async def fake_streaming(settings: Settings, *, max_tokens: int):
        models.append(settings.llm_model)
        yield _ManagedCompletion(settings.llm_model)

    monkeypatch.setattr(streaming_module, "streaming_llm_client", fake_streaming)

    settings = _settings(llm_model="main-model", llm_sub_model="sub-model")
    text = await llm_chat([{"role": "user", "content": "hi"}], settings=settings, task="macro_item")

    assert text == "ok"
    assert models == ["sub-model", "main-model"]


async def test_no_duplicate_call_when_sub_model_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """未配置子模型时不会因为回退而重复调用。"""
    models: list[str] = []

    @asynccontextmanager
    async def fake_streaming(settings: Settings, *, max_tokens: int):
        models.append(settings.llm_model)
        yield _ManagedCompletion(settings.llm_model)

    monkeypatch.setattr(streaming_module, "streaming_llm_client", fake_streaming)

    text = await llm_chat(
        [{"role": "user", "content": "hi"}],
        settings=_settings(llm_model="main-model"),
        task="macro_item",
    )

    assert text == "ok"
    assert models == ["main-model"]


async def _run_refine_decision(monkeypatch: pytest.MonkeyPatch, settings: Settings, *, fail_models: set[str]):
    """用最小化的 orchestrator 跑一次意图分类，返回 (访问过的模型序列, 结果)。"""
    from app.modules.chat import orchestrator as orch_module
    from app.modules.chat.orchestrator import Orchestrator
    from app.modules.chat.routing import RoutingDecision

    models: list[str] = []

    class _Runtime:
        def __init__(self, model: str) -> None:
            self.model = model
            self.client = object()

    @asynccontextmanager
    async def fake_borrow(settings: Settings, *, simple: bool = False, task: str | None = None):
        effective = apply_task_model(settings, simple=simple, task=task)
        models.append(effective.llm_model)
        yield _Runtime(effective.llm_model)

    monkeypatch.setattr(orch_module, "borrow_async_openai_chat_runtime", fake_borrow)

    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.sub_agents = ["technical", "fundamental"]

    async def fake_classify(message: str, llm_client: object, model: str) -> RoutingDecision:
        if model in fail_models:
            raise RuntimeError(f"{model} down")
        return RoutingDecision(agents=["technical"], reasoning="ok")

    monkeypatch.setattr(orchestrator, "_llm_classify", fake_classify)

    decision = RoutingDecision(agents=[], needs_llm_classification=True)
    refined = await orchestrator._refine_decision("分析一下", decision, settings)
    return models, refined


async def test_refine_decision_falls_back_to_main_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """子模型意图分类失败时，回退主模型再试一次并采用结果。"""
    settings = _settings(llm_model="main-model", llm_sub_model="sub-model")
    models, refined = await _run_refine_decision(monkeypatch, settings, fail_models={"sub-model"})

    assert models == ["sub-model", "main-model"]
    assert refined.agents == ["technical"]


async def test_refine_decision_single_attempt_without_sub_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """未配置子模型时不重复调用，失败后回退全部 Agent。"""
    settings = _settings(llm_model="main-model")
    models, refined = await _run_refine_decision(monkeypatch, settings, fail_models={"main-model"})

    assert models == ["main-model"]
    assert refined.agents == ["technical", "fundamental"]
