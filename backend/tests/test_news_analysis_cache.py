"""资讯 AI 分析缓存：公共资讯流的结果与用户无关，同一内容只调用一次 LLM。"""

from __future__ import annotations

from app.core.cache import analysis_cache
from app.modules.market_intelligence import news_analysis


async def test_news_analysis_is_shared_for_identical_feed(monkeypatch) -> None:
    items = [{"title": "标题A", "url": "https://example.com/a"}]
    calls = {"llm": 0}

    async def fake_feed():
        return items

    async def fake_llm(messages, **kwargs):
        calls["llm"] += 1
        return '{"market_sentiment": "neutral", "summary": "摘要", "sections": []}'

    monkeypatch.setattr(news_analysis, "get_market_feed", fake_feed)
    monkeypatch.setattr(news_analysis, "llm_chat", fake_llm)
    analysis_cache.delete_prefix("news_analysis")

    first = await news_analysis.analyze_market_news()
    second = await news_analysis.analyze_market_news()

    assert calls["llm"] == 1, "同一资讯流应只调用一次 LLM（结果与用户无关）"
    assert first == second


async def test_news_analysis_recomputes_when_feed_changes(monkeypatch) -> None:
    """内容哈希进 key：资讯流变化必须重新分析，不能复用旧 feed 的结果。"""
    state = {"items": [{"title": "标题A", "url": "https://example.com/a"}]}
    calls = {"llm": 0}

    async def fake_feed():
        return state["items"]

    async def fake_llm(messages, **kwargs):
        calls["llm"] += 1
        return f'{{"market_sentiment": "neutral", "summary": "摘要{calls["llm"]}", "sections": []}}'

    monkeypatch.setattr(news_analysis, "get_market_feed", fake_feed)
    monkeypatch.setattr(news_analysis, "llm_chat", fake_llm)
    analysis_cache.delete_prefix("news_analysis")

    first = await news_analysis.analyze_market_news()
    state["items"] = [{"title": "标题B", "url": "https://example.com/b"}]
    second = await news_analysis.analyze_market_news()

    assert calls["llm"] == 2
    assert first["summary"] != second["summary"]
