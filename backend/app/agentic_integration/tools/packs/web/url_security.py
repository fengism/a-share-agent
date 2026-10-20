"""URL classification and SSRF-safe DNS resolution helpers."""

from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from urllib.parse import urlparse

Resolver = Callable[..., Sequence[tuple]]
_DEFAULT_PORTS = {"http": 80, "https": 443}


@dataclass(frozen=True, slots=True)
class ResolvedUrlTarget:
    """One URL origin whose complete DNS answer set has been validated."""

    scheme: str
    hostname: str
    port: int
    addresses: tuple[str, ...]

    @property
    def host_header(self) -> str:
        host = f"[{self.hostname}]" if ":" in self.hostname else self.hostname
        default_port = _DEFAULT_PORTS[self.scheme]
        return host if self.port == default_port else f"{host}:{self.port}"


def is_twitter_url(url: str) -> bool:
    """Return whether a URL belongs to X/Twitter."""
    host = (urlparse(url).hostname or "").lower()
    return host in ("x.com", "twitter.com") or host.endswith(".x.com") or host.endswith(".twitter.com")


def parse_tweet_url(url: str) -> tuple[str, str]:
    """Extract a username and tweet ID from an X/Twitter status URL."""
    match = re.search(r"(?:x\.com|twitter\.com)/(\w+)/status/(\d+)", url)
    if match:
        return match.group(1), match.group(2)
    raise ValueError(f"Cannot parse tweet URL: {url}")


class UnsafeUrlError(ValueError):
    """Raised when an outbound URL cannot be proven to target the public Internet."""


def _normalize_public_address(host: str, raw_address: str) -> str:
    try:
        address = ipaddress.ip_address(raw_address)
    except ValueError as error:
        raise UnsafeUrlError(f"主机名返回无效地址: {host} -> {raw_address}") from error
    if not address.is_global:
        raise UnsafeUrlError(f"拒绝访问非公网地址: {host} -> {address.compressed}")
    return address.compressed


def validate_url_syntax(url: str) -> tuple[str, str, int]:
    """Validate browser-safe HTTP(S) URL syntax without performing DNS I/O."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in _DEFAULT_PORTS:
        raise UnsafeUrlError(f"仅支持 http/https，拒绝 scheme={parsed.scheme!r}")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeUrlError("URL 不允许包含用户名或密码")
    raw_hostname = parsed.hostname
    if not raw_hostname:
        raise UnsafeUrlError("URL 缺少主机名")
    try:
        hostname = raw_hostname.encode("idna").decode("ascii").lower()
        port = parsed.port or _DEFAULT_PORTS[scheme]
    except (UnicodeError, ValueError) as error:
        raise UnsafeUrlError("URL 主机名或端口无效") from error
    return scheme, hostname, port


def resolve_url_target(url: str, *, resolver: Resolver = socket.getaddrinfo) -> ResolvedUrlTarget:
    """Resolve and validate every address for a URL before a connection is attempted.

    The returned addresses are the exact addresses that the transport must use. A
    caller must not resolve ``hostname`` again after this function returns.
    """
    scheme, hostname, port = validate_url_syntax(url)

    try:
        addr_infos = resolver(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise UnsafeUrlError(f"主机名解析失败: {hostname}") from error

    addresses: list[str] = []
    for info in addr_infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        address = _normalize_public_address(hostname, str(sockaddr[0]))
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise UnsafeUrlError(f"主机名未解析到可用公网地址: {hostname}")

    return ResolvedUrlTarget(
        scheme=scheme,
        hostname=hostname,
        port=port,
        addresses=tuple(addresses),
    )
