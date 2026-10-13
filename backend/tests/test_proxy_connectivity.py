"""出站代理连通性探测端点的单元测试。"""

from __future__ import annotations

import pytest
import requests

from app.api.errors import ApiError
from app.api.routes import settings as settings_routes
from app.api.routes.settings import ProxyTestRequest, ProxyTestResponse
from app.configuration import get_settings
from app.infrastructure.http.proxy import PROXY_TYPE_HTTP, PROXY_TYPE_NONE

_ADMIN = {"id": 1, "username": "admin", "is_admin": True}
_TARGET = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
_ALIASES = {
    "proxy_type": "outbound_proxy_type",
    "proxy_url": "outbound_proxy_url",
    "timeout": "outbound_proxy_timeout_seconds",
    "retries": "outbound_proxy_retries",
}


def _patch_settings(monkeypatch: pytest.MonkeyPatch, **overrides):
    overrides = {_ALIASES.get(key, key): value for key, value in overrides.items()}
    settings = get_settings().model_copy(update=overrides)
    monkeypatch.setattr("app.api.routes.settings.get_settings", lambda: settings)
    return settings


def _patch_requests(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    monkeypatch.setattr("app.api.routes.settings.requests.get", handler)


class _FakeResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


async def _run() -> ProxyTestResponse:
    # 通过模块引用调用，避免被 pytest 误当作测试用例收集
    return await settings_routes.test_outbound_proxy(ProxyTestRequest(), _ADMIN)


@pytest.mark.asyncio
async def test_reports_disabled_proxy_without_any_request(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, proxy_type=PROXY_TYPE_NONE, proxy_url="http://proxy.local:3128")
    called = []

    def _unexpected(url, **kwargs):
        called.append(url)
        raise AssertionError("代理未启用时不应发起探测请求")

    _patch_requests(monkeypatch, _unexpected)

    response = await _run()

    assert response.ok is True
    assert response.proxy_enabled is False
    assert response.message == "出站代理未启用（直连）"
    assert called == []


@pytest.mark.asyncio
async def test_reports_exit_ip_and_latency_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, proxy_type=PROXY_TYPE_HTTP, proxy_url="http://proxy.local:3128", timeout=15.0)
    seen_proxies = []

    def _handler(url, **kwargs):
        seen_proxies.append(kwargs.get("proxies"))
        if "ipify" in url:
            return _FakeResponse(200, "203.0.113.7\n")
        return _FakeResponse(200, '{"rc":0}')

    _patch_requests(monkeypatch, _handler)

    response = await _run()

    assert response.ok is True
    assert response.proxy_enabled is True
    assert response.exit_ip == "203.0.113.7"
    assert "203.0.113.7" in response.message
    assert response.latency_ms >= 0
    # 探测与出口 IP 查询都必须经过同一代理
    assert all(proxies == {"http": "http://proxy.local:3128", "https": "http://proxy.local:3128"}
               for proxies in seen_proxies)


@pytest.mark.asyncio
async def test_treats_upstream_403_as_connected_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """代理链路打通即算连通：上游 403 属于业务风控，不代表代理故障。"""
    _patch_settings(monkeypatch, proxy_type=PROXY_TYPE_HTTP, proxy_url="http://proxy.local:3128", timeout=15.0)

    def _handler(url, **kwargs):
        if "ipify" in url:
            return _FakeResponse(200, "203.0.113.8")
        return _FakeResponse(403, "403 Forbidden")

    _patch_requests(monkeypatch, _handler)

    response = await _run()

    assert response.ok is True
    assert response.exit_ip == "203.0.113.8"
    assert "HTTP 403" in response.message


@pytest.mark.asyncio
async def test_reports_failure_when_proxy_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, proxy_type=PROXY_TYPE_HTTP, proxy_url="http://proxy.local:3128", timeout=5.0)

    def _handler(url, **kwargs):
        if "ipify" in url:
            raise requests.ConnectionError("exit ip lookup failed")
        raise requests.ConnectionError("proxy tunnel closed")

    _patch_requests(monkeypatch, _handler)

    response = await _run()

    assert response.ok is False
    assert response.proxy_enabled is True
    assert response.exit_ip is None
    assert "ConnectionError" in response.message


@pytest.mark.asyncio
async def test_ignores_non_ip_body_from_exit_ip_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """代理返回错误页时不能把 HTML 当成出口 IP。"""
    _patch_settings(monkeypatch, proxy_type=PROXY_TYPE_HTTP, proxy_url="http://proxy.local:3128", timeout=15.0)

    def _handler(url, **kwargs):
        if "ipify" in url:
            return _FakeResponse(200, "<html>proxy error</html>")
        return _FakeResponse(200, '{"rc":0}')

    _patch_requests(monkeypatch, _handler)

    response = await _run()

    assert response.ok is True
    assert response.exit_ip is None
    assert "出口 IP" not in response.message


@pytest.mark.asyncio
async def test_invalid_proxy_address_returns_422(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(
        monkeypatch,
        proxy_type=PROXY_TYPE_HTTP,
        proxy_url="socks5h://proxy.local:2260",
        timeout=15.0,
    )

    with pytest.raises(ApiError) as excinfo:
        await _run()

    assert excinfo.value.status_code == 422
    assert excinfo.value.code == "config.proxy_invalid"


@pytest.mark.asyncio
async def test_upstream_5xx_is_reported_as_not_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, proxy_type=PROXY_TYPE_HTTP, proxy_url="http://proxy.local:3128", timeout=15.0)

    def _handler(url, **kwargs):
        if "ipify" in url:
            raise requests.ConnectionError("nope")
        return _FakeResponse(502, "Bad Gateway")

    _patch_requests(monkeypatch, _handler)

    response = await _run()

    assert response.ok is False
    assert "HTTP 502" in response.message