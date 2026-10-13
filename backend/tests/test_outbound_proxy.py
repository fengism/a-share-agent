"""公共出站代理的单元测试：代理解析（通用）+ 东财接入点。"""

from __future__ import annotations

import pytest
import requests

from app.configuration import get_settings
from app.infrastructure.http.proxy import (
    PROXY_TYPE_HTTP,
    PROXY_TYPE_NONE,
    PROXY_TYPE_SOCKS5,
    DIRECT_REQUEST,
    ProxyConfigError,
    ProxyScope,
    normalize_proxy_url,
    resolve_outbound_proxy,
    resolve_proxy_request,
)

KLINE_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
FUND_FLOW_URL = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
PUSH2_URL = "https://push2.eastmoney.com/api/qt/clist/get"

# 东财 provider 实际使用的作用域，等价于 base.py 中的 _PROXY_SCOPE
EASTMONEY_SCOPE = ProxyScope(
    hosts=frozenset({"push2his.eastmoney.com"}),
    path_prefixes=("/api/qt/stock/kline/get", "/api/qt/stock/fflow/daykline/get"),
)


class _FakeSettings:
    """最小化的 Settings 替身，仅用于代理解析的纯函数测试。"""

    def __init__(
        self,
        proxy_type: str = PROXY_TYPE_NONE,
        proxy_url: str = "",
        timeout: float = 20.0,
        retries: int = 2,
    ) -> None:
        self.outbound_proxy_type = proxy_type
        self.outbound_proxy_url = proxy_url
        self.outbound_proxy_timeout_seconds = timeout
        self.outbound_proxy_retries = retries


_FIELD_ALIASES = {
    "proxy_type": "outbound_proxy_type",
    "proxy_url": "outbound_proxy_url",
    "timeout": "outbound_proxy_timeout_seconds",
    "retries": "outbound_proxy_retries",
}


def _patch_settings(monkeypatch: pytest.MonkeyPatch, **overrides) -> None:
    """基于真实 Settings 覆盖代理相关字段，避免替身与实际字段漂移。"""
    overrides = {_FIELD_ALIASES.get(key, key): value for key, value in overrides.items()}
    overrides.setdefault("eastmoney_min_interval_seconds", 0.0)
    overrides.setdefault("eastmoney_jitter_min_seconds", 0.0)
    overrides.setdefault("eastmoney_jitter_max_seconds", 0.0)
    settings = get_settings().model_copy(update=overrides)
    monkeypatch.setattr(
        "app.infrastructure.providers.eastmoney.base.get_settings",
        lambda: settings,
    )


# ────────────────────────── 通用能力：作用域 ──────────────────────────


def test_scope_matches_declared_host_and_paths() -> None:
    assert EASTMONEY_SCOPE.matches(KLINE_URL) is True
    assert EASTMONEY_SCOPE.matches(FUND_FLOW_URL) is True


@pytest.mark.parametrize("url", [DATACENTER_URL, PUSH2_URL, "https://www.baidu.com"])
def test_scope_excludes_other_hosts(url: str) -> None:
    assert EASTMONEY_SCOPE.matches(url) is False


def test_scope_excludes_undeclared_paths_on_same_host() -> None:
    url = "https://push2his.eastmoney.com/api/qt/stock/trends2/get"
    assert EASTMONEY_SCOPE.matches(url) is False


def test_scope_without_path_prefixes_covers_whole_host() -> None:
    scope = ProxyScope(hosts=frozenset({"example.com"}))
    assert scope.matches("https://example.com/any/path") is True
    assert scope.matches("https://other.com/any/path") is False


def test_scope_is_hostname_case_insensitive() -> None:
    scope = ProxyScope(hosts=frozenset({"example.com"}))
    assert scope.matches("https://EXAMPLE.com/path") is True


def test_none_scope_applies_proxy_to_every_url() -> None:
    settings = _FakeSettings(proxy_type=PROXY_TYPE_HTTP, proxy_url="http://proxy.local:3128")
    # scope=None 表示 provider 要求所有流量都走代理
    assert resolve_outbound_proxy(DATACENTER_URL, settings, None) is not None
    # 而同一个代理配置在东财作用域下对数据中心接口不生效
    assert resolve_outbound_proxy(DATACENTER_URL, settings, EASTMONEY_SCOPE) is None


# ────────────────────────── 通用能力：地址解析 ──────────────────────────


def test_scheme_is_inferred_from_proxy_type() -> None:
    assert normalize_proxy_url("proxy.local:3128", PROXY_TYPE_HTTP) == "http://proxy.local:3128"
    assert normalize_proxy_url("user:pw@proxy.local:2260", PROXY_TYPE_SOCKS5) == (
        "socks5h://user:pw@proxy.local:2260"
    )


