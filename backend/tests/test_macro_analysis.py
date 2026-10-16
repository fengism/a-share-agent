"""宏观 AI 解读：请求路径只读缓存、后台预热补齐解读（两级缓存）。"""

from __future__ import annotations

import inspect
import json
from unittest.mock import MagicMock

import pytest

from app.core.cache import analysis_cache
from app.financial_data.market.macro import analysis as analysis_module
from app.financial_data.market.macro.schemas import MacroAnalysisResponse, MacroFeedItem, MacroFeedResponse


def _feed(titles: list[str]) -> MacroFeedResponse:
    return MacroFeedResponse(
        period_start="2026-09-14",
        period_end="2026-10-15",
        releases=[
            MacroFeedItem(
                id=title,
                title=title,
                url=f"https://example.com/{title}",
                published_at="2026-10-14",
                source="国家统计局",
            )
            for title in titles
        ],
    )


def _fake_llm(item_prompts: list[str], summary_prompts: list[str], task_flags: list[str | None] | None = None):
    async def fake_llm(messages, **kwargs):  # noqa: ANN001, ANN003
        if task_flags is not None:
            task_flags.append(kwargs.get("task"))
        system = messages[0]["content"]
        user = messages[-1]["content"]
        if "逐条解读" in system:
            item_prompts.append(user)
            count = sum(1 for line in user.splitlines() if line.startswith("["))
            return json.dumps(
                {
                    "items": [
                        {"index": index, "category": "物价", "interpretation": f"解读{index}", "impact": "偏多"}
                        for index in range(count)
                    ]
                }
            )
        summary_prompts.append(user)
        return json.dumps({"summary": "综述", "sentiment": "偏多", "policy_signals": ["信号A"]})

    return fake_llm


@pytest.fixture(autouse=True)
def _clear_cache():
    analysis_cache.clear()
    analysis_module._prewarm_task = None
    yield
    analysis_module._prewarm_task = None
    analysis_cache.clear()


