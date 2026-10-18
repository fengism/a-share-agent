"""会话 Cookie Secure 标志的协议探测测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.api.auth import cookies


def _request(*, scheme: str, forwarded_proto: str | None = None) -> Request:
    headers = []
    if forwarded_proto is not None:
        headers.append((b"x-forwarded-proto", forwarded_proto.encode()))
    return Request(
        {
            "type": "http",
            "scheme": scheme,
            "method": "GET",
            "path": "/api/auth/login",
            "query_string": b"",
            "headers": headers,
            "server": ("testserver", 80),
        }
    )


def test_secure_request_trusts_forwarded_proto_only_when_configured() -> None:
    assert cookies._is_secure_request(
        scheme="http", forwarded_proto="https", trust_proxy_headers=True
    )
    assert not cookies._is_secure_request(
        scheme="http", forwarded_proto="https", trust_proxy_headers=False
    )
    assert cookies._is_secure_request(
        scheme="https", forwarded_proto=None, trust_proxy_headers=False
    )
    assert not cookies._is_secure_request(
        scheme="http", forwarded_proto="http", trust_proxy_headers=True
    )


def test_resolve_secure_cookie_uses_request_scheme_and_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cookies, "get_settings", lambda: SimpleNamespace(trust_proxy_headers=True))

    assert cookies.resolve_secure_cookie(_request(scheme="http", forwarded_proto="https"), False) is True
    assert cookies.resolve_secure_cookie(_request(scheme="http", forwarded_proto="http"), False) is False
    # 显式配置为 True 时无条件 Secure。
    assert cookies.resolve_secure_cookie(_request(scheme="http"), True) is True
