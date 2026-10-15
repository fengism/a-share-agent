"""Shared outbound proxy support for upstream data providers.

Some upstreams reject requests by source IP (many CN market-data vendors answer
HTTP 403 to overseas datacentre addresses). One operator-managed proxy can be
configured once and then adopted by any provider that needs it, without
duplicating proxy parsing or leaking credentials into logs.

Providers opt in by declaring a :class:`ProxyScope` (which hosts/paths may use
the proxy) and calling :func:`resolve_proxy_request` per request:

    _PROXY_SCOPE = ProxyScope(hosts=frozenset({"push2his.example.com"}))
    options = resolve_proxy_request(url, settings, _PROXY_SCOPE)
    response = session.get(url, proxies=options.proxies, timeout=options.timeout)

Passing ``scope=None`` makes the proxy apply to every URL, which suits providers
that route all traffic through one host. Hosts outside a provider's declared
scope always stay direct, so enabling the proxy can never silently change
behaviour for endpoints that rely on direct access.

This module only depends on the standard library so it stays cheap to import and
easy to test in isolation.
"""

from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)

PROXY_TYPE_NONE = "none"
PROXY_TYPE_HTTP = "http"
PROXY_TYPE_SOCKS5 = "socks5"
PROXY_TYPES = (PROXY_TYPE_NONE, PROXY_TYPE_HTTP, PROXY_TYPE_SOCKS5)

_ALLOWED_SCHEMES = {
    PROXY_TYPE_HTTP: ("http", "https"),
    PROXY_TYPE_SOCKS5: ("socks5h", "socks5", "socks4a", "socks4"),
}
_DEFAULT_SCHEME = {
    PROXY_TYPE_HTTP: "http",
    # socks5h lets the proxy resolve DNS, avoiding local resolution and leaks
    PROXY_TYPE_SOCKS5: "socks5h",
}
_SOCKS_DEPENDENCY_HINT = (
    "SOCKS5 代理需要额外依赖，请安装 PySocks（pip install 'requests[socks]'）或 socksio"
)

SETTING_TYPE = "outbound_proxy_type"
SETTING_URL = "outbound_proxy_url"
SETTING_TIMEOUT = "outbound_proxy_timeout_seconds"
SETTING_RETRIES = "outbound_proxy_retries"


class ProxyConfigError(ValueError):
    """代理配置非法（协议不匹配、缺少主机或端口等）。"""


def _safe_port(split) -> int | None:
    """urlsplit 的 port 属性在端口非法时会抛错，这里统一降级为 None。"""
    try:
        return split.port
    except ValueError as exc:
        raise ProxyConfigError(f"代理端口非法: {exc}") from exc


@dataclass(frozen=True, slots=True)
class ProxyScope:
    """描述哪些上游请求允许走代理。

    Param:
        hosts: 允许走代理的主机名（小写比较）
        path_prefixes: 允许走代理的路径前缀；为空表示该主机下所有路径
    """

    hosts: frozenset[str]
    path_prefixes: tuple[str, ...] = field(default=())

    def matches(self, url: str) -> bool:
        """判断 URL 是否落在本作用域内。"""
        split = urlsplit(url)
        hostname = (split.hostname or "").lower()
        if hostname not in self.hosts:
            return False
        if not self.path_prefixes:
            return True
        path = split.path or ""
        return any(path.startswith(prefix) for prefix in self.path_prefixes)


@dataclass(frozen=True, slots=True)
class OutboundProxy:
    """一条已规范化的代理配置。"""

    proxy_type: str
    url: str

    @property
    def is_socks(self) -> bool:
        return self.proxy_type == PROXY_TYPE_SOCKS5

    @property
    def redacted(self) -> str:
        """可安全写入日志的脱敏形式，例如 socks5h://user:***@host:2260。"""
        split = urlsplit(self.url)
        if not split.username and not split.password:
            return urlunsplit((split.scheme, split.netloc, "", "", ""))
        netloc = f"{split.username or ''}:***@{split.hostname or ''}"
        port = _safe_port(split)
        if port:
            netloc = f"{netloc}:{port}"
        return urlunsplit((split.scheme, netloc, "", "", ""))

    def proxies(self) -> dict[str, str]:
        """构造 requests 的 proxies 参数，同时覆盖 http 与 https 目标。"""
        return {"http": self.url, "https": self.url}


