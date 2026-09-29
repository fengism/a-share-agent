"""版本检查与在线更新 API 端点。

展示版本在镜像构建时通过 APP_VERSION 注入，更新判断遵循语义版本；发布标记同时携带
正式版本和不可变 commit SHA。更新执行由 compose 内的 updater 服务完成。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

import httpx
from fastapi import Depends, FastAPI
from packaging.version import InvalidVersion, Version

from app.api.auth.dependencies import require_admin
from app.api.schemas import UpdateStatusResponse, VersionCheckResponse

logger = logging.getLogger(__name__)

HUB_TAGS_URL = "https://hub.docker.com/v2/repositories/{namespace}/{repo}/tags/"
_SEMVER = r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
_RELEASE_MARKER = re.compile(
    rf"release-(?P<version>v?{_SEMVER})-sha-(?P<revision>[0-9a-f]{{7,40}})",
    re.IGNORECASE,
)

_OK_TTL_SECONDS = 300.0
_FAIL_TTL_SECONDS = 30.0
_hub_lock = asyncio.Lock()


@dataclass(frozen=True, slots=True)
class ReleaseMarker:
    version: str
    revision: str
    published_at: datetime


class _VersionCache(TypedDict):
    at: float
    latest: ReleaseMarker | None
    ok: bool


_cache: _VersionCache = {"at": 0.0, "latest": None, "ok": False}
_http_client: httpx.AsyncClient | None = None


def current_version() -> str:
    """当前运行版本。

    与 OpenAPI 元数据共用 app.runtime.app_version 的解析逻辑：注入的
    APP_VERSION 原样返回（tag 形态），未注入时回退读 pyproject，使源码部署
    不再被误判成 dev 而禁用在线更新。
    """
    from app.runtime.app_version import resolve_app_version

    return resolve_app_version()


def _parse_semantic_version(value: str) -> Version | None:
    candidate = value.strip()
    if re.fullmatch(rf"v?{_SEMVER}", candidate, re.IGNORECASE) is None:
        return None
    try:
        return Version(candidate.removeprefix("v").removeprefix("V"))
    except InvalidVersion:
        return None


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _pick_latest_release_marker(tags: list[dict[str, Any]]) -> ReleaseMarker | None:
    """按语义版本选择最新发布；同版本重复发布时取最后完成的标记。"""
    candidates: list[tuple[Version, ReleaseMarker]] = []
    for tag in tags:
        matched = _RELEASE_MARKER.fullmatch(str(tag.get("name") or ""))
        published_at = _parse_timestamp(tag.get("last_updated"))
        if matched is None or published_at is None:
            continue
        parsed_version = _parse_semantic_version(matched.group("version"))
        if parsed_version is None:
            continue
        marker = ReleaseMarker(
            version=f"v{matched.group('version').lstrip('vV')}",
            revision=matched.group("revision").lower(),
            published_at=published_at,
        )
        candidates.append((parsed_version, marker))
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: (candidate[0], candidate[1].published_at))[1]


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=10.0)
    return _http_client


async def fetch_latest_version() -> ReleaseMarker | None:
    """查询 Docker Hub 上语义版本最高且已完整发布的版本标记。

    成功结果缓存 300 秒；失败结果只缓存 30 秒，避免瞬时故障掩盖真实更新。
    single-flight 锁保证缓存过期时的并发请求只触发一次 Hub 调用。
    """
    if _cache["at"] + (_OK_TTL_SECONDS if _cache["ok"] else _FAIL_TTL_SECONDS) > time.monotonic():
        return _cache["latest"]

    async with _hub_lock:
        # 持锁期间可能已被前一个请求刷新
        if _cache["at"] + (_OK_TTL_SECONDS if _cache["ok"] else _FAIL_TTL_SECONDS) > time.monotonic():
            return _cache["latest"]

        from app.configuration.runtime import get_settings

        settings = get_settings()
        latest: ReleaseMarker | None = None
        ok = False
        try:
            response = await _get_http_client().get(
                HUB_TAGS_URL.format(
                    namespace=settings.update_hub_namespace,
                    repo=settings.update_hub_repo,
                ),
                params={"page_size": 100, "name": "release-v"},
            )
            response.raise_for_status()
            latest = _pick_latest_release_marker(response.json().get("results") or [])
            ok = True
        except Exception:
            logger.warning("查询 Docker Hub 最新版本失败", exc_info=True)
        _cache["at"] = time.monotonic()
        _cache["latest"] = latest
        _cache["ok"] = ok
        return latest


def _is_newer_release(current: str, latest: str) -> bool:
    current_semver = _parse_semantic_version(current)
    latest_semver = _parse_semantic_version(latest)
    return bool(current_semver is not None and latest_semver is not None and latest_semver > current_semver)


async def version_check() -> VersionCheckResponse:
    from app.api.errors import ApiError

    current = current_version()
    latest = await fetch_latest_version()
    if latest is None:
        raise ApiError(
            status_code=503,
            code="system.version_check_unavailable",
            message="暂时无法获取最新版本，请稍后重试",
        )
    update_available = _is_newer_release(current, latest.version)
    return VersionCheckResponse(
        current_version=current,
        latest_version=latest.version,
        update_available=update_available,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json_atomically(path: Path, payload: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


async def update_status() -> UpdateStatusResponse:
    """Return the latest updater state from the shared data directory."""
    from app.configuration.runtime import get_settings

    status_file = get_settings().app_data_dir / "update-status.json"
    if not status_file.exists():
        return UpdateStatusResponse(status="idle")
    try:
        return UpdateStatusResponse.model_validate_json(status_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("读取更新状态失败", exc_info=True)
        return UpdateStatusResponse(status="failed", message="更新状态文件损坏")


async def trigger_update() -> UpdateStatusResponse:
    """Atomically enqueue an update request for the updater container."""
    from app.api.errors import ApiError
    from app.configuration.runtime import get_settings

    data_dir = get_settings().app_data_dir
    marker = data_dir / "update-request.json"
    status_file = data_dir / "update-status.json"
    requested_at = _utc_now()

    # Treat repeated clicks as idempotent while the updater owns or awaits a request.
    processing = data_dir / "update-request.running.json"
    if processing.exists():
        return UpdateStatusResponse(
            status="running",
            message="更新正在执行",
            updated_at=requested_at,
        )
    if marker.exists():
        return UpdateStatusResponse(
            status="pending",
            message="更新请求已提交",
            updated_at=requested_at,
        )

    latest = await fetch_latest_version()
    if latest is None:
        raise ApiError(
            status_code=503,
            code="system.update_unavailable",
            message="暂时无法获取可用更新，请稍后重试",
        )
    if not _is_newer_release(current_version(), latest.version):
        raise ApiError(
            status_code=409,
            code="system.update_not_available",
            message="当前没有可安装的新版本",
        )

    try:
        _write_json_atomically(
            status_file,
            {
                "status": "pending",
                "message": "更新请求已提交",
                "updated_at": requested_at,
            },
        )
        _write_json_atomically(
            marker,
            {
                "requested_at": requested_at,
                "target_version": latest.revision,
            },
        )
    except OSError as exc:
        logger.warning("写入更新请求失败: %s", exc)
        try:
            _write_json_atomically(
                status_file,
                {
                    "status": "failed",
                    "message": "无法写入更新请求",
                    "updated_at": _utc_now(),
                },
            )
        except OSError:
            logger.warning("写入更新失败状态失败", exc_info=True)
        raise ApiError(
            status_code=503,
            code="system.update_unavailable",
            message="更新服务不可用，请检查 updater 容器是否运行",
        ) from exc
    return UpdateStatusResponse(
        status="pending",
        message="更新请求已提交",
        updated_at=requested_at,
    )


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
        "/api/system/update/status",
        update_status,
        methods=["GET"],
        response_model=UpdateStatusResponse,
        dependencies=list(active_user_dependencies),
        name="system_update_status",
    )
    application.add_api_route(
        "/api/system/update",
        trigger_update,
        methods=["POST"],
        response_model=UpdateStatusResponse,
        dependencies=[Depends(require_admin)],
        name="system_update",
    )
