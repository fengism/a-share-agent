"""URL 工具函数：链接判断、安全校验、短链解析等通用 URL 操作。

被 Web Tool Pack 和 AgentExecutor 复用。
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse


def is_twitter_url(url: str) -> bool:
    """判断 URL 是否为 X/Twitter 链接（按主机名匹配 x.com / twitter.com）。

    Param:
        url: 待判断的 URL
    Return:
        True 表示是 X/Twitter 链接
    """
    host = (urlparse(url).hostname or "").lower()
    return (
        host in ("x.com", "twitter.com")
        or host.endswith(".x.com")
        or host.endswith(".twitter.com")
    )


def parse_tweet_url(url: str) -> tuple[str, str]:
    """从 X/Twitter URL 中提取用户名和推文 ID。

    Param:
        url: X/Twitter 推文链接
    Return:
        (username, tweet_id) 元组
    Raises:
        ValueError: URL 格式无法匹配推文链接模式
    """
    match = re.search(r'(?:x\.com|twitter\.com)/(\w+)/status/(\d+)', url)
    if match:
        return match.group(1), match.group(2)
    raise ValueError(f"Cannot parse tweet URL: {url}")


class UnsafeUrlError(ValueError):
    """URL 指向私网/环回/元数据地址等不安全目标时抛出。"""


def assert_url_safe(url: str) -> None:
    """校验 URL 安全性：仅允许 http/https 且目标主机不解析到私网/环回/元数据地址（SSRF 防护）。

    Param:
        url: 待校验的 URL
    Return:
        无返回；不安全时抛出 UnsafeUrlError
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError(f"仅支持 http/https，拒绝 scheme={parsed.scheme!r}")

    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL 缺少主机名")

    # 解析主机名到所有 IP，逐一校验，避免 DNS 指向内网或云元数据地址
    try:
        addr_infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise UnsafeUrlError(f"主机名解析失败: {host}")

    for info in addr_infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise UnsafeUrlError(f"拒绝访问内网/保留地址: {host} -> {ip_str}")