@pytest.fixture(autouse=True)
def _no_persistence(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(analysis_module, "load_macro_analysis", lambda *args, **kwargs: {})
    monkeypatch.setattr(analysis_module, "save_macro_analysis", lambda *args, **kwargs: None)


def _patch_feed(monkeypatch: pytest.MonkeyPatch, feed: MacroFeedResponse) -> None:
    async def fake_feed(days: int = 31) -> MacroFeedResponse:
        return feed

    monkeypatch.setattr(analysis_module, "get_macro_feed", fake_feed)


async def test_request_path_is_cache_only_and_marks_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    """请求路径不调用大模型：未命中缓存的条目展示原文并标记 pending。"""
    item_prompts: list[str] = []
    summary_prompts: list[str] = []
    monkeypatch.setattr(analysis_module, "llm_chat", _fake_llm(item_prompts, summary_prompts))
    _patch_feed(monkeypatch, _feed(["A", "B"]))

    result = await analysis_module.get_macro_analysis()

    assert item_prompts == []
    assert summary_prompts == []
    assert result.pending_count == 2
    assert result.warning
    assert all(event.pending for event in result.events)
    assert all(event.interpretation == event.title for event in result.events)


async def test_prewarm_interprets_then_request_serves_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    item_prompts: list[str] = []
    summary_prompts: list[str] = []
    task_flags: list[str | None] = []
    monkeypatch.setattr(analysis_module, "llm_chat", _fake_llm(item_prompts, summary_prompts, task_flags))
    _patch_feed(monkeypatch, _feed(["A", "B"]))

    interpreted = await analysis_module.prewarm_macro_analysis()

    assert interpreted == 2
    assert len(item_prompts) == 1
    assert "A" in item_prompts[0] and "B" in item_prompts[0]
    assert task_flags[0] == "macro_item"  # 高频的逐条解读走子模型任务
    assert len(summary_prompts) == 1

    result = await analysis_module.get_macro_analysis()

    assert result.pending_count == 0
    assert not result.warning
    assert len(result.events) == 2
    assert all(not event.pending for event in result.events)
    assert result.summary == "综述"
    assert result.sentiment == "偏多"
    assert result.policy_signals == ["信号A"]
    assert result.cached is True
    assert result.events[0].refs[0].url == "https://example.com/A"


async def test_prewarm_skips_already_interpreted_items(monkeypatch: pytest.MonkeyPatch) -> None:
    item_prompts: list[str] = []
    summary_prompts: list[str] = []
    monkeypatch.setattr(analysis_module, "llm_chat", _fake_llm(item_prompts, summary_prompts))
    _patch_feed(monkeypatch, _feed(["A", "B"]))

    assert await analysis_module.prewarm_macro_analysis() == 2
    assert await analysis_module.prewarm_macro_analysis() == 0
    assert len(item_prompts) == 1  # 第二次全部命中缓存，不再调用大模型


async def test_persistent_cache_hit_skips_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    item_prompts: list[str] = []
    summary_prompts: list[str] = []
    monkeypatch.setattr(analysis_module, "llm_chat", _fake_llm(item_prompts, summary_prompts))

    feed = _feed(["A"])
    key = f"{analysis_module._cache_prefix('item')}:{analysis_module._item_hash(feed.releases[0])}"
    stored = {key: {"category": "货币金融", "interpretation": "来自持久化缓存", "impact": "偏空"}}
    monkeypatch.setattr(
        analysis_module,
        "load_macro_analysis",
        lambda keys, **kwargs: {k: stored[k] for k in keys if k in stored},
    )
    _patch_feed(monkeypatch, feed)

    result = await analysis_module.get_macro_analysis()

    assert len(item_prompts) == 0  # 条目命中 L2，未调用大模型
    assert result.pending_count == 0
    assert result.events[0].interpretation == "来自持久化缓存"
    assert result.events[0].impact == "偏空"
    assert result.events[0].category == "货币金融"


async def test_pending_when_llm_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_llm(messages, **kwargs):  # noqa: ANN001, ANN003
        raise RuntimeError("llm down")

    monkeypatch.setattr(analysis_module, "llm_chat", failing_llm)
    _patch_feed(monkeypatch, _feed(["A", "B"]))

    assert await analysis_module.prewarm_macro_analysis() == 0

    result = await analysis_module.get_macro_analysis()

    assert result.pending_count == 2
    assert result.warning
    assert len(result.events) == 2
    assert all(event.interpretation == event.title for event in result.events)
    assert all(event.pending for event in result.events)
    assert result.sentiment == "中性"


async def test_events_sorted_by_date_desc(monkeypatch: pytest.MonkeyPatch) -> None:
    item_prompts: list[str] = []
    summary_prompts: list[str] = []
    monkeypatch.setattr(analysis_module, "llm_chat", _fake_llm(item_prompts, summary_prompts))

    feed = MacroFeedResponse(
        period_start="2026-09-01",
        period_end="2026-10-15",
        releases=[
            MacroFeedItem(id="old", title="旧事件", url="u-old", published_at="2026-09-20", source="国家统计局"),
            MacroFeedItem(id="new", title="新事件", url="u-new", published_at="2026-10-14", source="国家统计局"),
        ],
    )
    _patch_feed(monkeypatch, feed)

    await analysis_module.prewarm_macro_analysis()
    result = await analysis_module.get_macro_analysis()

    assert [event.title for event in result.events] == ["新事件", "旧事件"]


async def test_trigger_macro_prewarm_fills_pending_and_is_deduplicated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """请求命中 pending 时触发的后台预热能补齐解读，且同一时刻只跑一个任务。"""
    item_prompts: list[str] = []
    summary_prompts: list[str] = []
    monkeypatch.setattr(analysis_module, "llm_chat", _fake_llm(item_prompts, summary_prompts))
    _patch_feed(monkeypatch, _feed(["A", "B"]))

    pending = await analysis_module.get_macro_analysis()
    assert pending.pending_count == 2

    assert analysis_module.trigger_macro_prewarm() is True
    task = analysis_module._prewarm_task
    assert task is not None
    assert analysis_module.trigger_macro_prewarm() is False  # 已有任务在跑，去重

    await task
    assert len(item_prompts) == 1  # 两条 pending 合并为一次批量解读
    assert len(summary_prompts) == 1

    result = await analysis_module.get_macro_analysis()
    assert result.pending_count == 0
    assert not result.warning
    assert all(not event.pending for event in result.events)


async def test_analysis_route_triggers_prewarm_when_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """路由命中 pending 时触发后台预热，无 pending 则不触发。"""
    from app.api.routes.market_sections import macro as macro_route

    def _service(pending_count: int):
        async def _call(days: int = 31) -> MacroAnalysisResponse:
            return MacroAnalysisResponse(
                period="2026-09-14 ~ 2026-10-15",
                summary="",
                sentiment="中性",
                events=[],
                policy_signals=[],
                degraded=False,
                pending_count=pending_count,
                warning="",
                generated_at="2026-10-15T00:00:00",
                cached=False,
            )

        return _call

    triggered: list[int] = []
    monkeypatch.setattr(
        macro_route, "trigger_macro_prewarm_service", lambda days=31: triggered.append(days)
    )

    monkeypatch.setattr(macro_route, "get_macro_analysis_service", _service(2))
    await macro_route.get_macro_analysis(days=31)
    assert triggered == [31]

    monkeypatch.setattr(macro_route, "get_macro_analysis_service", _service(0))
    await macro_route.get_macro_analysis(days=7)
    assert triggered == [31]  # 无 pending，不再触发


def test_cache_prefix_is_model_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    """缓存键不包含 provider/model/sub_model：切换模型不会作废历史解读。"""
    from app.configuration.schema import Settings

    settings = Settings(llm_provider="openai", llm_model="gpt-x", llm_sub_model="fast-y")
    monkeypatch.setattr(analysis_module, "get_effective_settings", lambda: settings, raising=False)

    prefix = analysis_module._cache_prefix("item")

    assert prefix == f"macro_item:{analysis_module.MACRO_ANALYSIS_PROMPT_VERSION}"
    assert "gpt-x" not in prefix
    assert "fast-y" not in prefix
    assert "openai" not in prefix


def test_lifecycle_registers_macro_analysis_prewarm() -> None:
    from app.runtime import lifecycle

    params = inspect.signature(lifecycle.build_background_task_specs).parameters
    assert "macro_analysis_prewarm" in params
    assert "macro_analysis_prewarm" in inspect.signature(lifecycle.application_lifespan).parameters

    kwargs = {name: MagicMock() for name in params}
    specs = lifecycle.build_background_task_specs(**kwargs)
    names = [spec.name for spec in specs]
    assert "macro_analysis_prewarm" in names

    source = inspect.getsource(lifecycle.application_lifespan)
    assert "macro_analysis_prewarm=macro_analysis_prewarm" in source
