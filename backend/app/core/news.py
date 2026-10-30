import re
from datetime import datetime, timedelta

from app.core.market import SHANGHAI_TIMEZONE


def get_news_field(item, field: str) -> str:
    """Get a stripped string field from a news dict or object."""
    if isinstance(item, dict):
        return str(item.get(field, "") or "").strip()
    return str(getattr(item, field, "") or "").strip()


def clean_headline(title: str) -> str:
    """去除新闻标题中的平台前缀、电讯头和媒体后缀等噪音。

    例如：
        "【快讯】央行：开展1000亿元逆回购操作" -> "央行：开展1000亿元逆回购操作"
        "【财联社4月15日电】工信部部署新型工业化工作" -> "工信部部署新型工业化工作"
        "财政部发行超长期特别国债（新浪财经）" -> "财政部发行超长期特别国债"
        "工信部发布最新指导意见 - 东方财富网" -> "工信部发布最新指导意见"
    """
    cleaned = title.strip()
    if not cleaned:
        return ""

    # 循环剥离前导方头括号或方括号内容，如 【快讯】、【财联社4月15日电】、[最新消息]
    while cleaned:
        match = re.match(r"^[【\[]([^】\]]*)[】\]]\s*", cleaned)
        if not match:
            break
        cleaned = cleaned[match.end():].strip()

    # 剥离通讯社电讯前缀，如 "财联社4月15日电 "、"新华社北京4月15日电 "、"证券时报网讯 "
    cleaned = re.sub(
        r"^(?:[\u4e00-\u9fa5]{2,10}(?:网|报|社|电讯|财经)?\s*(?:\d{1,2}月\d{1,2}日)?\s*[电讯]\s*[:：，,\s]*)",
        "",
        cleaned,
    ).strip()

    # 剥离末尾括号来源，如 "（新浪财经）"、"(财联社)"、"（来源：证券时报）"
    cleaned = re.sub(
        r"[（\(](?:来源[：:])?[\u4e00-\u9fa5a-zA-Z0-9_\-\s]{2,16}[）\)]\s*$",
        "",
        cleaned,
    ).strip()

    # 剥离末尾破折号/下划线来源，如 "- 华尔街见闻"、"—— 东方财富网"
    cleaned = re.sub(
        r"[-—_~]+\s*[\u4e00-\u9fa5a-zA-Z0-9]{2,12}(?:网|财经|报|社)?\s*$",
        "",
        cleaned,
    ).strip()

    return cleaned


def _normalize_title(title: str) -> str:
    """Normalize a news title for fuzzy equality: clean platform noises, drop
    spaces and punctuation, and normalize case."""
    cleaned = clean_headline(title)
    return "".join(ch for ch in cleaned.casefold() if ch.isalnum())


def _text_similarity(s1: str, s2: str) -> float:
    """计算两个标题的最长公共子序列（LCS）匹配比率（0.0 ~ 1.0）。

    在保持汉字顺序的同时容忍平台插入词（如“今日”、“7天期”），精准捕获跨媒体同质通稿。
    """
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0
    m, n = len(s1), len(s2)
    dp = [0] * (n + 1)
    for ch1 in s1:
        prev = 0
        for j, ch2 in enumerate(s2, 1):
            temp = dp[j]
            if ch1 == ch2:
                dp[j] = prev + 1
            else:
                dp[j] = max(dp[j], dp[j - 1])
            prev = temp
    return (2.0 * dp[n]) / (m + n)


def dedupe_news_items(items: list, fuzzy: bool = True, sim_threshold: float = 0.80) -> list:
    """Remove duplicate news items while preserving their order, with canonical
    prefix/suffix stripping and near-duplicate fuzzy matching."""
    seen_titles: set[str] = set()
    seen_fallback: set[tuple[str, str]] = set()
    accepted_items: list[str] = []
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

        # 针对中长标题的同质化通稿/近重复检查
        if fuzzy and len(normalized) >= 8:
            is_dup = False
            for accepted_norm in accepted_items:
                len_ratio = len(normalized) / max(1, len(accepted_norm))
                if len_ratio < 0.6 or len_ratio > 1.67:
                    continue
                if _text_similarity(normalized, accepted_norm) >= sim_threshold:
                    is_dup = True
                    break
            if is_dup:
                continue

        seen_titles.add(normalized)
        accepted_items.append(normalized)
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
        # 先取整秒，毫秒级时间戳在后面降为浮点秒
        timestamp: float = int(float(value))
    except (TypeError, ValueError):
        return None
    if timestamp > 10**12:
        timestamp /= 1000
    try:
        return datetime.fromtimestamp(timestamp, tz=SHANGHAI_TIMEZONE).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError):
        return None
