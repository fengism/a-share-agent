"""网络推送韧性 HTTP 客户端。

提供统一的超时控制、网络抖动容错、瞬态状态码识别与带上限的指数退避重试（Exponential Backoff with Jitter），
确保推送通知在偶发网络波动或平台上行限流时具备极高的交付可靠性。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# 可恢复的瞬态 HTTP 状态码（限流或上游服务器偶发错误）
TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


async def resilient_post(
    url: str,
    *,
    json_data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    timeout: float = 10.0,
    max_retries: int = 2,
    base_backoff: float = 0.5,
) -> httpx.Response:
    """发送带有指数退避重试的异步 HTTP POST 请求。

    参数:
        url: 目标 Webhook 接口 URL。
        json_data: 请求体 JSON 数据。
        headers: 自定义 HTTP 请求头。
        params: URL 查询参数。
        timeout: 单次 HTTP 请求超时时间（秒）。
        max_retries: 最大重试次数（默认 2 次，即最多尝试 3 次）。
        base_backoff: 指数退避基数（秒）。
    返回:
        httpx.Response 响应对象。
    异常:
        httpx.HTTPError 或 asyncio.TimeoutError: 达到最大重试次数后仍然失败时抛出。
    """
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    json=json_data,
                    headers=headers,
                    params=params,
                )

                # 遇到限流或服务器瞬态错误且仍有重试机会
                if response.status_code in TRANSIENT_STATUS_CODES and attempt < max_retries:
                    retry_after_hdr = response.headers.get("Retry-After")
                    if retry_after_hdr and retry_after_hdr.isdigit():
                        delay = min(float(retry_after_hdr), 2.0)
                    else:
                        delay = min(base_backoff * (2**attempt), 2.0)

                    logger.warning(
                        "Webhook 响应瞬态状态码 HTTP %d，将在 %.2fs 后进行第 %d 次重试: url=%s",
                        response.status_code,
                        delay,
                        attempt + 1,
                        url[:60],
                    )
                    await asyncio.sleep(delay)
                    continue

                return response

        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = min(base_backoff * (2**attempt), 2.0)
                logger.warning(
                    "Webhook 请求网络异常 (%s: %s)，将在 %.2fs 后进行第 %d 次重试: url=%s",
                    type(exc).__name__,
                    exc,
                    delay,
                    attempt + 1,
                    url[:60],
                )
                await asyncio.sleep(delay)
                continue
            raise

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("resilient_post 发生未知分支错误")
