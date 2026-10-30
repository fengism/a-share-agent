"""组合多币种折算。

组合以人民币为基准币种。港股行情和成交价仍是港币，汇总市值、成本、
盈亏和现金前需要按汇率折算成人民币，避免把港币金额直接当人民币相加。
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Iterable

from app.core.concurrency.rate_limiter import call_blocking, sina_semaphore
from app.infrastructure.http.client import get_provider_session
from app.modules.portfolio.schemas import is_hk_stock_code

logger = logging.getLogger(__name__)

_HKD_CNY_URL = "https://hq.sinajs.cn/list=fx_shkdcny"
_REQUEST_TIMEOUT_SECONDS = 8
_CACHE_TTL_SECONDS = 3600
_cache_lock = threading.Lock()
_cached_rate: float | None = None
_cached_at: float = 0.0


def _parse_sina_fx_rate(text: str) -> float | None:
    """从新浪外汇接口返回值中解析港币兑人民币中间价附近的报价。"""

    match = re.search(r'="([^"]*)"', text)
    if match is None:
        return None
    fields = match.group(1).split(",")
    # 字段 1/2 分别是买价和卖价，优先取买价；异常时再尝试卖价和昨收。
    for raw in fields[1:4]:
        try:
            rate = float(raw)
        except (TypeError, ValueError):
            continue
        if 0.1 <= rate <= 10:
            return rate
    return None


def _fetch_hkd_cny_rate_sync() -> float | None:
    try:
        response = get_provider_session().get(
            _HKD_CNY_URL,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/114.0.0.0 Safari/537.36"
                ),
                "Accept": "*/*",
                "Referer": "https://finance.sina.com.cn",
            },
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except Exception as error:  # noqa: BLE001 - 汇率失败不应阻断组合查询
        logger.warning("获取港币兑人民币汇率失败: %s", error)
        return None

    rate = _parse_sina_fx_rate(response.text)
    if rate is None:
        logger.warning("港币兑人民币汇率响应无法解析: %s", response.text[:120])
    return rate


def _cached_hkd_cny_rate() -> float | None:
    global _cached_rate, _cached_at

    now = time.monotonic()
    with _cache_lock:
        if _cached_rate is not None and now - _cached_at < _CACHE_TTL_SECONDS:
            return _cached_rate

    rate = _fetch_hkd_cny_rate_sync()
    if rate is None:
        return None

    with _cache_lock:
        _cached_rate = rate
        _cached_at = now
    return rate


async def fetch_fx_rates(stock_codes: Iterable[str]) -> dict[str, float]:
    """返回组合基准币种和持仓涉及的汇率。

    当前仅需要港币兑人民币；纯 A 股组合不会发起外部汇率请求。
    汇率获取失败时只返回基准币种，调用方按 1:1 兜底并给出提示。
    """

    codes = [str(code) for code in stock_codes if str(code).strip()]
    rates: dict[str, float] = {"CNY": 1.0}
    if not any(is_hk_stock_code(code) for code in codes):
        return rates

    rate = await call_blocking(_cached_hkd_cny_rate, semaphore=sina_semaphore)
    if rate is not None and rate > 0:
        rates["HKD"] = rate
    return rates


def reset_fx_cache() -> None:
    """清空汇率缓存，供测试或运行期刷新配置使用。"""

    global _cached_rate, _cached_at
    with _cache_lock:
        _cached_rate = None
        _cached_at = 0.0


__all__ = ["fetch_fx_rates", "reset_fx_cache"]
