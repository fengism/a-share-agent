"""URL 辅助：只放行可安全外链的 http(s) 地址。

报表渲染会把外部数据源给出的链接直接嵌进 HTML ``href`` / Markdown 链接，
必须过滤 ``javascript:``、``data:`` 等协议与畸形 URL，避免注入可执行链接。
本函数只做协议与主机白名单判断，不做 DNS 解析或 SSRF 校验（后者见
``app.agentic.tools.packs.web.url_security``）。
"""

from __future__ import annotations

from urllib.parse import urlsplit

__all__ = ["safe_http_url"]


def safe_http_url(value: object) -> str:
    """返回可安全嵌入链接的 http(s) 地址，否则返回空串。

    Param:
        value: 任意待校验值（``None`` / 非字符串 / 相对路径均返回空串）
    Return:
        规范化后仍为 http(s) 且带主机的原始地址，或空串
    """
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = urlsplit(text)
    except ValueError:
        return ""
    return text if parsed.scheme in {"http", "https"} and parsed.netloc else ""