def test_https_http_proxy_scheme_is_accepted() -> None:
    assert normalize_proxy_url("https://proxy.local:8443", PROXY_TYPE_HTTP) == "https://proxy.local:8443"


@pytest.mark.parametrize(
    ("raw_url", "proxy_type", "expected_message"),
    [
        ("", PROXY_TYPE_HTTP, "不能为空"),
        ("proxy.local 3128", PROXY_TYPE_HTTP, "不能包含空格"),
        ("socks5h://proxy.local:2260", PROXY_TYPE_HTTP, "不匹配"),
        ("http://proxy.local:3128", PROXY_TYPE_SOCKS5, "不匹配"),
        ("http://", PROXY_TYPE_HTTP, "缺少主机名"),
        ("proxy.local:notaport", PROXY_TYPE_HTTP, "端口非法"),
        ("socks5h://proxy.local", PROXY_TYPE_SOCKS5, "必须指定端口"),
    ],
)
def test_invalid_proxy_address_is_rejected(raw_url: str, proxy_type: str, expected_message: str) -> None:
    with pytest.raises(ProxyConfigError) as excinfo:
        normalize_proxy_url(raw_url, proxy_type)
    assert expected_message in str(excinfo.value)


def test_unsupported_proxy_type_is_rejected() -> None:
    with pytest.raises(ProxyConfigError) as excinfo:
        normalize_proxy_url("proxy.local:3128", "socks6")
    assert "不支持的代理类型" in str(excinfo.value)


def test_proxy_address_is_redacted_for_logging() -> None:
    settings = _FakeSettings(proxy_type=PROXY_TYPE_HTTP, proxy_url="http://user:pass@proxy.local:3128")
    proxy = resolve_outbound_proxy(KLINE_URL, settings, EASTMONEY_SCOPE)
    assert proxy is not None
    redacted = proxy.redacted
    assert "pass" not in redacted
    assert redacted.endswith("@proxy.local:3128")


def test_redaction_keeps_address_when_no_credentials() -> None:
    settings = _FakeSettings(proxy_type=PROXY_TYPE_HTTP, proxy_url="http://proxy.local:3128")
    proxy = resolve_outbound_proxy(KLINE_URL, settings, EASTMONEY_SCOPE)
    assert proxy is not None
    assert proxy.redacted == "http://proxy.local:3128"


def test_proxies_payload_covers_both_schemes() -> None:
    settings = _FakeSettings(proxy_type=PROXY_TYPE_HTTP, proxy_url="http://proxy.local:3128")
    proxy = resolve_outbound_proxy(KLINE_URL, settings, EASTMONEY_SCOPE)
    assert proxy is not None
    # K 线走 http、资金流走 https，两者都必须带代理
    assert proxy.proxies() == {
        "http": "http://proxy.local:3128",
        "https": "http://proxy.local:3128",
    }


def test_disabled_proxy_returns_direct_request() -> None:
    settings = _FakeSettings(proxy_type=PROXY_TYPE_NONE, proxy_url="http://proxy.local:3128")
    assert resolve_proxy_request(KLINE_URL, settings, EASTMONEY_SCOPE) is DIRECT_REQUEST


def test_empty_url_is_treated_as_disabled() -> None:
    settings = _FakeSettings(proxy_type=PROXY_TYPE_HTTP, proxy_url="   ")
    assert resolve_proxy_request(KLINE_URL, settings, EASTMONEY_SCOPE) is DIRECT_REQUEST


def test_request_options_include_timeout_and_retries() -> None:
    settings = _FakeSettings(
        proxy_type=PROXY_TYPE_HTTP,
        proxy_url="http://user:pass@proxy.local:3128",
        timeout=25.0,
        retries=3,
    )
    options = resolve_proxy_request(KLINE_URL, settings, EASTMONEY_SCOPE)
    assert options.active is True
    assert options.proxies == {
        "http": "http://user:pass@proxy.local:3128",
        "https": "http://user:pass@proxy.local:3128",
    }
    assert options.timeout == 25.0
    assert options.retries == 3


def test_request_options_tolerate_garbage_numeric_settings() -> None:
    settings = _FakeSettings(proxy_type=PROXY_TYPE_HTTP, proxy_url="http://proxy.local:3128")
    settings.outbound_proxy_timeout_seconds = "not-a-number"
    settings.outbound_proxy_retries = None
    options = resolve_proxy_request(KLINE_URL, settings, EASTMONEY_SCOPE)
    assert options.timeout is None
    assert options.retries == 0


def test_proxy_settings_are_exposed_as_persisted_global_keys() -> None:
    settings = get_settings()
    assert settings.outbound_proxy_type in {PROXY_TYPE_NONE, PROXY_TYPE_HTTP, PROXY_TYPE_SOCKS5}
    assert 5 <= settings.outbound_proxy_timeout_seconds <= 120
    assert 0 <= settings.outbound_proxy_retries <= 6


