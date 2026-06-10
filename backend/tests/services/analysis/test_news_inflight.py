import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.search_item import NewsSearchItem
from app.services.analysis import news


def _item(title: str, source: str = "东方财富", publish_time: str | None = None) -> NewsSearchItem:
    """Build a NewsSearchItem with sensible defaults for tests.

    Param:
        title: news headline used for title, content and url slug.
        source: news source label.
        publish_time: explicit timestamp string; defaults to current time when None.
    Return:
        a populated NewsSearchItem instance.
    """
    return NewsSearchItem(
        title=title,
        content=title,
        source=source,
        publish_time=publish_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        url=f"https://example.com/{title}",
        author="",
        read_count=0,
        comment_count=0,
    )


@pytest.mark.asyncio
async def test_load_stock_news_keeps_only_recent_news(monkeypatch):
    """_load_stock_news filters out news older than the recency window."""
    recent_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    old_time = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")

    async def fake_name_map():
        return {"600519": "贵州茅台"}

    monkeypatch.setattr(news, "get_stock_name_map", fake_name_map)
    monkeypatch.setattr(
        news,
        "_get_eastmoney_provider",
        lambda: SimpleNamespace(fetch_stock_news=lambda **kwargs: [_item("recent", publish_time=recent_time)]),
    )
    monkeypatch.setattr(
        news,
        "_get_cls_provider",
        lambda: SimpleNamespace(fetch_market_news=lambda **kwargs: [_item("old", "财联社", old_time)]),
    )

    result = await news._load_stock_news(news.normalize_code("600519"))

    assert [item.title for item in result] == ["recent"]


@pytest.mark.asyncio
async def test_get_stock_news_dedupes_concurrent_same_code(monkeypatch):
    """get_stock_news coalesces concurrent calls for the same code into one provider call."""
    calls = {"em": 0, "cls": 0}

    async def fake_name_map():
        return {"600519": "贵州茅台"}

    def fake_em(**kwargs):
        calls["em"] += 1
        return [_item("em")]

    def fake_cls(**kwargs):
        calls["cls"] += 1
        return [_item("cls", "财联社")]

    async def fake_to_thread(func, *args, **kwargs):
        await asyncio.sleep(0.01)
        return func(*args, **kwargs)

    monkeypatch.setattr(news, "get_stock_name_map", fake_name_map)
    monkeypatch.setattr(news, "_get_eastmoney_provider", lambda: SimpleNamespace(fetch_stock_news=fake_em))
    monkeypatch.setattr(news, "_get_cls_provider", lambda: SimpleNamespace(fetch_market_news=fake_cls))
    monkeypatch.setattr(news.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(news.cache, "get", lambda key: None)
    monkeypatch.setattr(news.cache, "set", lambda *args, **kwargs: None)
    news._news_inflight.clear()

    result_a, result_b = await asyncio.gather(
        news.get_stock_news("600519"),
        news.get_stock_news("600519"),
    )

    assert [item.title for item in result_a] == [item.title for item in result_b]
    assert calls == {"em": 1, "cls": 1}


@pytest.mark.asyncio
async def test_get_stock_news_does_not_dedupe_different_codes(monkeypatch):
    """get_stock_news issues separate provider calls for different stock codes."""
    requested: list[str] = []

    async def fake_name_map():
        return {"600519": "贵州茅台", "000858": "五粮液"}

    def fake_em(**kwargs):
        requested.append(kwargs["code"])
        return [_item(kwargs["code"])]

    def fake_cls(**kwargs):
        return []

    async def fake_to_thread(func, *args, **kwargs):
        await asyncio.sleep(0.01)
        return func(*args, **kwargs)

    monkeypatch.setattr(news, "get_stock_name_map", fake_name_map)
    monkeypatch.setattr(news, "_get_eastmoney_provider", lambda: SimpleNamespace(fetch_stock_news=fake_em))
    monkeypatch.setattr(news, "_get_cls_provider", lambda: SimpleNamespace(fetch_market_news=fake_cls))
    monkeypatch.setattr(news.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(news.cache, "get", lambda key: None)
    monkeypatch.setattr(news.cache, "set", lambda *args, **kwargs: None)
    news._news_inflight.clear()

    await asyncio.gather(news.get_stock_news("600519"), news.get_stock_news("000858"))

    assert sorted(requested) == ["000858", "600519"]


@pytest.mark.asyncio
async def test_get_stock_news_clears_inflight_after_failure(monkeypatch):
    """get_stock_news clears inflight state when the underlying loader raises."""
    calls = 0

    async def fake_load(sym):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary failure")
        return [_item("ok")]

    monkeypatch.setattr(news, "_load_stock_news", fake_load)
    monkeypatch.setattr(news.cache, "get", lambda key: None)
    monkeypatch.setattr(news.cache, "set", lambda *args, **kwargs: None)
    news._news_inflight.clear()

    with pytest.raises(RuntimeError, match="temporary failure"):
        await news.get_stock_news("600519")

    result = await news.get_stock_news("600519")

    assert [item.title for item in result] == ["ok"]
    assert calls == 2


@pytest.mark.asyncio
async def test_get_stock_news_uses_cache_without_provider(monkeypatch):
    """get_stock_news returns the cached payload without invoking the provider."""
    cached = [_item("cached")]

    async def fake_load(sym):
        raise AssertionError("provider should not be called")

    monkeypatch.setattr(news, "_load_stock_news", fake_load)
    monkeypatch.setattr(news.cache, "get", lambda key: cached)
    news._news_inflight.clear()

    result = await news.get_stock_news("600519")

    assert result == cached
