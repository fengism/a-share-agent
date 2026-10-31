"""SharedTdxhubQuotes 的重建 single-flight、探测移出锁与冷却负缓存回归测试。"""

import threading
import time
from types import SimpleNamespace

import pytest
from tdxhub.exceptions import TdxhubConnectionError
from tdxhub.tdx.deadline import request_budget
from tdxhub.tdx.errors import ResponseHeaderRecvFails

from app.infrastructure.providers import tdxhub as tdxhub_module
from app.infrastructure.providers.tdxhub import SharedTdxhubQuotes, TdxhubUnavailableError

_PROBE_DELAY_SECONDS = 0.2


class _Upstream:
    """模拟 SDK 工厂：记录探测次数，可开关上游可用性。"""

    def __init__(self) -> None:
        self.available = True
        self.probes = 0
        self.proxies: list[str | None] = []
        self.raise_exception: list[bool] = []
        self.servers: list[tuple[str, int] | None] = []
        self.fail_for_preferred = False

    def factory(self, market, timeout, proxy=None, raise_exception=False, server=None):
        self.proxies.append(proxy)
        self.raise_exception.append(raise_exception)
        self.servers.append(server)
        self.probes += 1
        if server is not None and self.fail_for_preferred:
            raise TdxhubConnectionError(f"首选节点 {server} 不可用")
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
    monkeypatch.setattr(tdxhub_module, "_preferred_hq_endpoint", lambda: None)
    monkeypatch.setattr(
        tdxhub_module,
        "Quotes",
        SimpleNamespace(
            factory=lambda market, timeout, proxy=None, raise_exception=False, server=None: upstream.factory(
                market, timeout, proxy, raise_exception, server
            )
        ),
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

    def slow_factory(market, timeout, proxy=None, raise_exception=False, server=None):
        probe_started.set()
        release_probe.wait(timeout=5)
        return original_factory(market, timeout, proxy, raise_exception, server)

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

    tdxhub_module.Quotes = SimpleNamespace(
        factory=lambda market, timeout, proxy=None, raise_exception=False, server=None: _Flaky()
    )
    shared = SharedTdxhubQuotes(_settings_provider())

    assert shared.call("second") == "recovered"
    assert shared.is_cooling_down() is False


def test_transport_error_triggers_rebuild(bind_upstream):
    """round2 读超时/EOF 属于传输故障，必须重建共享客户端而不是把死连接留在缓存里。"""

    class _Flaky:
        def first(self) -> str:
            raise ResponseHeaderRecvFails("round2 响应头接收 0/16 字节失败")

        def second(self) -> str:
            return "recovered"

    tdxhub_module.Quotes = SimpleNamespace(
        factory=lambda market, timeout, proxy=None, raise_exception=False, server=None: _Flaky()
    )
    shared = SharedTdxhubQuotes(_settings_provider())

    assert shared.call("second") == "recovered"


def test_exhausted_io_budget_does_not_rebuild(bind_upstream):
    """预算（request_budget）耗尽是我们自己的墙钟限制，不是链路故障，不应重建客户端。

    资金流按日拉取时预算到点会让 SDK 抛 TimeoutError；把它当连接故障重建，
    等于让已经超时的请求再白付一次全量探测（还可能把实例推进冷却）。
    """

    class _Deadline:
        def ping(self):
            raise TimeoutError("TDX request deadline exceeded")

    shared = SharedTdxhubQuotes(_settings_provider())
    shared._client = _Deadline()
    probes_before = bind_upstream.probes

    with pytest.raises(TimeoutError):
        with request_budget(0.01):
            time.sleep(0.02)
            shared.call("ping")

    assert bind_upstream.probes == probes_before
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


# ------------------------------------------------------- 指数退避冷却


def _backoff_settings(cap: float = 30.0, base: float = 2.0):
    settings = SimpleNamespace(
        tdxhub_timeout_seconds=5.0,
        tdxhub_rebuild_cooldown_seconds=cap,
        tdxhub_rebuild_backoff_base_seconds=base,
    )
    return lambda: settings


def test_first_failure_cools_down_for_backoff_base_only(bind_upstream):
    """单次瞬时失败只应停最短窗口，而不是直接吃掉整个冷却上限。"""
    bind_upstream.available = False
    shared = SharedTdxhubQuotes(_backoff_settings(cap=30.0, base=2.0))

    with pytest.raises(TdxhubUnavailableError):
        shared.call("ping")

    assert 0 < shared.cooldown_remaining_seconds() <= 2.0


def test_cooldown_grows_exponentially_up_to_cap(bind_upstream):
    bind_upstream.available = False
    shared = SharedTdxhubQuotes(_backoff_settings(cap=8.0, base=1.0))

    actual: list[float] = []
    for upper_bound in (1.0, 2.0, 4.0, 8.0, 8.0):
        with pytest.raises(TdxhubUnavailableError):
            shared.call("ping")
        actual.append(shared.cooldown_remaining_seconds())
        assert actual[-1] <= upper_bound
        shared._blocked_until = 0.0  # 只清时间窗，保留连续失败计数

    # 向下抖动不影响增长趋势，封顶后不再增长
    assert actual[0] < actual[1] < actual[2] < actual[3]
    assert actual[4] <= 8.0


def test_successful_rebuild_resets_backoff(bind_upstream):
    bind_upstream.available = False
    shared = SharedTdxhubQuotes(_backoff_settings(cap=30.0, base=2.0))
    for _ in range(3):
        with pytest.raises(TdxhubUnavailableError):
            shared.call("ping")
        shared._blocked_until = 0.0
    assert shared._failures == 3

    bind_upstream.available = True
    assert shared.call("ping").startswith("ok-")
    assert shared._failures == 0
    assert shared.is_cooling_down() is False


# ---------------------------------------------------- raise_exception 语义


def test_raise_exception_flag_is_passed_to_sdk_factory(bind_upstream):
    """历史资金流依赖 SDK 抛异常，普通行情保持返回 None 的宽容语义。"""
    SharedTdxhubQuotes(_settings_provider()).call("ping")
    SharedTdxhubQuotes(_settings_provider(), raise_exception=True).call("ping")

    assert bind_upstream.raise_exception == [False, True]


def test_separate_instances_do_not_share_cooldown(bind_upstream):
    """资金流实例进入冷却不应拖累普通行情，反之亦然。"""
    bind_upstream.available = False
    lenient = SharedTdxhubQuotes(_settings_provider())
    strict = SharedTdxhubQuotes(_settings_provider(), raise_exception=True)

    with pytest.raises(TdxhubUnavailableError):
        strict.call("ping")
    assert strict.is_cooling_down() is True
    assert lenient.is_cooling_down() is False

    bind_upstream.available = True
    assert lenient.call("ping").startswith("ok-")

# ------------------------------------------------------------------ 出站代理接入


def _proxy_settings(**overrides):
    values = {
        "tdxhub_timeout_seconds": 5.0,
        "tdxhub_rebuild_cooldown_seconds": 2.0,
        "outbound_proxy_type": "none",
        "outbound_proxy_url": "",
        "outbound_proxy_scopes": ["eastmoney"],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_proxy_passed_to_factory_when_scope_enabled(bind_upstream):
    settings = _proxy_settings(
        outbound_proxy_type="socks5",
        outbound_proxy_url="socks5://proxy.local:2260",
        outbound_proxy_scopes=["eastmoney", "tdxhub"],
    )
    shared = SharedTdxhubQuotes(lambda: settings)

    assert shared.call("ping") == "ok-1"
    # 地址按配置原样传递（socks5/socks5h 对 TDX 的 IP 目标等价）
    assert bind_upstream.proxies == ["socks5://proxy.local:2260"]


def test_proxy_skipped_when_scope_not_selected(bind_upstream):
    settings = _proxy_settings(
        outbound_proxy_type="http",
        outbound_proxy_url="http://proxy.local:8080",
        outbound_proxy_scopes=["eastmoney"],
    )
    shared = SharedTdxhubQuotes(lambda: settings)

    assert shared.call("ping") == "ok-1"
    assert bind_upstream.proxies == [None]


def test_proxy_config_change_rebuilds_client(bind_upstream):
    settings = _proxy_settings()
    shared = SharedTdxhubQuotes(lambda: settings)

    assert shared.call("ping") == "ok-1"
    settings.outbound_proxy_type = "socks5"
    settings.outbound_proxy_url = "socks5h://proxy.local:2260"
    settings.outbound_proxy_scopes = ["tdxhub"]

    assert shared.call("ping") == "ok-2"
    assert bind_upstream.probes == 2
    assert bind_upstream.proxies == [None, "socks5h://proxy.local:2260"]


# ---------------------------------------------------- 首选节点（BESTIP.HQ）


def test_preferred_endpoint_skips_full_probe(bind_upstream, monkeypatch):
    """后台测速写回的 BESTIP 可用时，冷启动只建连一次而不是全量探测。"""
    monkeypatch.setattr(
        tdxhub_module, "_preferred_hq_endpoint", lambda: ("10.0.0.9", 7709)
    )
    shared = SharedTdxhubQuotes(_settings_provider())

    assert shared.call("ping") == "ok-1"
    assert bind_upstream.servers == [("10.0.0.9", 7709)]


def test_stale_preferred_endpoint_falls_back_to_full_probe(bind_upstream, monkeypatch):
    """首选节点失效时必须回退全量探测，而不是把行情锁死在单节点上。"""
    monkeypatch.setattr(
        tdxhub_module, "_preferred_hq_endpoint", lambda: ("10.0.0.9", 7709)
    )
    bind_upstream.fail_for_preferred = True
    shared = SharedTdxhubQuotes(_settings_provider())

    assert shared.call("ping") == "ok-2"
    assert bind_upstream.servers == [("10.0.0.9", 7709), None]


def test_invalid_proxy_config_falls_back_to_direct(bind_upstream):
    settings = _proxy_settings(
        outbound_proxy_type="socks5",
        # 缺少端口属于非法配置，应按直连降级而不是让行情整体不可用
        outbound_proxy_url="socks5://proxy.local",
        outbound_proxy_scopes=["tdxhub"],
    )
    shared = SharedTdxhubQuotes(lambda: settings)

    assert shared.call("ping") == "ok-1"
    assert bind_upstream.proxies == [None]
