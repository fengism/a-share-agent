"""版本检查与在线更新 API 端点。

版本号在镜像构建时通过 APP_VERSION 注入（git commit sha）；本地开发为 "dev"。
更新执行由 compose 内的 Watchtower updater 服务完成，见 docker-compose.yml。
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx
from fastapi import Depends, FastAPI

from app.api.schemas import VersionCheckResponse
from app.api.auth.dependencies import require_admin

logger = logging.getLogger(__name__)

HUB_TAGS_URL = "https://hub.docker.com/v2/repositories/{namespace}/{repo}/tags/"
HUB_NAMESPACE = os.environ.get("UPDATE_HUB_NAMESPACE", "fengliu1989")
HUB_REPO = os.environ.get("UPDATE_HUB_REPO", "a-share-backend")
UPDATER_URL = os.environ.get("UPDATER_HTTP_URL", "http://updater:8080/v1/update")

_CACHE_TTL_SECONDS = 300.0
_cache: dict[str, Any] = {"at": 0.0, "latest": None}


def current_version() -> str:
    return os.environ.get("APP_VERSION") or "dev"


def _short(sha: str) -> str:
    return sha[:7]


def _pick_latest_sha_tag(tags: list[dict[str, Any]]) -> str | None:
    """取最新的 sha-<short> tag（Hub 返回已按时间倒序）。"""
    for tag in tags:
        name = str(tag.get("name") or "")
        if name.startswith("sha-"):
            return name.removeprefix("sha-")
    return None


async def fetch_latest_version() -> str | None:
    """查询 Docker Hub 上最新的 sha- 版本；失败返回 None 并记录日志。"""
    now = time.monotonic()
    if now - float(_cache["at"]) < _CACHE_TTL_SECONDS:
        return _cache["latest"]
    latest: str | None = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                HUB_TAGS_URL.format(namespace=HUB_NAMESPACE, repo=HUB_REPO),
                params={"page_size": 25},
            )
            response.raise_for_status()
            latest = _pick_latest_sha_tag(response.json().get("results") or [])
    except Exception:
        logger.warning("查询 Docker Hub 最新版本失败", exc_info=True)
    _cache["at"] = now
    _cache["latest"] = latest
    return latest


async def version_check() -> VersionCheckResponse:
    current = current_version()
    latest = await fetch_latest_version()
    update_available = bool(
        latest
        and current != "dev"
        and not latest.startswith(_short(current))
    )
    return VersionCheckResponse(
        current_version=current,
        latest_version=latest,
        update_available=update_available,
    )


async def trigger_update() -> dict[str, str]:
    import httpx as _httpx

    from app.configuration.runtime import get_settings

    token = get_settings().updater_http_token
    try:
        async with _httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                UPDATER_URL,
                headers={"Authorization": f"Bearer {token}"} if token else {},
            )
            response.raise_for_status()
    except Exception as exc:
        logger.warning("触发在线更新失败: %s", exc)
        from app.api.errors import ApiError

        raise ApiError(
            status_code=503,
            code="system.update_unavailable",
            message="更新服务不可用，请检查 updater 容器是否运行",
        ) from exc
    return {"status": "update_started"}


def register_version_endpoints(
    application: FastAPI,
    *,
    active_user_dependencies: list[Any],
) -> None:
    application.add_api_route(
        "/api/system/version",
        version_check,
        methods=["GET"],
        response_model=VersionCheckResponse,
        dependencies=list(active_user_dependencies),
        name="system_version",
    )
    application.add_api_route(
        "/api/system/update",
        trigger_update,
        methods=["POST"],
        dependencies=[Depends(require_admin)],
        name="system_update",
    )
