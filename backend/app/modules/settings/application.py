"""用户配置异步应用用例。"""

from app.configuration.schema import Settings
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.modules.settings.effects import apply_update_side_effects
from app.modules.settings.service import SettingsUpdateResult, get_user_settings, update_user_settings


async def load_user_settings(user_id: int) -> Settings:
    return await call_blocking(
        get_user_settings,
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
        apply_update_side_effects(result.global_settings, result.global_patch)
    return result
