"""上海黄金交易所公开历史行情适配器。"""

from collections.abc import Mapping
from typing import Any

from curl_cffi import requests as curl_requests

_SGE_URL = "https://www.sge.com.cn/graph/Dailyhq"


class SgeHttpProvider:
    """访问上金所公开历史行情接口。"""

    def fetch(self, symbol: str) -> Mapping[str, Any]:
        headers = {
            "Accept": "text/html, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://www.sge.com.cn",
            "Referer": "https://www.sge.com.cn/sjzx/mrhq",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
        }
        response = curl_requests.post(
            _SGE_URL,
            data={"instid": symbol},
            headers=headers,
            timeout=15,
            impersonate="chrome",
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise ValueError("上金所返回格式无效")
        return payload


sge_provider = SgeHttpProvider()
