"""出网目标校验，挡住 SSRF 指向的云元数据与内网地址。

**为什么需要**：``llm_base_url`` 允许用户自填（自建 Ollama / 中转网关是既定功能），
后端会带着用户的 API Key 主动请求该地址。若不做目标校验，任何登录用户都能让服务器
访问 ``169.254.169.254``（AWS/GCP 元数据）、``100.100.100.200``（阿里云元数据）或
内网管理端口，并把响应前若干字符带回给自己（``/settings/llm/models`` 的错误信息里就
含响应体片段）。

**三段式策略**（默认即安全，本地自建照常可用）：

1. **始终拦截**：云元数据与链路本地网段（``169.254.0.0/16``、``100.64.0.0/10`` 等）、
   组播/保留段、元数据域名。自建模型永远不会用到这些目标。
2. **始终允许回环**：``127.0.0.0/8``、``::1``。这是 Ollama 等"本机自建"的默认地址
   （见 ``provider_catalog``），拦截它会让开箱即用的本地模型直接不可用。
3. **需要显式开启**：RFC1918（``10/8``、``172.16/12``、``192.168/16``）与 IPv6 ULA
   ``fc00::/7``。默认**关闭**，因为 ``llm_base_url`` 是任意登录用户可写的字段——
   放开后任何账号都能把服务器当成内网探测器（Redis、内部管理后台、内网 API 都能探）。
   同机 docker-compose 用服务名（如 ``http://ollama:11434`` 解析到 172.x）时，
   显式设置 ``LLM_ALLOW_PRIVATE_ENDPOINTS=true`` 即可。

**已知局限**：这里校验的是**解析结果**，而真正的连接由 httpx/openai 客户端再次解析，
理论上存在 DNS rebinding 的 TOCTOU 窗口。彻底关闭需要把解析结果固定到连接
（自定义 transport），成本远高于收益：攻击者仍需控制一个能通过首次解析的域名，
且只能拿到我们自己发出的错误信息片段。故保留为"尽力而为"的校验，并在文档里写明。
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

#: 无论配置如何都拦截的网段：云元数据、链路本地、无效源地址、组播/保留段。
_ALWAYS_BLOCKED_NETWORKS = (
    ipaddress.ip_network("169.254.0.0/16"),  # 链路本地，含 AWS/GCP/Azure 元数据 169.254.169.254
    ipaddress.ip_network("100.64.0.0/10"),  # CGNAT，含阿里云元数据 100.100.100.200
    ipaddress.ip_network("0.0.0.0/8"),  # 未指定地址（部分系统语义上等同本机）
    ipaddress.ip_network("224.0.0.0/4"),  # IPv4 组播
    ipaddress.ip_network("240.0.0.0/4"),  # IPv4 保留段
    ipaddress.ip_network("fe80::/10"),  # IPv6 链路本地
    ipaddress.ip_network("ff00::/8"),  # IPv6 组播
)

#: 回环：始终允许（Ollama 等本机自建的默认地址）。
_LOOPBACK_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
)

#: RFC1918 / IPv6 ULA：默认拦截，需 ``LLM_ALLOW_PRIVATE_ENDPOINTS=true`` 才放行。
_PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),  # IPv6 唯一本地地址
)

#: 元数据服务的域名形式（GCP / AWS 的部分部署）。
_BLOCKED_HOSTNAMES = frozenset(
    {
        "metadata",
        "metadata.google.internal",
        "metadata.goog",
        "instance-data",
        "instance-data.ec2.internal",
    }
)

_Address = ipaddress.IPv4Address | ipaddress.IPv6Address


class OutboundUrlBlockedError(ValueError):
    """目标地址被出网策略拒绝。

    ``reason`` 已是可展示的中文说明，调用方应原样透出（不要吞掉，否则用户只会看到
    超时，无法判断是策略拦截还是网络问题）。
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _parse_ip(host: str) -> _Address | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _resolve(host: str) -> tuple[_Address, ...] | None:
    """解析主机名；失败返回 ``None``（交给真正的请求去报错）。"""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError):
        return None
    addresses: list[_Address] = []
    for info in infos:
        raw = str(info[4][0]).split("%", 1)[0]  # 去掉 IPv6 scope id
        address = _parse_ip(raw)
        if address is not None and address not in addresses:
            addresses.append(address)
    return tuple(addresses) or None


def describe_blocked_target(url: str, *, allow_private: bool) -> str | None:
    """检查 URL 是否是允许的出网目标。

    Param:
        url: 待校验的完整 URL（含 scheme）。
        allow_private: 是否允许回环/RFC1918/IPv6 ULA 目标。
    Return:
        ``None`` 表示放行；否则返回中文拦截原因。
    """
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        return f"只支持 http/https，当前为 {scheme or '(空)'}"

    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return "URL 缺少主机名"
    if host in _BLOCKED_HOSTNAMES:
        return f"目标是云元数据域名 {host}"

    literal = _parse_ip(host)
    addresses = (literal,) if literal is not None else _resolve(host)
    if addresses is None:
        # 解析不了就让真实请求去产生"连接失败"，这里的职责只是拒绝已知危险目标。
        return None

    for address in addresses:
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
            address = address.ipv4_mapped
        if any(address in network for network in _ALWAYS_BLOCKED_NETWORKS):
            return f"目标 {address} 属于元数据/链路本地网段"
        if any(address in network for network in _LOOPBACK_NETWORKS):
            continue  # 本机自建（Ollama 默认地址）始终可用
        if not allow_private and any(address in network for network in _PRIVATE_NETWORKS):
            return (
                f"目标 {address} 属于内网地址；如需指向同机 docker 服务名或内网网关，"
                "请设置 LLM_ALLOW_PRIVATE_ENDPOINTS=true（本机 127.0.0.1 无需设置）"
            )
    return None


#: 跟随重定向的最大跳数（每一跳都要重新校验目标）。
MAX_REDIRECT_HOPS = 3


def resolve_redirect_target(current_url: str, location: str, *, allow_private: bool) -> str:
    """把 ``Location`` 解析成绝对地址并校验，返回可继续请求的目标。

    只校验第一跳是不够的：``requests`` 默认跟随 3xx，公网 URL 完全可以用 302 把
    服务端引到 ``169.254.169.254``。因此这里要求调用方逐跳校验（见 ``MAX_REDIRECT_HOPS``）。

    Raise:
        OutboundUrlBlockedError: 重定向目标被策略拒绝。
    """
    target = urljoin(current_url, location or "")
    ensure_outbound_url_allowed(target, allow_private=allow_private)
    return target


def ensure_outbound_url_allowed(url: str, *, allow_private: bool) -> None:
    """放行则返回，否则抛 :class:`OutboundUrlBlockedError`。"""
    reason = describe_blocked_target(url, allow_private=allow_private)
    if reason is not None:
        raise OutboundUrlBlockedError(reason)


__all__ = [
    "MAX_REDIRECT_HOPS",
    "OutboundUrlBlockedError",
    "describe_blocked_target",
    "ensure_outbound_url_allowed",
    "resolve_redirect_target",
]
