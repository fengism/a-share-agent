import re
from datetime import datetime, timedelta

from app.core.market import SHANGHAI_TIMEZONE


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
    """Remove duplicate news items while preserving their order."""
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


def _local_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(SHANGHAI_TIMEZONE).replace(tzinfo=None)


def _reference_time(now: datetime | None) -> datetime:
    return _local_naive(now or datetime.now(SHANGHAI_TIMEZONE))


def _safe_replace_year(value: datetime, year: int) -> datetime:
    try:
        return value.replace(year=year)
    except ValueError:
        # 2 月 29 日落到非闰年时，按该月最后一天处理。
        return value.replace(year=year, day=28)


def parse_news_datetime(
    value: object,
    *,
    now: datetime | None = None,
    allow_relative: bool = True,
    allow_time_only: bool = True,
    assume_year: bool = True,
) -> datetime | None:
    """解析常见新闻时间格式；调用方可关闭相对时间以防历史数据穿越。"""
    reference = _reference_time(now)
    if isinstance(value, datetime):
        return _local_naive(value)
    text = str(value or "").strip()
    if not text or text.casefold() in {"none", "null", "nat", "nan", "-"}:
        return None

    normalized = (
        text.replace("年", "-")
        .replace("月", "-")
        .replace("日", " ")
        .replace("/", "-")
        .replace("T", " ")
        .strip()
    )

    # 先识别紧凑日期，避免 YYYYMMDD 被误当作 Unix 秒。
    compact_formats = {
        14: "%Y%m%d%H%M%S",
        8: "%Y%m%d",
    }
    date_format = compact_formats.get(len(normalized))
    if date_format is not None:
        try:
            return datetime.strptime(normalized, date_format)
        except ValueError:
            pass

    numeric_match = re.fullmatch(r"\d{10}(?:\.\d+)?|\d{13}", normalized)
    if numeric_match:
        timestamp = float(normalized)
        if timestamp >= 10**12:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp, tz=SHANGHAI_TIMEZONE).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None

    iso_value = normalized.replace("Z", "+00:00")
    try:
        return _local_naive(datetime.fromisoformat(iso_value))
    except ValueError:
        pass

    for date_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y.%m.%d %H:%M:%S",
        "%Y.%m.%d %H:%M",
        "%Y.%m.%d",
    ):
        try:
            return datetime.strptime(normalized, date_format)
        except ValueError:
            pass

    if assume_year:
        month_day_match = re.fullmatch(
            r"(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
            normalized,
        )
        if month_day_match:
            month, day, hour, minute, second = month_day_match.groups()
            try:
                parsed = datetime(
                    reference.year,
                    int(month),
                    int(day),
                    int(hour or 0),
                    int(minute or 0),
                    int(second or 0),
                )
            except ValueError:
                return None
            # 实时新闻跨年时，“12-31”可能对应上一年。
            if parsed > reference + timedelta(days=1):
                parsed = _safe_replace_year(parsed, reference.year - 1)
            return parsed

    if allow_relative:
        relative_text = text.replace(" ", "")
        if relative_text in {"刚刚", "刚才"}:
            return reference
        relative_match = re.fullmatch(r"(\d+)\s*(秒钟?|分钟?|小时|天)前", text)
        if relative_match:
            amount = int(relative_match.group(1))
            unit = relative_match.group(2)
            if unit.startswith("秒"):
                return reference - timedelta(seconds=amount)
            if unit.startswith("分"):
                return reference - timedelta(minutes=amount)
            if unit == "小时":
                return reference - timedelta(hours=amount)
            return reference - timedelta(days=amount)

        day_prefix_match = re.fullmatch(
            r"(今天|今日|昨天|昨日|前天)(?:\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
            text,
        )
        if day_prefix_match:
            prefix, hour, minute, second = day_prefix_match.groups()
            offset = {"今天": 0, "今日": 0, "昨天": 1, "昨日": 1, "前天": 2}[prefix]
            target = reference - timedelta(days=offset)
            return target.replace(
                hour=int(hour or 0),
                minute=int(minute or 0),
                second=int(second or 0),
                microsecond=0,
            )

    if allow_time_only:
        time_match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
        if time_match:
            hour, minute, second = time_match.groups()
            try:
                return reference.replace(
                    hour=int(hour),
                    minute=int(minute),
                    second=int(second or 0),
                    microsecond=0,
                )
            except ValueError:
                return None
    return None


def filter_recent_news_items(items: list, days: int = 2, now: datetime | None = None) -> list:
    """Filter news items to those published within the last N days."""
    current_time = _reference_time(now)
    cutoff_time = current_time - timedelta(days=days)
    result = []
    for item in items:
        publish_time = parse_news_datetime(
            get_news_field(item, "publish_time") or get_news_field(item, "time"),
            now=current_time,
        )
        if publish_time is None or publish_time < cutoff_time or publish_time > current_time:
            continue
        result.append(item)
    return result


def parse_news_time(value: object, now: datetime | None = None) -> datetime:
    """Parse a news timestamp, returning datetime.min when invalid."""
    return parse_news_datetime(value, now=now) or datetime.min


def news_sort_key(item) -> datetime:
    """Return the parsed publication time used to sort a news item."""
    return parse_news_time(get_news_field(item, "publish_time") or get_news_field(item, "time"))


def parse_timestamp(value) -> datetime | None:
    """Parse Unix seconds or milliseconds into a Shanghai-naive datetime.

    资讯管道（``filter_recent_news_items``/``news_sort_key``）统一按北京时间比较，
    这里显式用上海时区，避免依赖服务器 TZ（容器外或未设置 TZ 时本地时间为 UTC，会偏 8 小时）。
    """
    if value in (None, "", 0, "0"):
        return None
    try:
        timestamp = int(float(value))
    except (TypeError, ValueError):
        return None
    if timestamp > 10**12:
        timestamp /= 1000
    try:
        return datetime.fromtimestamp(timestamp, tz=SHANGHAI_TIMEZONE).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError):
        return None
