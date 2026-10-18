"""Pinned and resource-bounded outbound HTTP transport for the Web fetch tool."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.models import PreparedRequest, Response
from urllib3.connectionpool import HTTPConnectionPool

from app.agentic_integration.tools.packs.web.url_security import ResolvedUrlTarget, UnsafeUrlError

DEFAULT_MAX_RESPONSE_BYTES = 20 * 1024 * 1024
_READ_CHUNK_BYTES = 64 * 1024
_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})


class WebFetchResponseTooLargeError(RuntimeError):
    """Raised before an oversized response can be retained in process memory."""


class PinnedHostAdapter(HTTPAdapter):
    """Connect to one validated IP while verifying TLS for the original host."""

    def __init__(self, target: ResolvedUrlTarget, address: str) -> None:
        super().__init__(max_retries=0)
        self._target = target
        self._address = address

    def get_connection_with_tls_context(
        self,
        request: PreparedRequest,
        verify: bool | str,
        proxies: dict[str, str] | None = None,
        cert: Any = None,
    ) -> HTTPConnectionPool:
        if proxies:
            raise UnsafeUrlError("安全 Web 抓取不支持代理转发")
        host_params, pool_kwargs = self.build_connection_pool_key_attributes(request, verify, cert)
        host_params["host"] = self._address
        host_params["port"] = self._target.port
        if self._target.scheme == "https":
            pool_kwargs["assert_hostname"] = self._target.hostname
            pool_kwargs["server_hostname"] = self._target.hostname
        return self.poolmanager.connection_from_host(**host_params, pool_kwargs=pool_kwargs)


def _read_bounded_response(response: Response, max_response_bytes: int) -> None:
    if response.status_code in _REDIRECT_STATUS_CODES:
        response.close()
        response._content = b""
        response._content_consumed = True
        return

    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            declared_bytes = int(content_length)
        except ValueError:
            declared_bytes = -1
        if declared_bytes > max_response_bytes:
            response.close()
            raise WebFetchResponseTooLargeError(
                f"Content-Length {declared_bytes} 超过 Web 抓取上限 {max_response_bytes} 字节"
            )

    chunks: list[bytes] = []
    received_bytes = 0
    try:
        for chunk in response.iter_content(chunk_size=_READ_CHUNK_BYTES):
            if not chunk:
                continue
            if not isinstance(chunk, bytes):
                chunk = chunk.encode(response.encoding or "utf-8")
            received_bytes += len(chunk)
            if received_bytes > max_response_bytes:
                raise WebFetchResponseTooLargeError(
                    f"实际响应体超过 Web 抓取上限 {max_response_bytes} 字节"
                )
            chunks.append(chunk)
    except BaseException:
        response.close()
        raise
    response._content = b"".join(chunks)
    response._content_consumed = True


def request_pinned(
    url: str,
    target: ResolvedUrlTarget,
    address: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int | float = 15,
    allow_redirects: bool = False,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> Response:
    """Issue one bounded request without resolving the origin again."""
    if allow_redirects:
        raise UnsafeUrlError("固定 DNS 传输必须由调用方逐跳处理重定向")
    if max_response_bytes <= 0:
        raise ValueError("max_response_bytes 必须大于 0")

    parsed = urlparse(url)
    request_host = (parsed.hostname or "").encode("idna").decode("ascii").lower()
    if parsed.scheme.lower() != target.scheme or request_host != target.hostname:
        raise UnsafeUrlError("固定连接目标与请求 URL 不一致")
    if address not in target.addresses:
        raise UnsafeUrlError("连接地址不在已验证 DNS 结果中")

    request_headers = dict(headers or {})
    request_headers["Host"] = target.host_header
    adapter = PinnedHostAdapter(target, address)
    with requests.Session() as session:
        session.trust_env = False
        session.mount(f"{target.scheme}://", adapter)
        response = session.get(
            url,
            headers=request_headers,
            timeout=timeout,
            allow_redirects=False,
            stream=True,
        )
        _read_bounded_response(response, max_response_bytes)
        return response
