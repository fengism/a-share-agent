"""资讯时间解析：统一按北京时间（Asia/Shanghai），不依赖服务器 TZ。"""

from __future__ import annotations

from datetime import datetime

from app.core.news import parse_timestamp


def test_parse_timestamp_uses_shanghai_timezone() -> None:
    # 1792055090 = 2026-10-15 09:04:50 UTC = 2026-10-15 17:04:50 北京时间
    assert parse_timestamp(1792055090) == datetime(2026, 10, 15, 17, 4, 50)


def test_parse_timestamp_accepts_milliseconds() -> None:
    assert parse_timestamp(1792055090000) == datetime(2026, 10, 15, 17, 4, 50)


def test_parse_timestamp_handles_empty_values() -> None:
    assert parse_timestamp(None) is None
    assert parse_timestamp("") is None
    assert parse_timestamp("0") is None
    assert parse_timestamp("not-a-number") is None
