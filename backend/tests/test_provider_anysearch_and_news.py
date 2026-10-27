"""离线 fixture 测试：AnySearch 适配器与新闻时间解析。

这两个模块此前覆盖率 0%，而它们的失效方式全是"静默"的：上游换个字段名、返回空
``title``、多 key 轮换把被限流的 key 继续用、时间字符串解析不出来→时间变成空。
这里用注入的 transport/clock/settings 把这些路径按住，完全不需要外网。
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime

import pytest
import requests

from app.infrastructure.providers.anysearch import (
    AnySearchKeysUnavailableError,
    AnySearchProvider,
    AnySearchResponseError,
    _parse_api_keys,
    _query_with_time_range,
    _retry_after_seconds,
)
from app.infrastructure.providers.news import parse_struct_time_string


class _FakeResponse:
    def __init__(self, payload=None, *, status_code: int = 200, headers: dict | None = None, text: str = "") -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class _Settings:
    def __init__(self, api_key: str = "") -> None:
        self.anysearch_api_key = api_key


class _Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def _provider(transport, *, api_key: str = "", clock: _Clock | None = None, today: date = date(2026, 10, 22)):
    return AnySearchProvider(
        transport=transport,
        settings_provider=lambda: _Settings(api_key),
        today_provider=lambda: today,
        clock=clock or _Clock(),
    )


def _ok_payload(results: list[dict]) -> dict:
    return {"code": 0, "data": {"results": results}}


# ── 纯函数 ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  ", ()),
        ("k1", ("k1",)),
        ("k1,k2", ("k1", "k2")),
        ("k1\nk2", ("k1", "k2")),
        ('["k1", "k2"]', ("k1", "k2")),
        ("k1,k1", ("k1",)),  # 去重：重复 key 不该拿到双份流量
        ("k1,***,k2", ("k1", "k2")),  # 掩码值不能当成真 key 发出去
    ],
)
def test_parse_api_keys(raw: str, expected: tuple[str, ...]) -> None:
    assert _parse_api_keys(raw) == expected


def test_query_with_time_range_appends_beijing_window() -> None:
    query = _query_with_time_range("茅台 业绩", "week", date(2026, 10, 22))
    assert query.startswith("茅台 业绩 时间范围：")
    assert "2026-10-15 至 2026-10-22" in query
    assert "北京时间" in query


def test_query_with_unknown_time_range_is_untouched() -> None:
    assert _query_with_time_range("q", "any", date(2026, 10, 22)) == "q"


def test_retry_after_numeric_and_http_date() -> None:
    assert _retry_after_seconds(_FakeResponse(headers={"Retry-After": "30"})) == 30.0
    future = format_datetime(datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=40))
    value = _retry_after_seconds(_FakeResponse(headers={"Retry-After": future}))
    assert value is not None and 30.0 <= value <= 45.0
    assert _retry_after_seconds(_FakeResponse(headers={"Retry-After": "not-a-date"})) is None
    assert _retry_after_seconds(_FakeResponse(headers={})) is None


# ── 响应归一化 ────────────────────────────────────────────


def test_search_normalizes_envelope() -> None:
    seen: list[dict] = []

    def transport(url, **kwargs):
        seen.append({"url": url, **kwargs})
        return _FakeResponse(
            _ok_payload(
                [
                    {"title": "标题", "url": "https://a", "snippet": "摘要", "publish_time": "2026-10-20"},
                    {"url": "https://b", "content": "正文"},  # 无 title → 回落 URL；无 snippet → 用 content
                    {"title": "无链接"},
                    "not-a-dict",
                ]
            )
        )

    results = _provider(transport).search("q", max_results=10, tag="news")

    assert [item["href"] for item in results] == ["https://a", "https://b", ""]
    assert results[0]["published_at"] == "2026-10-20"
    assert results[1]["title"] == "https://b"
    assert results[1]["body"] == "正文"
    assert "published_at" not in results[1]
    # 请求体：中文默认 language、tag 透传、max_results 夹到上限 10
    payload = seen[0]["json_body"]
    assert payload["language"] == "zh-CN"
    assert payload["tag"] == "news"
    assert payload["max_results"] == 10


def test_max_results_is_clamped_and_applied() -> None:
    def transport(url, **kwargs):
        return _FakeResponse(_ok_payload([{"url": f"https://{i}"} for i in range(20)]))

    results = _provider(transport).search("q", max_results=99)
    assert len(results) == 10
    results = _provider(transport).search("q", max_results=0)
    assert len(results) == 1


@pytest.mark.parametrize(
    "response",
    [
        _FakeResponse(None),
        _FakeResponse({"code": 1, "data": {}}),
        _FakeResponse({"code": 0, "data": {}}),
        _FakeResponse({"code": 0, "data": {"results": "nope"}}),
    ],
)
def test_malformed_envelopes_raise(response) -> None:
    def transport(url, **kwargs):
        return response

    with pytest.raises(AnySearchResponseError):
        _provider(transport).search("q")


# ── 多 key 轮换与冷却 ─────────────────────────────────────


def _http_error(status: int, headers: dict | None = None) -> requests.HTTPError:
    response = _FakeResponse(status_code=status, headers=headers)
    error = requests.HTTPError(f"{status}")
    error.response = response
    return error


def test_rotates_away_from_rate_limited_key_and_recovers_after_cooldown() -> None:
    clock = _Clock()
    used: list[str] = []

    def transport(url, *, headers=None, **kwargs):
        key = headers.get("Authorization", "")
        used.append(key)
        if key == "Bearer k1":
            raise _http_error(429, {"Retry-After": "120"})
        return _FakeResponse(_ok_payload([{"url": "https://ok"}]))

    provider = _provider(transport, api_key="k1,k2", clock=clock)
    assert [item["href"] for item in provider.search("q")] == ["https://ok"]
    assert used == ["Bearer k1", "Bearer k2"]

    # 冷却期内 k1 不再参与轮换（否则每次搜索都白撞一次 429）
    used.clear()
    clock.now += 30
    provider.search("q")
    provider.search("q")
    assert set(used) == {"Bearer k2"}

    # 冷却结束后恢复（Retry-After 120s）
    used.clear()
    clock.now += 200
    provider.search("q")
    provider.search("q")
    assert "Bearer k1" in used


def test_permanently_rejected_key_is_disabled() -> None:
    def transport(url, *, headers=None, **kwargs):
        raise _http_error(401)

    provider = _provider(transport, api_key="bad")
    with pytest.raises(AnySearchKeysUnavailableError):
        provider.search("q")


def test_non_key_scoped_status_is_propagated() -> None:
    def transport(url, *, headers=None, **kwargs):
        raise _http_error(500)

    with pytest.raises(requests.HTTPError):
        _provider(transport, api_key="k1").search("q")


def test_missing_key_still_calls_without_authorization() -> None:
    seen: dict = {}

    def transport(url, *, headers=None, **kwargs):
        seen.update(headers)
        return _FakeResponse(_ok_payload([]))

    assert _provider(transport).search("q") == []
    assert "Authorization" not in seen


# ── 新闻时间解析 ──────────────────────────────────────────


def test_parse_struct_time_from_struct_time_object() -> None:
    value = time.struct_time((2026, 10, 20, 8, 30, 5, 0, 0, 0))
    assert parse_struct_time_string(value) == "2026-10-20 08:30:05"


def test_parse_struct_time_from_repr_string() -> None:
    text = "time.struct_time(tm_year=2026, tm_mon=10, tm_mday=20, tm_hour=8, tm_min=30, tm_sec=5, tm_wday=1, tm_yday=293, tm_isdst=0)"
    assert parse_struct_time_string(text) == "2026-10-20 08:30:05"


@pytest.mark.parametrize("value", [None, "", "garbage", "tm_year=2026"])
def test_parse_struct_time_returns_empty_on_unknown_input(value) -> None:
    assert parse_struct_time_string(value) == ""
