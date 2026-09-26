from datetime import datetime, timedelta

from app.core.market import market_today


def get_news_field(item, field: str) -> str:
    """Get a stripped string field from a news dict or object."""
    if isinstance(item, dict):
        return str(item.get(field, "") or "").strip()
    return str(getattr(item, field, "") or "").strip()


def _normalize_title(title: str) -> str:
    """Normalize a news title for fuzzy equality: drop spaces and punctuation
    (half- or full-width) and case, so the same headline syndicated across
    sources with minor formatting differences collapses to one key."""
    return "".join(ch for ch in title.strip().casefold() if ch.isalnum())


def dedupe_news_items(items: list) -> list:
    """Remove duplicate news items while preserving their order.

    Duplicates are detected by normalized title (cross-source syndication of
    the same headline collapses to the first occurrence); items without a
    usable title fall back to a (source, time) key instead of being dropped.
    """
    seen_titles: set[str] = set()
    seen_fallback: set[tuple[str, str]] = set()
    result: list = []
    for item in items:
        title = get_news_field(item, "title")
        source = get_news_field(item, "source")
        time_text = get_news_field(item, "publish_time") or get_news_field(item, "time")
        if not title:
            fallback_key = (source, time_text)
            if fallback_key in seen_fallback:
                continue
            seen_fallback.add(fallback_key)
            result.append(item)
            continue
        normalized = _normalize_title(title)
        if not normalized or normalized in seen_titles:
            continue
        seen_titles.add(normalized)
        result.append(item)
    return result


def filter_recent_news_items(items: list, days: int = 2, now: datetime | None = None) -> list:
    """Filter news items to those published within the last N days."""
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
    """Parse a news timestamp, returning datetime.min when invalid."""
    text = str(value or "").strip()
    if not text:
        return datetime.min
    for date_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m-%d %H:%M",
    ):
        try:
            parsed = datetime.strptime(text, date_format)
            if date_format == "%m-%d %H:%M":
                return parsed.replace(year=market_today().year)
            return parsed
        except ValueError:
            continue
    return datetime.min


def news_sort_key(item) -> datetime:
    """Return the parsed publication time used to sort a news item."""
    return parse_news_time(get_news_field(item, "publish_time") or get_news_field(item, "time"))


def parse_timestamp(value) -> datetime | None:
    """Parse Unix seconds or milliseconds into a datetime."""
    if value in (None, "", 0, "0"):
        return None
    try:
        timestamp = int(float(value))
    except (TypeError, ValueError):
        return None
    if timestamp > 10**12:
        timestamp /= 1000
    try:
        return datetime.fromtimestamp(timestamp)
    except (OverflowError, OSError, ValueError):
        return None
