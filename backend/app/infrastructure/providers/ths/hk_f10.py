"""同花顺港股 F10 页面抓取与解码的共享实现。

港股 F10 与 A 股 F10 有两处必须分市场处理的差异，都曾导致静默错误，因此集中到
本模块，避免各能力各写一份：

1. 路径代码：A 股是 6 位代码；港股是 ``HK`` + 去掉前导零后补齐 4 位。5 位补零
   （``HK00700``）只会拿到一个 2417 字节的空壳页，不报错、只是没有内容。
2. 页面编码：A 股是 gb2312 系，港股是 utf-8。用错编码时 BeautifulSoup 仍能
   解析出标签结构，于是不会报错，只会静默产出整片乱码文本。
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from app.core.market import is_hk_code
from app.infrastructure.providers.ths.transport import ThsTransport

_A_SHARE_ENCODING = "gb2312"
_HK_ENCODING = "utf-8"

_F10_BASE_URL = "https://basic.10jqka.com.cn/new"
_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def ths_f10_code_segment(code: str) -> str:
    """返回同花顺 F10 路径中的代码片段。"""
    if not is_hk_code(code):
        return code
    digits = "".join(char for char in code if char.isdigit())
    return f"HK{(digits.lstrip('0') or '0').zfill(4)}"


def fetch_ths_f10_page(transport: ThsTransport, code: str, page: str) -> BeautifulSoup:
    """抓取并按市场正确解码同花顺 F10 页面。

    Param:
        transport: 同花顺 HTTP 传输
        code: A 股 6 位或港股 1-5 位代码
        page: 页面文件名，例如 ``operate.html``
    Return:
        解析后的文档
    """
    is_hk = is_hk_code(code)
    response = transport.request(
        "GET",
        f"{_F10_BASE_URL}/{ths_f10_code_segment(code)}/{page}",
        headers={
            "User-Agent": _USER_AGENT,
            "Referer": "https://basic.10jqka.com.cn/",
        },
        timeout=15,
    )
    response.encoding = _HK_ENCODING if is_hk else _A_SHARE_ENCODING
    return BeautifulSoup(response.text, "html.parser")


__all__ = ["fetch_ths_f10_page", "ths_f10_code_segment"]
