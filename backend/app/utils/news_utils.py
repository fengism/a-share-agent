import re
import time
from datetime import datetime, timedelta

from app.models.search_item import NewsSearchItem


def news_item_to_dict(item) -> dict:
    if isinstance(item, dict):
        return item
    return {
        "title": str(getattr(item, "title", "") or "").strip(),
        "content": str(getattr(item, "content", "") or "").strip(),
        "source": str(getattr(item, "source", "") or "").strip(),
        "publish_time": str(getattr(item, "publish_time", "") or "").strip(),
        "url": str(getattr(item, "url", "") or "").strip(),
        "author": str(getattr(item, "author", "") or "").strip(),
        "read_count": getattr(item, "read_count", 0) or 0,
        "comment_count": getattr(item, "comment_count", 0) or 0,
    }


def get_news_field(item, field: str) -> str:
    if isinstance(item, dict):
        return str(item.get(field, "") or "").strip()
    return str(getattr(item, field, "") or "").strip()


def dedupe_news_items(items: list) -> list:
    seen: set[tuple[str, str, str]] = set()
    result: list = []
    for item in items:
        title = get_news_field(item, "title")
        source = get_news_field(item, "source")
        time_text = get_news_field(item, "publish_time") or get_news_field(item, "time")
        key = (title, source, time_text)
        if title and key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def filter_news_items(items: list[NewsSearchItem], date: datetime) -> list[NewsSearchItem]:
    result: list[NewsSearchItem] = []
    for item in items:
        publish_time = parse_news_time(get_news_field(item, "publish_time"))
        if publish_time.date() != date.date():
            continue
        result.append(item)
    return result


def filter_recent_news_items(items: list, days: int = 2, now: datetime | None = None) -> list:
    current_time = now or datetime.now()
    cutoff_time = current_time - timedelta(days=days)
    result = []
    for item in items:
        publish_time = parse_news_time(get_news_field(item, "publish_time") or get_news_field(item, "time"))
        if publish_time < cutoff_time or publish_time > current_time:
            continue
        result.append(item)
    return result


def parse_news_time(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.min
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m-%d %H:%M",
    ):
        try:
            parsed = datetime.strptime(text, fmt)
            if fmt == "%m-%d %H:%M":
                return parsed.replace(year=datetime.now().year)
            return parsed
        except ValueError:
            continue
    return datetime.min


def news_sort_key(item) -> datetime:
    return parse_news_time(get_news_field(item, "publish_time") or get_news_field(item, "time"))


def parse_struct_time_string(value) -> str:
    if hasattr(value, "tm_year"):
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", value)
        except (TypeError, ValueError):
            return ""

    text = str(value or "").strip()
    pattern = (
        r"tm_year=(\d+),\s*"
        r"tm_mon=(\d+),\s*"
        r"tm_mday=(\d+),\s*"
        r"tm_hour=(\d+),\s*"
        r"tm_min=(\d+),\s*"
        r"tm_sec=(\d+)"
    )
    match = re.search(pattern, text)
    if not match:
        return ""
    year, month, day, hour, minute, second = map(int, match.groups())
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
