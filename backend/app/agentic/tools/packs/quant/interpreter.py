"""Remote-only Python execution. No local subprocess or AST-based security boundary."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import uuid
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.configuration import get_settings

logger = logging.getLogger(__name__)
_TIMEOUT_SECONDS = 20.0
_MAX_CODE_BYTES = 32_768
_MAX_RESPONSE_BYTES = 1_048_576


def _unavailable() -> dict[str, Any]:
    return {
        "ok": False,
        "output": "",
        "error_code": "sandbox_unavailable",
        "error": "隔离 Python 服务未配置、不可用或响应无效；未在后端本机执行。常用计算请使用 financial_calculator。",
    }


async def _cancel_job(client: httpx.AsyncClient, path: str) -> None:
    try:
        async with asyncio.timeout(3):
            response = await client.delete(path, timeout=3)
            response.raise_for_status()
    except (httpx.HTTPError, TimeoutError, ValueError):
        # Runner also enforces an independent wall deadline and reaps expired containers.
        logger.warning("Python 沙盒取消请求失败，等待执行服务的独立超时清理")


async def execute_python_code(code: str, timeout: float = _TIMEOUT_SECONDS) -> dict[str, Any]:
    try:
        valid_code = (
            isinstance(code, str)
            and bool(code.strip())
            and "\x00" not in code
            and len(code.encode("utf-8")) <= _MAX_CODE_BYTES
        )
    except UnicodeEncodeError:
        valid_code = False
    if not valid_code:
        return {
            "ok": False,
            "output": "",
            "error_code": "invalid_arguments",
            "error": "代码必须为有效 UTF-8、非空、不含空字节且不超过 32768 字节",
        }
    if not math.isfinite(timeout) or timeout <= 0:
        return _unavailable()
    settings = get_settings()  # Global deployment configuration, never user-overridable settings.
    url, token = settings.python_sandbox_url.rstrip("/"), settings.python_sandbox_token
    try:
        parsed = urlsplit(url)
        _ = parsed.port  # Reject malformed ports before creating an HTTP client.
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or len(token) < 32
            or not token.isascii()
            or not token.isprintable()
        ):
            return _unavailable()
    except ValueError:
        return _unavailable()
    path = f"/jobs/{uuid.uuid4().hex}"
    async with httpx.AsyncClient(
        base_url=url,
        headers={"Authorization": f"Bearer {token}"},
        trust_env=False,
        follow_redirects=False,
        timeout=min(timeout, _TIMEOUT_SECONDS),
    ) as client:
        try:
            async with asyncio.timeout(min(timeout, _TIMEOUT_SECONDS)):
                async with client.stream("POST", path, json={"code": code}) as response:
                    if response.status_code != 200:
                        raise ValueError("runner unavailable")
                    payload = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(payload) + len(chunk) > _MAX_RESPONSE_BYTES:
                            raise ValueError("oversized response")
                        payload.extend(chunk)
                result = json.loads(payload)
                if (
                    not isinstance(result, dict)
                    or type(result.get("ok")) is not bool
                    or not isinstance(result.get("output"), str)
                    or not isinstance(result.get("error"), str)
                ):
                    raise ValueError("invalid response")
                return {key: result[key] for key in ("ok", "output", "error")}
        except asyncio.CancelledError:
            cleanup = asyncio.create_task(_cancel_job(client, path))
            await asyncio.shield(cleanup)
            raise
        except (httpx.HTTPError, TimeoutError, ValueError):
            await _cancel_job(client, path)
            return _unavailable()
