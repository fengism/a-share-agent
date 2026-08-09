from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.errors import ApiError
from app.configuration import PROVIDER_DEFAULTS, SECRET_KEYS
from app.configuration.crypto import ConfigEncryptionError
from app.configuration.effective import mask_secret
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.modules.auth.public import AuthenticatedUser, require_active_user
from app.modules.settings import service as settings_service
from app.modules.settings.effects import apply_update_side_effects
from app.modules.settings.schemas import CONFIG_VALUE_FIELDS, ConfigResponse, ConfigUpdateRequest

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
        settings = await call_blocking(
            settings_service.get_user_settings,
            user["id"],
            semaphore=database_semaphore,
        )
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
        result = await call_blocking(
            settings_service.update_user_settings,
            user["id"],
            bool(user["is_admin"]),
            request.model_dump(exclude_none=True),
            semaphore=database_semaphore,
        )
    except settings_service.GlobalSettingsPermissionError as error:
        raise ApiError(
            status_code=403,
            code="config.admin_required",
            message="仅管理员可修改全局配置项: " + ", ".join(error.fields),
        ) from error
    except settings_service.UnknownChatCapabilityError as error:
        raise ApiError(
            status_code=422,
            code="config.unknown_capability",
            message="未知的 Skill 或 Agent: " + ", ".join(error.names),
        ) from error
    except ConfigEncryptionError as error:
        raise _encryption_unavailable(error) from error
    if result.global_settings is not None:
        apply_update_side_effects(result.global_settings, result.global_patch)
    return _to_response(result.settings, is_admin=bool(user["is_admin"]))