@dataclass(frozen=True, slots=True)
class ProxyRequestOptions:
    """单次请求应使用的代理参数。"""

    proxies: dict[str, str] | None = None
    timeout: float | None = None
    retries: int = 0

    @property
    def active(self) -> bool:
        return self.proxies is not None


DIRECT_REQUEST = ProxyRequestOptions()
"""未启用代理时的请求参数（保持直连与调用方默认超时）。"""


def normalize_proxy_url(raw_url: str, proxy_type: str) -> str:
    """校验并规范化代理地址。

    Param:
        raw_url: 用户填写的代理地址，可省略协议头
        proxy_type: 代理类型 "http" 或 "socks5"
    Return:
        str: 带协议头的代理地址
    """
    if proxy_type not in _ALLOWED_SCHEMES:
        raise ProxyConfigError(f"不支持的代理类型: {proxy_type}")

    value = (raw_url or "").strip()
    if not value:
        raise ProxyConfigError("代理地址不能为空")
    if any(ch.isspace() for ch in value):
        raise ProxyConfigError("代理地址不能包含空格或换行")

    if "://" not in value:
        value = f"{_DEFAULT_SCHEME[proxy_type]}://{value}"

    split = urlsplit(value)
    scheme = (split.scheme or "").lower()
    if scheme == "socks":
        scheme = "socks5h"
    if scheme not in _ALLOWED_SCHEMES[proxy_type]:
        allowed = "/".join(_ALLOWED_SCHEMES[proxy_type])
        raise ProxyConfigError(
            f"代理地址协议 {scheme or '(空)'} 与所选代理类型不匹配，支持: {allowed}"
        )
    if not split.hostname:
        raise ProxyConfigError("代理地址缺少主机名，请形如 host:port")
    port = _safe_port(split)
    if scheme.startswith("socks") and not port:
        raise ProxyConfigError("SOCKS5 代理必须指定端口，例如 socks5h://user:pass@host:2260")

    return urlunsplit((scheme, split.netloc, "", "", ""))


def socks_support_available() -> bool:
    """检查运行环境是否具备 SOCKS 代理依赖（PySocks 或 socksio）。"""
    for module_name in ("socks", "socksio"):
        if importlib.util.find_spec(module_name) is not None:
            return True
    return False


def resolve_outbound_proxy(
    url: str,
    settings,
    scope: ProxyScope | None = None,
) -> OutboundProxy | None:
    """解析当前请求应使用的代理，不需要代理时返回 None。

    Param:
        url: 请求地址
        settings: 应用配置对象
        scope: 允许走代理的作用域；None 表示对所有地址生效
    Return:
        OutboundProxy | None: 规范化后的代理配置
    """
    if scope is not None and not scope.matches(url):
        return None

    proxy_type = str(getattr(settings, SETTING_TYPE, PROXY_TYPE_NONE) or PROXY_TYPE_NONE)
    raw_url = str(getattr(settings, SETTING_URL, "") or "")
    if proxy_type == PROXY_TYPE_NONE or not raw_url.strip():
        return None

    proxy = OutboundProxy(proxy_type=proxy_type, url=normalize_proxy_url(raw_url, proxy_type))
    if proxy.is_socks and not socks_support_available():
        logger.error("出站代理已配置为 SOCKS5，但运行环境缺少依赖: %s", _SOCKS_DEPENDENCY_HINT)
        raise ProxyConfigError(_SOCKS_DEPENDENCY_HINT)

    logger.debug("出站代理生效: %s", proxy.redacted)
    return proxy


def resolve_proxy_request(
    url: str,
    settings,
    scope: ProxyScope | None = None,
) -> ProxyRequestOptions:
    """解析单次请求的代理、超时与重试参数。

    Param:
        url: 请求地址
        settings: 应用配置对象
        scope: 允许走代理的作用域；None 表示对所有地址生效
    Return:
        ProxyRequestOptions: 未启用代理时为 DIRECT_REQUEST
    """
    proxy = resolve_outbound_proxy(url, settings, scope)
    if proxy is None:
        return DIRECT_REQUEST

    timeout = getattr(settings, SETTING_TIMEOUT, None)
    retries = getattr(settings, SETTING_RETRIES, 0)
    try:
        timeout_value = float(timeout) if timeout is not None else None
    except (TypeError, ValueError):
        timeout_value = None
    try:
        retry_value = max(0, int(retries))
    except (TypeError, ValueError):
        retry_value = 0
    return ProxyRequestOptions(proxies=proxy.proxies(), timeout=timeout_value, retries=retry_value)