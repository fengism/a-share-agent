"""宏观 AI 解读：按条目增量调用大模型 + 两级缓存命中。"""

from __future__ import annotations

import json

import pytest

from app.core.cache import analysis_cache
from app.financial_data.market.macro import analysis as analysis_module
from app.financial_data.market.macro.schemas import MacroFeedItem, MacroFeedResponse


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


def _fake_llm(item_prompts: list[str], summary_prompts: list[str]):
    async def fake_llm(messages, **kwargs):  # noqa: ANN001, ANN003
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
    yield
    analysis_cache.clear()


@pytest.fixture(autouse=True)
def _no_persistence(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(analysis_module, "load_macro_analysis", lambda *args, **kwargs: {})
    monkeypatch.setattr(analysis_module, "save_macro_analysis", lambda *args, **kwargs: None)


async def test_only_new_items_are_sent_to_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    item_prompts: list[str] = []
    summary_prompts: list[str] = []
    monkeypatch.setattr(analysis_module, "llm_chat", _fake_llm(item_prompts, summary_prompts))

    titles = ["A", "B"]

    async def fake_feed(days: int = 31) -> MacroFeedResponse:
        return _feed(titles)

    monkeypatch.setattr(analysis_module, "get_macro_feed", fake_feed)

    first = await analysis_module.get_macro_analysis()
    assert len(item_prompts) == 1
    assert "A" in item_prompts[0] and "B" in item_prompts[0]
    assert len(first.events) == 2
    assert first.events[0].refs[0].url == "https://example.com/A"

    # 新增 C：只把 C 发给大模型，A/B 走缓存
    titles.append("C")
    second = await analysis_module.get_macro_analysis()
    assert len(item_prompts) == 2
    assert "C" in item_prompts[1]
    assert "A" not in item_prompts[1] and "B" not in item_prompts[1]
    assert len(second.events) == 3

    # 内容未变：条目与综述全部命中缓存，不再调用大模型
    third = await analysis_module.get_macro_analysis()
    assert len(item_prompts) == 2
    assert len(summary_prompts) == 2
    assert len(third.events) == 3
    assert third.summary == "综述"
    assert third.sentiment == "偏多"
    assert third.policy_signals == ["信号A"]


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

    async def fake_feed(days: int = 31) -> MacroFeedResponse:
        return feed

    monkeypatch.setattr(analysis_module, "get_macro_feed", fake_feed)

    result = await analysis_module.get_macro_analysis()

    assert item_prompts == []  # 条目命中 L2，未调用大模型
    assert result.events[0].interpretation == "来自持久化缓存"
    assert result.events[0].impact == "偏空"
    assert result.events[0].category == "货币金融"


async def test_degrades_when_llm_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_llm(messages, **kwargs):  # noqa: ANN001, ANN003
        raise RuntimeError("llm down")

    monkeypatch.setattr(analysis_module, "llm_chat", failing_llm)

    async def fake_feed(days: int = 31) -> MacroFeedResponse:
        return _feed(["A", "B"])

    monkeypatch.setattr(analysis_module, "get_macro_feed", fake_feed)

    result = await analysis_module.get_macro_analysis()

    assert result.degraded is True
    assert result.warning
    assert len(result.events) == 2
    assert all(event.interpretation == event.title for event in result.events)  # 降级为原文
    assert result.sentiment == "中性"


async def test_events_sorted_by_date_desc(monkeypatch: pytest.MonkeyPatch) -> None:
    item_prompts: list[str] = []
    summary_prompts: list[str] = []
    monkeypatch.setattr(analysis_module, "llm_chat", _fake_llm(item_prompts, summary_prompts))

    async def fake_feed(days: int = 31) -> MacroFeedResponse:
        return MacroFeedResponse(
            period_start="2026-09-01",
            period_end="2026-10-15",
            releases=[
                MacroFeedItem(id="old", title="旧事件", url="u-old", published_at="2026-09-20", source="国家统计局"),
                MacroFeedItem(id="new", title="新事件", url="u-new", published_at="2026-10-14", source="国家统计局"),
            ],
        )

    monkeypatch.setattr(analysis_module, "get_macro_feed", fake_feed)

    result = await analysis_module.get_macro_analysis()

    assert [event.title for event in result.events] == ["新事件", "旧事件"]