# ────────────────────────── 东财接入点 ──────────────────────────


class _FakeResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None


def _build_provider():
    from app.infrastructure.providers.eastmoney.base import EastMoneyBase

    return EastMoneyBase()


def test_kline_request_passes_configured_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, proxy_type=PROXY_TYPE_HTTP, proxy_url="http://proxy.local:3128")
    provider = _build_provider()
    captured: dict = {}

    def _fake_get(url, **kwargs):
        captured.update(kwargs)
        captured["url"] = url
        return _FakeResponse()

    monkeypatch.setattr(provider.em_session, "get", _fake_get)

    provider.em_get_response(KLINE_URL, params={"secid": "1.000001"}, timeout=10)

    assert captured["proxies"] == {"http": "http://proxy.local:3128", "https": "http://proxy.local:3128"}
    # 走代理时使用独立的代理超时，而不是接口默认超时
    assert captured["timeout"] == 20.0
    # 会话级代理仍然保持清空，避免污染其它东财接口
    assert provider.em_session.proxies == {"http": None, "https": None}
    assert provider.em_session.trust_env is False


def test_other_endpoints_are_requested_without_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, proxy_type=PROXY_TYPE_HTTP, proxy_url="http://proxy.local:3128")
    provider = _build_provider()
    captured: dict = {}

    def _fake_get(url, **kwargs):
        captured.update(kwargs)
        captured["url"] = url
        return _FakeResponse()

    monkeypatch.setattr(provider.em_session, "get", _fake_get)

    provider.em_get_response(DATACENTER_URL, timeout=15)

    assert captured["proxies"] is None
    assert captured["timeout"] == 15


