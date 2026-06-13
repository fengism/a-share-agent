from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.stock import retail


def test_get_retail_sentiment_counts_only_recent_posts(monkeypatch):
    """get_retail_sentiment counts only posts within the recency window."""
    recent_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    old_time = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    posts = [
        SimpleNamespace(title="看多突破上涨趋势很强继续加仓", content="", author="a", publish_time=recent_time),
        SimpleNamespace(title="看空下跌风险很大需要减仓", content="", author="b", publish_time=old_time),
    ]

    async def fake_call_blocking(func, *args, **kwargs):
        return posts

    monkeypatch.setattr(retail.cache, "get", lambda key: None)
    monkeypatch.setattr(retail.cache, "set", lambda *args, **kwargs: None)
    monkeypatch.setattr(retail, "call_blocking", fake_call_blocking)
    monkeypatch.setattr(
        retail,
        "_get_eastmoney_provider",
        lambda: SimpleNamespace(fetch_stock_guba_posts=lambda code: posts),
    )

    import asyncio

    result = asyncio.run(retail.get_retail_sentiment("600519"))

    assert result["guba_post_count"] == 1
    assert result["post_count"] == 1
    assert result["sample_posts"][0]["text"] == "看多突破上涨趋势很强继续加仓"
