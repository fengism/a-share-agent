from datetime import datetime

from app.models.search_item import NewsSearchItem
from app.utils.news_utils import filter_recent_news_items


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
        content="",
        source="test",
        publish_time=publish_time,
        url="",
        author="",
        read_count=0,
        comment_count=0,
    )


def test_filter_recent_news_items_keeps_only_last_two_days():
    """filter_recent_news_items keeps only items published within the last two days."""
    items = [
        _item("recent", "2026-05-26 09:00:00"),
        _item("boundary", "2026-05-25 12:00:00"),
        _item("old", "2026-05-25 11:59:59"),
        _item("unknown", ""),
    ]

    result = filter_recent_news_items(items, days=2, now=datetime(2026, 5, 27, 12, 0, 0))

    assert [item.title for item in result] == ["recent", "boundary"]


def test_filter_recent_news_items_supports_dict_time_field():
    """filter_recent_news_items works with dict items that use a 'time' field."""
    items = [
        {"title": "recent-dict", "time": "2026-05-26 09:00:00"},
        {"title": "old-dict", "time": "2026-05-24 09:00:00"},
    ]

    result = filter_recent_news_items(items, days=2, now=datetime(2026, 5, 27, 12, 0, 0))

    assert [item["title"] for item in result] == ["recent-dict"]
