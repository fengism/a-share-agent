from datetime import datetime, timedelta

import pytest

from app.models.search_item import NewsSearchItem
from app.services.market import news


def _item(title: str, publish_time: str) -> NewsSearchItem:
    """Build a NewsSearchItem with test-friendly defaults.

    Param:
        title: news headline used for both title and content fields.
        publish_time: explicit publish timestamp string.
    Return:
        a NewsSearchItem with source="test" and zeroed engagement counters.
    """
    return NewsSearchItem(
        title=title,
        content=title,
        source="test",
        publish_time=publish_time,
        url="",
        author="",
        read_count=0,
        comment_count=0,
    )


@pytest.mark.asyncio
async def test_get_market_news_keeps_only_recent_news(monkeypatch):
    """get_market_news keeps only items published within the recency window."""
    recent_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    old_time = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")

    async def fake_call_blocking(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(news.cache, "get", lambda key: None)
    monkeypatch.setattr(news.cache, "set", lambda *args, **kwargs: None)
    monkeypatch.setattr(news, "call_blocking", fake_call_blocking)

    # Patch all providers to return controlled data
    monkeypatch.setattr(news._eastmoney_provider, "fetch_market_news", lambda: [_item("old_em", old_time)])
    monkeypatch.setattr(news._eastmoney_provider, "fetch_market_kuaixun", lambda: [])
    monkeypatch.setattr(news._rss_provider, "fetch_market_kuaixun", lambda: [_item("old_rss", old_time)])
    monkeypatch.setattr(news._cls_provider, "fetch_market_news", lambda: [])
    monkeypatch.setattr(news._baidu_provider, "fetch_market_kuaixun", lambda: [])
    monkeypatch.setattr(news._rss_provider, "fetch_china_news", lambda: [])
    monkeypatch.setattr(news._rss_provider, "fetch_zaobao_news", lambda: [])
    monkeypatch.setattr(news._rss_provider, "fetch_36kr_news", lambda: [_item("recent_kr", recent_time)])
    monkeypatch.setattr(news._rss_provider, "fetch_xueqiu_news", lambda: [])
    monkeypatch.setattr(news._rss_provider, "fetch_jiemain_news", lambda: [])
    monkeypatch.setattr(news._rss_provider, "fetch_eeo_news", lambda: [])
    monkeypatch.setattr(news._twitter_provider, "fetch_market_news", lambda: [])

    result = await news.get_market_news()

    # Only recent items should survive the filter
    titles = [item.title for item in result]
    assert "recent_kr" in titles
    assert "old_em" not in titles
    assert "old_rss" not in titles
