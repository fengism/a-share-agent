"""SharedTdxhubQuotes 的重建 single-flight、探测移出锁与冷却负缓存回归测试。"""

import threading
import time
from types import SimpleNamespace

import pytest
from tdxhub.exceptions import TdxhubConnectionError

from app.infrastructure.providers import tdxhub as tdxhub_module
from app.infrastructure.providers.tdxhub import SharedTdxhubQuotes, TdxhubUnavailableError

_PROBE_DELAY_SECONDS = 0.2


class _Upstream:
    """模拟 SDK 工厂：记录探测次数，可开关上游可用性。"""

    def __init__(self) -> None:
        self.available = True
        self.probes = 0

    def factory(self, market, timeout):
        self.probes += 1
        time.sleep(_PROBE_DELAY_SECONDS)  # 模拟全量服务器探测耗时
        if not self.available:
            raise TdxhubConnectionError("无法连接任何可用的标准行情服务器")
        probes = self.probes

        class _Client:
            def ping(self):
                return f"ok-{probes}"

            def broken(self):
                raise TdxhubConnectionError("行情服务器断连")

        return _Client()


def _settings_provider(cooldown_seconds: float = 2.0):
    settings = SimpleNamespace(
        tdxhub_timeout_seconds=5.0,
        tdxhub_rebuild_cooldown_seconds=cooldown_seconds,
    )
    return lambda: settings


@pytest.fixture
def bind_upstream(monkeypatch):
    upstream = _Upstream()
    monkeypatch.setattr(
        tdxhub_module,
        "Quotes",
        SimpleNamespace(factory=lambda market, timeout: upstream.factory(market, timeout)),
    )
    return upstream


def test_concurrent_failures_probe_only_once(bind_upstream):
    """上游全挂时并发请求不得各自触发一次昂贵的全量探测。"""
    bind_upstream.available = False
    shared = SharedTdxhubQuotes(_settings_provider())
    errors: list[str] = []
    barrier = threading.Barrier(8)

    def worker() -> None:
        barrier.wait()
        try:
            shared.call("broken")
        except Exception as error:  # noqa: BLE001 - 断言异常类型
            errors.append(type(error).__name__)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert bind_upstream.probes == 1
    assert set(errors) == {TdxhubUnavailableError.__name__}


def test_cooling_down_fails_fast_without_probing(bind_upstream):
    bind_upstream.available = False
    shared = SharedTdxhubQuotes(_settings_provider())
    with pytest.raises(TdxhubUnavailableError):
        shared.call("ping")

    probes_after_failure = bind_upstream.probes
    started_at = time.monotonic()
    for _ in range(5):
        with pytest.raises(TdxhubUnavailableError):
            shared.call("ping")
    elapsed = time.monotonic() - started_at

    assert bind_upstream.probes == probes_after_failure
    assert elapsed < 0.05
    assert shared.is_cooling_down() is True
    assert shared.cooldown_remaining_seconds() > 0


def test_recovers_automatically_after_cooldown(bind_upstream):
    """冷却只缓存时间窗、不缓存 IP 黑名单：到期后应重新探测并自愈。"""
    bind_upstream.available = False
    shared = SharedTdxhubQuotes(_settings_provider(cooldown_seconds=0.05))
    with pytest.raises(TdxhubUnavailableError):
        shared.call("ping")

    probes_after_failure = bind_upstream.probes
    bind_upstream.available = True
    time.sleep(0.06)

    assert shared.is_cooling_down() is False
    assert shared.call("ping") == "ok-2"
    assert bind_upstream.probes == probes_after_failure + 1


def test_concurrent_callers_reuse_inflight_rebuild(bind_upstream):
    """并发请求应等待同一次重建并复用其结果，而不是各自探测或被运维入口阻塞。"""
    probe_started = threading.Event()
    release_probe = threading.Event()
    original_factory = bind_upstream.factory

    def slow_factory(market, timeout):
        probe_started.set()
        release_probe.wait(timeout=5)
        return original_factory(market, timeout)

    tdxhub_module.Quotes = SimpleNamespace(factory=slow_factory)
    shared = SharedTdxhubQuotes(_settings_provider())

    results: list[str] = []
    threads = [
        threading.Thread(target=lambda: results.append(shared.call("ping"))),
        threading.Thread(target=lambda: results.append(shared.call("ping"))),
    ]
    for thread in threads:
        thread.start()
    assert probe_started.wait(timeout=5)

    # 探测进行中，运维入口必须仍然可用（探测不持有串行锁）。
    assert shared.is_cooling_down() is False
    shared.reset()

    release_probe.set()
    for thread in threads:
        thread.join(timeout=5)

    assert bind_upstream.probes == 1
    assert results == ["ok-1", "ok-1"]


def test_rebuilds_once_after_transport_error(bind_upstream):
    """连接异常应重建客户端并重试一次，而不是让异常直接冒给调用方。"""

    class _Flaky:
        def first(self) -> str:
            raise TdxhubConnectionError("行情服务器断连")

        def second(self) -> str:
            return "recovered"

    tdxhub_module.Quotes = SimpleNamespace(factory=lambda market, timeout: _Flaky())
    shared = SharedTdxhubQuotes(_settings_provider())

    assert shared.call("second") == "recovered"
    assert shared.is_cooling_down() is False


def test_reset_drops_client_and_clear_cooldown_releases_circuit(bind_upstream):
    shared = SharedTdxhubQuotes(_settings_provider())
    shared.call("ping")
    probes_before_reset = bind_upstream.probes

    shared.reset()
    shared.call("ping")
    assert bind_upstream.probes == probes_before_reset + 1

    shared._blocked_until = time.monotonic() + 60
    assert shared.is_cooling_down() is True
    shared.clear_cooldown()
    assert shared.is_cooling_down() is False