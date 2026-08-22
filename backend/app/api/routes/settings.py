"""用户与全局配置 HTTP API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth.dependencies import require_active_user
from app.api.errors import ApiError
from app.configuration import PROVIDER_DEFAULTS, SECRET_KEYS
from app.configuration.crypto import ConfigEncryptionError
from app.configuration.effective import mask_secret
from app.domain.identity import AuthenticatedUser
from app.domain.llm import LLMConfigurationError
from app.modules.settings.public import (
    CONFIG_VALUE_FIELDS,
    ConfigResponse,
    ConfigUpdateRequest,
    GlobalSettingsPermissionError,
    UnknownChatCapabilityError,
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
    except ConfigEncryptionError as error:
        raise _encryption_unavailable(error) from error
    return _to_response(result.settings, is_admin=bool(user["is_admin"]))
