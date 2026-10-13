"""上海黄金交易所公开历史行情适配器。"""

from __future__ import annotations

import threading
import time
from collections.abc import Mapping
from typing import Any

from curl_cffi import requests as curl_requests

from app.core.exceptions import UpstreamRateLimitedError

_SGE_URL = "https://www.sge.com.cn/graph/Dailyhq"

# 上金所 Dailyhq 对请求频率敏感：同一出口连续请求几乎必返 403。
# 5s 是实测可用下限（10s 更稳但首次预热翻倍），留出余量后按 5s 串行放行。
_MIN_INTERVAL_SECONDS = 5.0


class _MinIntervalThrottle:
    """进程内按最小间隔串行放行，避免触发上金所频率风控。"""

    def __init__(self, min_interval_seconds: float) -> None:
        self._min_interval = max(0.0, min_interval_seconds)
        self._lock = threading.Lock()
        self._next_allowed_at = 0.0

    def acquire(self) -> None:
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._next_allowed_at - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._next_allowed_at = now + self._min_interval


_throttle = _MinIntervalThrottle(_MIN_INTERVAL_SECONDS)


class SgeHttpProvider:
    """访问上金所公开历史行情接口。"""

    min_interval_seconds: float = _MIN_INTERVAL_SECONDS

    def fetch(self, symbol: str) -> Mapping[str, Any]:
        _throttle.acquire()
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
        if response.status_code == 403:
            # 上金所以 403 表达频率限制而非合约不存在，按可重试故障上报。
            raise UpstreamRateLimitedError(
                f"上金所请求过于频繁，请稍后重试: {symbol}"
            )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise ValueError("上金所返回格式无效")
        return payload


sge_provider = SgeHttpProvider()