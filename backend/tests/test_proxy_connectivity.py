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

# ------------------------------------------------- TDX 原始 TCP 链路探测

from app.api.routes.settings import TdxProxyTestResponse  # noqa: E402
from app.infrastructure.providers import tdxhub as tdxhub_module  # noqa: E402
from app.infrastructure.providers.tdxhub import probe_tdx_connectivity  # noqa: E402


class _FakeRound2:
    """模拟 round2 客户端：分别控制建连与行情协议两个阶段。"""

    def __init__(self, *, proxy=None, connect_timeout=5.0):
        self.proxy = proxy
        self.connect_timeout = connect_timeout
        self.closed = False
        self.connect_error: Exception | None = None
        self.bars_error: Exception | None = None

    def connect(self, ip, port, time_out=None):
        if self.connect_error is not None:
            raise self.connect_error
        return self

    def get_security_bars(self, category, market, code, start=0, count=1):
        if self.bars_error is not None:
            raise self.bars_error
        import pandas as pd

        return pd.DataFrame([{"time": "2026-09-30", "open": 10.0}])

    def close(self) -> None:
        self.closed = True


def _patch_tdx(monkeypatch: pytest.MonkeyPatch, *, connect_error=None, bars_error=None, endpoints=None):
    instances: list[_FakeRound2] = []

    def _factory(**kwargs):
        client = _FakeRound2(**kwargs)
        client.connect_error = connect_error
        client.bars_error = bars_error
        instances.append(client)
        return client

    monkeypatch.setattr(tdxhub_module, "Round2Client", _factory)
    monkeypatch.setattr(
        tdxhub_module,
        "_hq_endpoints",
        lambda limit: (endpoints if endpoints is not None else [("10.0.0.9", 7709)])[:limit],
    )
    return instances


async def _run_tdx() -> TdxProxyTestResponse:
    return await settings_routes.test_tdx_proxy(_ADMIN)


@pytest.mark.asyncio
async def test_tdx_probe_reports_success_through_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _patch_settings(
        monkeypatch,
        proxy_type=PROXY_TYPE_HTTP,
        proxy_url="http://proxy.local:3128",
        outbound_proxy_scopes=["eastmoney", "tdxhub"],
    )
    instances = _patch_tdx(monkeypatch)

    response = await _run_tdx()

    assert response.ok is True
    assert response.stage == "ok"
    assert response.endpoint == "10.0.0.9:7709"
    assert response.proxy_enabled is True
    assert "代理隧道" in response.message
    # 探测必须真的走代理，否则测的就不是隧道
    assert instances[0].proxy is not None
    assert settings.outbound_proxy_type == PROXY_TYPE_HTTP
    assert instances[0].closed is True


@pytest.mark.asyncio
async def test_tdx_probe_reports_direct_route_when_scope_not_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(
        monkeypatch,
        proxy_type=PROXY_TYPE_HTTP,
        proxy_url="http://proxy.local:3128",
        outbound_proxy_scopes=["eastmoney"],
    )
    instances = _patch_tdx(monkeypatch)

    response = await _run_tdx()

    assert response.ok is True
    assert response.proxy_enabled is False
    assert "直连" in response.message
    assert instances[0].proxy is None


@pytest.mark.asyncio
async def test_tdx_probe_distinguishes_tunnel_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(
        monkeypatch,
        proxy_type=PROXY_TYPE_HTTP,
        proxy_url="http://proxy.local:3128",
        outbound_proxy_scopes=["tdxhub"],
    )
    _patch_tdx(monkeypatch, connect_error=ConnectionError("proxy tunnel closed"))

    response = await _run_tdx()

    assert response.ok is False
    assert response.stage == "connect"
    assert "代理隧道不可用" in response.message


@pytest.mark.asyncio
async def test_tdx_probe_distinguishes_protocol_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """隧道通了但目标节点协议不可用时，不能误报成代理故障。"""
    _patch_settings(
        monkeypatch,
        proxy_type=PROXY_TYPE_HTTP,
        proxy_url="http://proxy.local:3128",
        outbound_proxy_scopes=["tdxhub"],
    )
    _patch_tdx(monkeypatch, bars_error=RuntimeError("ProtocolError: 快照记录 marker 未找到"))

    response = await _run_tdx()

    assert response.ok is False
    assert response.stage == "protocol"
    assert "目标行情节点不可用" in response.message


@pytest.mark.asyncio
async def test_tdx_probe_falls_back_to_next_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, proxy_type=PROXY_TYPE_NONE)
    _patch_tdx(
        monkeypatch,
        endpoints=[("10.0.0.1", 7709), ("10.0.0.2", 7709)],
    )
    calls: list[str] = []

    class _Fallback(_FakeRound2):
        def connect(self, ip, port, time_out=None):
            calls.append(ip)
            if ip == "10.0.0.1":
                raise ConnectionError("node down")
            return self

    monkeypatch.setattr(tdxhub_module, "Round2Client", lambda **kwargs: _Fallback(**kwargs))

    response = await _run_tdx()

    assert response.ok is True
    assert response.endpoint == "10.0.0.2:7709"
    assert calls == ["10.0.0.1", "10.0.0.2"]


@pytest.mark.asyncio
async def test_tdx_probe_reports_empty_candidate_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, proxy_type=PROXY_TYPE_NONE)
    _patch_tdx(monkeypatch, endpoints=[])

    response = await _run_tdx()

    assert response.ok is False
    assert response.stage == "config"
    assert response.endpoint is None


@pytest.mark.asyncio
async def test_tdx_probe_invalid_proxy_address_returns_422(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(
        monkeypatch,
        proxy_type=PROXY_TYPE_HTTP,
        proxy_url="socks5h://proxy.local:2260",
        outbound_proxy_scopes=["tdxhub"],
    )

    with pytest.raises(ApiError) as excinfo:
        await _run_tdx()

    assert excinfo.value.status_code == 422
    assert excinfo.value.code == "config.proxy_invalid"


def test_tdx_probe_function_returns_plain_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings().model_copy(update={"outbound_proxy_type": PROXY_TYPE_NONE})
    _patch_tdx(monkeypatch)

    result = probe_tdx_connectivity(settings)

    assert set(result) == {
        "ok",
        "endpoint",
        "stage",
        "proxy_enabled",
        "proxy_type",
        "latency_ms",
        "message",
    }


def test_tdx_probe_success_releases_shared_client_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    """探测成功即视为链路恢复：两个共享实例的重建冷却都要提前解除。"""
    settings = get_settings().model_copy(update={"outbound_proxy_type": PROXY_TYPE_NONE})
    _patch_tdx(monkeypatch)

    class _StubShared:
        def __init__(self) -> None:
            self.released = 0

        def clear_cooldown(self) -> None:
            self.released += 1

    lenient, strict = _StubShared(), _StubShared()
    monkeypatch.setattr(tdxhub_module, "shared_tdxhub_quotes", lenient)
    monkeypatch.setattr(tdxhub_module, "shared_tdxhub_raise_quotes", strict)

    assert probe_tdx_connectivity(settings)["ok"] is True
    assert (lenient.released, strict.released) == (1, 1)

    # 探测失败不得动冷却状态，否则会变成"失败也重试"的风暴入口
    _patch_tdx(monkeypatch, connect_error=OSError("refused"))
    assert probe_tdx_connectivity(settings)["ok"] is False
    assert (lenient.released, strict.released) == (1, 1)