def test_disabled_proxy_keeps_direct_request(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, proxy_type=PROXY_TYPE_NONE, proxy_url="http://proxy.local:3128")
    provider = _build_provider()
    captured: dict = {}

    def _fake_get(url, **kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(provider.em_session, "get", _fake_get)

    provider.em_get_response(FUND_FLOW_URL, timeout=15)

    assert captured["proxies"] is None
    assert captured["timeout"] == 15


def test_proxy_request_retries_transient_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(
        monkeypatch,
        proxy_type=PROXY_TYPE_HTTP,
        proxy_url="http://proxy.local:3128",
        retries=2,
    )
    provider = _build_provider()
    monkeypatch.setattr("app.infrastructure.providers.eastmoney.base.time.sleep", lambda _seconds: None)

    attempts: list[int] = []

    def _flaky_get(url, **kwargs):
        attempts.append(1)
        if len(attempts) < 3:
            raise requests.ConnectionError("proxy tunnel closed")
        return _FakeResponse()

    monkeypatch.setattr(provider.em_session, "get", _flaky_get)

    provider.em_get_response(FUND_FLOW_URL, timeout=15)

    assert len(attempts) == 3


def test_proxy_request_gives_up_after_retry_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(
        monkeypatch,
        proxy_type=PROXY_TYPE_HTTP,
        proxy_url="http://proxy.local:3128",
        retries=1,
    )
    provider = _build_provider()
    monkeypatch.setattr("app.infrastructure.providers.eastmoney.base.time.sleep", lambda _seconds: None)

    attempts: list[int] = []

    def _always_fail(url, **kwargs):
        attempts.append(1)
        raise requests.ConnectionError("proxy tunnel closed")

    monkeypatch.setattr(provider.em_session, "get", _always_fail)

    with pytest.raises(requests.ConnectionError):
        provider.em_get_response(FUND_FLOW_URL, timeout=15)

    assert len(attempts) == 2


def test_direct_requests_are_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(
        monkeypatch,
        proxy_type=PROXY_TYPE_HTTP,
        proxy_url="http://proxy.local:3128",
        retries=3,
    )
    provider = _build_provider()
    attempts: list[int] = []

    def _always_fail(url, **kwargs):
        attempts.append(1)
        raise requests.ConnectionError("connection reset")

    monkeypatch.setattr(provider.em_session, "get", _always_fail)

    with pytest.raises(requests.ConnectionError):
        provider.em_get_response(DATACENTER_URL, timeout=15)

    assert len(attempts) == 1


# ──────────────────── 代理抖动不得误伤上游风控冷却 ────────────────────


def test_proxy_failures_do_not_trigger_host_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    """代理隧道抖动不代表东财封禁，不应冷却整个 host。"""
    _patch_settings(
        monkeypatch,
        proxy_type=PROXY_TYPE_HTTP,
        proxy_url="http://proxy.local:3128",
        retries=0,
    )
    provider = _build_provider()

    def _always_fail(url, **kwargs):
        raise requests.ConnectionError("proxy tunnel closed")

    monkeypatch.setattr(provider.em_session, "get", _always_fail)

    # 连续失败期间（熔断打开前）host 始终不应被误判为风控
    for _ in range(3):
        with pytest.raises(requests.ConnectionError):
            provider.em_get_response(FUND_FLOW_URL, timeout=15)

    assert provider.em_cooldown_remaining(FUND_FLOW_URL) == 0.0
    assert provider._em_transient_failures_by_host.get("push2his.eastmoney.com", 0) == 0
    assert provider._em_proxy_failures == 3


def test_proxy_breaker_opens_after_repeated_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """代理连续失败达到阈值后熔断，后续请求跳过代理，不再空等超时。"""
    _patch_settings(
        monkeypatch,
        proxy_type=PROXY_TYPE_HTTP,
        proxy_url="http://proxy.local:3128",
        retries=0,
    )
    provider = _build_provider()
    attempts: list[dict] = []

    def _always_fail(url, **kwargs):
        attempts.append(kwargs)
        raise requests.ConnectionError("proxy tunnel closed")

    monkeypatch.setattr(provider.em_session, "get", _always_fail)

    for _ in range(3):
        with pytest.raises(requests.ConnectionError):
            provider.em_get_response(FUND_FLOW_URL, timeout=15)

    assert provider._proxy_breaker_open() is True

    # 熔断期内的新请求不再携带代理参数
    with pytest.raises(requests.ConnectionError):
        provider.em_get_response(FUND_FLOW_URL, timeout=15)

    assert attempts[-1]["proxies"] is None


def test_proxy_breaker_expires_then_recovers_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """熔断按时间到期，之后重新走代理；一次成功的代理请求清零计数。"""
    _patch_settings(
        monkeypatch,
        proxy_type=PROXY_TYPE_HTTP,
        proxy_url="http://proxy.local:3128",
        retries=0,
    )
    provider = _build_provider()

    def _fail(url, **kwargs):
        raise requests.ConnectionError("proxy tunnel closed")

    monkeypatch.setattr(provider.em_session, "get", _fail)
    for _ in range(3):
        with pytest.raises(requests.ConnectionError):
            provider.em_get_response(FUND_FLOW_URL, timeout=15)
    assert provider._proxy_breaker_open() is True

    # 熔断期内走直连：直连成功不代表代理已恢复，熔断保持开启
    monkeypatch.setattr(provider.em_session, "get", lambda url, **kwargs: _FakeResponse())
    provider.em_get_response(FUND_FLOW_URL, timeout=15)
    assert provider._proxy_breaker_open() is True

    # 冷却期满后恢复走代理
    provider._em_proxy_open_until = 0.0
    attempts: list[dict] = []

    def _ok(url, **kwargs):
        attempts.append(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(provider.em_session, "get", _ok)
    provider.em_get_response(FUND_FLOW_URL, timeout=15)

    assert attempts[-1]["proxies"] == {
        "http": "http://proxy.local:3128",
        "https": "http://proxy.local:3128",
    }
    assert provider._em_proxy_failures == 0
    assert provider._proxy_breaker_open() is False


def test_direct_failures_still_trigger_host_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    """关闭代理后，真实的连接失败仍按原逻辑触发冷却。"""
    _patch_settings(
        monkeypatch,
        proxy_type=PROXY_TYPE_NONE,
        retries=0,
    )
    provider = _build_provider()

    def _always_fail(url, **kwargs):
        raise requests.ConnectionError("connection reset")

    monkeypatch.setattr(provider.em_session, "get", _always_fail)

    for _ in range(3):
        with pytest.raises(requests.ConnectionError):
            provider.em_get_response(FUND_FLOW_URL, timeout=15)

    assert provider.em_cooldown_remaining(FUND_FLOW_URL) > 0.0
    assert provider._em_transient_failures_by_host.get("push2his.eastmoney.com") == 3


def test_successful_proxy_request_resets_proxy_failure_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(
        monkeypatch,
        proxy_type=PROXY_TYPE_HTTP,
        proxy_url="http://proxy.local:3128",
        retries=0,
    )
    provider = _build_provider()

    def _fail_once(url, **kwargs):
        # 由被测代码自己累加计数，这里只负责抛出连接异常
        raise requests.ConnectionError("proxy tunnel closed")

    monkeypatch.setattr(provider.em_session, "get", _fail_once)
    with pytest.raises(requests.ConnectionError):
        provider.em_get_response(FUND_FLOW_URL, timeout=15)
    assert provider._em_proxy_failures == 1

    monkeypatch.setattr(provider.em_session, "get", lambda url, **kwargs: _FakeResponse())
    provider.em_get_response(FUND_FLOW_URL, timeout=15)
    assert provider._em_proxy_failures == 0