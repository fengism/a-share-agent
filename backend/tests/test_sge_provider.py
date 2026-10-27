"""上金所 provider 的频率风控防护与错误分类测试。"""

from __future__ import annotations

import threading
import time

import pytest
from curl_cffi.requests import exceptions as curl_errors

from app.core.exceptions import UpstreamRateLimitedError
from app.infrastructure.providers import sge as sge_module
from app.infrastructure.providers.provider_policy import classify_provider_error, is_retryable


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError(f"不应走到 raise_for_status: {self.status_code}")

    def json(self) -> dict:
        return self._payload


@pytest.fixture(autouse=True)
def _reset_throttle():
    """每个用例都从「允许立即放行」开始，避免节流串味。"""
    original = sge_module._throttle
    sge_module._throttle = sge_module._MinIntervalThrottle(0.0)
    yield
    sge_module._throttle = original


def test_rate_limited_error_is_retryable() -> None:
    category = classify_provider_error(UpstreamRateLimitedError("too fast"))
    assert category == "rate_limit"
    assert is_retryable(category) is True


def test_fetch_returns_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    def _fake_post(url, **kwargs):
        seen["url"] = url
        seen["data"] = kwargs.get("data")
        return _FakeResponse(200, {"time": [["2026-10-12", 904.5, 902.9, 900.0, 911.9]]})

    monkeypatch.setattr(sge_module.curl_requests, "post", _fake_post)

    payload = sge_module.sge_provider.fetch("Au99.99")

    assert payload["time"][0][0] == "2026-10-12"
    assert seen["data"] == {"instid": "Au99.99"}
    assert seen["url"] == sge_module._SGE_URL


def test_403_becomes_rate_limited_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sge_module.curl_requests,
        "post",
        lambda url, **kwargs: _FakeResponse(403),
    )

    with pytest.raises(UpstreamRateLimitedError):
        sge_module.sge_provider.fetch("Au99.99")


def test_non_403_error_is_not_misreported_as_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ServerError(_FakeResponse):
        def raise_for_status(self) -> None:
            raise curl_errors.HTTPError("500 Server Error")

    monkeypatch.setattr(
        sge_module.curl_requests,
        "post",
        lambda url, **kwargs: _ServerError(500),
    )

    with pytest.raises(curl_errors.HTTPError):
        sge_module.sge_provider.fetch("Au99.99")


#: 计时类断言的容差：线程唤醒/上下文切换会带来几十微秒抖动，
#: 不放容差时 0.19991s 这样的值会让 CI 随机失败。
_TIMING_TOLERANCE = 0.02


def test_throttle_enforces_minimum_interval() -> None:
    throttle = sge_module._MinIntervalThrottle(0.2)

    started = time.monotonic()
    throttle.acquire()
    throttle.acquire()
    throttle.acquire()
    elapsed = time.monotonic() - started

    # 三次放行之间有两个间隔，至少 0.4s。
    # _MinIntervalThrottle 用「放行时刻 + 间隔」计算下一次允许时间，
    # 调用方记录的墙上时间会包含微秒级的调度抖动，这里留 20ms 容差，
    # 避免极偶发的 0.1999s 让 CI 变红（真正的串行性由下面的并发用例保证）。
    assert elapsed >= 0.4 - _TIMING_TOLERANCE


def test_throttle_serializes_concurrent_callers() -> None:
    throttle = sge_module._MinIntervalThrottle(0.2)
    release_times: list[float] = []

    def worker() -> None:
        throttle.acquire()
        release_times.append(time.monotonic())

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(release_times) == 3
    ordered = sorted(release_times)
    # 并发调用也必须串行，彼此间隔不小于最小间隔（留调度抖动容差）
    assert ordered[1] - ordered[0] >= 0.2 - _TIMING_TOLERANCE
    assert ordered[2] - ordered[1] >= 0.2 - _TIMING_TOLERANCE


def test_zero_interval_disables_throttle() -> None:
    throttle = sge_module._MinIntervalThrottle(0.0)

    started = time.monotonic()
    for _ in range(5):
        throttle.acquire()

    assert time.monotonic() - started < 0.1