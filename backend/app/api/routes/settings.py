"""用户与全局配置 HTTP API。"""

from __future__ import annotations

import asyncio
import ipaddress
import time

import requests
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.auth.dependencies import require_active_user, require_admin
from app.api.errors import ApiError
from app.configuration import PROVIDER_DEFAULTS, SECRET_KEYS, get_settings
from app.configuration.crypto import ConfigEncryptionError
from app.configuration.effective import mask_secret
from app.domain.identity import AuthenticatedUser
from app.domain.llm import LLMConfigurationError
from app.infrastructure.http.proxy import ProxyConfigError, resolve_proxy_request
from app.infrastructure.providers.eastmoney.base import PROXY_SCOPE
from app.modules.settings.public import (
    CONFIG_VALUE_FIELDS,
    ConfigResponse,
    ConfigUpdateRequest,
    GlobalSettingsPermissionError,
    LlmModelsRequest,
    LlmModelsResponse,
    LlmModelsUnavailableError,
    UnknownChatCapabilityError,
    fetch_llm_models,
    load_user_settings,
    save_user_settings,
)

router = APIRouter()


def _to_response(settings, is_admin: bool = False) -> ConfigResponse:
    """Convert effective settings to a masked API response."""
    values = settings.model_dump(include=CONFIG_VALUE_FIELDS)
    for key in SECRET_KEYS & CONFIG_VALUE_FIELDS:
        values[key] = mask_secret(values[key])
    return ConfigResponse(
        **values,
        provider_defaults=PROVIDER_DEFAULTS,
        is_admin=is_admin,
    )


def _encryption_unavailable(error: ConfigEncryptionError) -> ApiError:
    return ApiError(
        status_code=503,
        code="config.encryption_unavailable",
        message=str(error),
    )


@router.get("", response_model=ConfigResponse)
async def get_config(user: AuthenticatedUser = Depends(require_active_user)) -> ConfigResponse:
    """Read the current user's effective configuration."""
    try:
        settings = await load_user_settings(user["id"])
    except ConfigEncryptionError as error:
        raise _encryption_unavailable(error) from error
    return _to_response(settings, is_admin=bool(user["is_admin"]))


@router.put("", response_model=ConfigResponse)
async def put_config(
    request: ConfigUpdateRequest,
    user: AuthenticatedUser = Depends(require_active_user),
) -> ConfigResponse:
    """Update per-user settings and administrator-only global settings."""
    try:
        result = await save_user_settings(
            user["id"],
            is_admin=bool(user["is_admin"]),
            patch=request.model_dump(exclude_none=True),
        )
    except GlobalSettingsPermissionError as error:
        raise ApiError(
            status_code=403,
            code="config.admin_required",
            message="仅管理员可修改全局配置项: " + ", ".join(error.fields),
        ) from error
    except UnknownChatCapabilityError as error:
        raise ApiError(
            status_code=422,
            code="config.unknown_capability",
            message="未知的 Skill 或 Agent: " + ", ".join(error.names),
        ) from error
    except LLMConfigurationError as error:
        raise ApiError(
            status_code=422,
            code="config.llm_credentials_missing",
            message=str(error),
        ) from error
    except ProxyConfigError as error:
        raise ApiError(
            status_code=422,
            code="config.proxy_invalid",
            message=str(error),
        ) from error
    except ConfigEncryptionError as error:
        raise _encryption_unavailable(error) from error
    return _to_response(result.settings, is_admin=bool(user["is_admin"]))


class ProxyTestRequest(BaseModel):
    """出站代理连通性探测请求（不落库，仅测试当前生效配置）。"""

    target_url: str = Field(
        default="http://push2his.eastmoney.com/api/qt/stock/kline/get",
        max_length=2048,
    )


class ProxyTestResponse(BaseModel):
    ok: bool
    target_url: str
    proxy_enabled: bool
    proxy_type: str
    exit_ip: str | None = None
    latency_ms: int
    message: str


async def _probe_exit_ip(proxy: dict[str, str] | None, timeout: float) -> str | None:
    """经同一代理查询出口 IP，便于管理员确认代理真正生效。"""
    probe_timeout = min(float(timeout), 10.0)
    try:
        response = await asyncio.to_thread(
            requests.get,
            "https://api.ipify.org",
            proxies=proxy,
            timeout=probe_timeout,
        )
        if response.status_code != 200:
            return None
        candidate: str = response.text.strip()
    except requests.RequestException:
        return None
    # 只接受合法 IP，避免把代理返回的错误页当成出口地址
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return None
    return candidate


@router.post("/proxy/test", response_model=ProxyTestResponse)
async def test_outbound_proxy(
    request: ProxyTestRequest,
    admin: AuthenticatedUser = Depends(require_admin),
) -> ProxyTestResponse:
    """探测出站代理连通性：报告出口 IP、耗时与失败原因，不修改任何配置。"""
    settings = get_settings()
    try:
        options = resolve_proxy_request(request.target_url, settings, PROXY_SCOPE)
    except ProxyConfigError as error:
        # 配置本身非法（例如协议与类型不匹配），属于 422 而非连通性问题
        raise ApiError(status_code=422, code="config.proxy_invalid", message=str(error)) from error
    timeout = options.timeout or 15.0
    started = time.monotonic()

    if not options.active:
        return ProxyTestResponse(
            ok=True,
            target_url=request.target_url,
            proxy_enabled=False,
            proxy_type=settings.outbound_proxy_type,
            latency_ms=int((time.monotonic() - started) * 1000),
            message="出站代理未启用（直连）",
        )

    def _fetch() -> tuple[int, str]:
        response = requests.get(
            request.target_url,
            proxies=options.proxies,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        return response.status_code, response.text[:200]

    try:
        status_code, body = await asyncio.to_thread(_fetch)
    except ProxyConfigError as error:
        raise ApiError(status_code=422, code="config.proxy_invalid", message=str(error)) from error
    except requests.RequestException as error:
        return ProxyTestResponse(
            ok=False,
            target_url=request.target_url,
            proxy_enabled=True,
            proxy_type=settings.outbound_proxy_type,
            latency_ms=int((time.monotonic() - started) * 1000),
            message=f"代理请求失败: {type(error).__name__}: {error}"[:300],
        )

    latency_ms = int((time.monotonic() - started) * 1000)
    exit_ip = await _probe_exit_ip(options.proxies, timeout)
    # 上游可能返回 403/JSON 错误体，但只要代理链路打通且拿到响应体即视为连通
    ok = status_code < 500
    detail = f"HTTP {status_code}"
    if exit_ip:
        detail += f"，出口 IP {exit_ip}"
    if not ok:
        detail += f"，响应片段: {body[:80]}"
    return ProxyTestResponse(
        ok=ok,
        target_url=request.target_url,
        proxy_enabled=True,
        proxy_type=settings.outbound_proxy_type,
        exit_ip=exit_ip,
        latency_ms=latency_ms,
        message=detail,
    )


@router.post("/llm/models", response_model=LlmModelsResponse)
async def list_llm_models(
    request: LlmModelsRequest,
    user: AuthenticatedUser = Depends(require_active_user),
) -> LlmModelsResponse:
    """按 Base URL + API Key 拉取该端点支持的模型列表。"""
    try:
        models = await fetch_llm_models(user["id"], request)
    except LlmModelsUnavailableError as error:
        raise ApiError(
            status_code=502,
            code="llm.models_unavailable",
            message=str(error),
        ) from error
    return LlmModelsResponse(models=models)
