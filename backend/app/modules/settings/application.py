"""用户配置异步应用用例。"""

from app.configuration.schema import Settings
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.infrastructure.persistence import admin_audit_store
from app.modules.settings.effects import apply_update_side_effects
from app.modules.settings.service import (
    SettingsUpdateResult,
    get_inherited_private_keys,
    get_user_settings,
    update_user_settings,
)


async def load_user_settings(user_id: int) -> Settings:
    return await call_blocking(
        get_user_settings,
        user_id,
        semaphore=database_semaphore,
    )


async def load_inherited_private_keys(user_id: int) -> list[str]:
    """用户仍沿用全局基线的私密字段（用于前端标记「使用管理员配置」）。"""
    return await call_blocking(
        get_inherited_private_keys,
        user_id,
        semaphore=database_semaphore,
    )


async def save_user_settings(
    user_id: int,
    *,
    is_admin: bool,
    patch: dict,
) -> SettingsUpdateResult:
    result = await call_blocking(
        update_user_settings,
        user_id,
        is_admin,
        patch,
        semaphore=database_semaphore,
    )
    if result.global_settings is not None:
        # 全局配置（LLM Key、代理、限速阈值…）是多用户共享的敏感面：只记录"改了哪些字段"，
        # 绝不落取值，避免审计表本身成为密钥泄漏源。
        apply_update_side_effects(result.global_settings, result.global_patch)
        admin_audit_store.record_admin_action(
            action="config.update_global",
            target_type="config",
            target_id="global",
            details={"fields": sorted(result.global_patch)},
        )
    return result
