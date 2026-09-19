import logging
from dataclasses import dataclass

from app import configuration as config
from app.configuration.effective import is_masked_secret, overlay_private
from app.core.request_context import invalidate_settings_cache
from app.infrastructure.llm.spec import resolve_llm_client_spec
from app.infrastructure.persistence import global_config_store, user_config_store

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SettingsUpdateResult:
    settings: config.Settings
    global_settings: config.Settings | None
    global_patch: dict


class GlobalSettingsPermissionError(Exception):
    def __init__(self, fields: list[str]):
        self.fields = tuple(sorted(fields))
        super().__init__(", ".join(self.fields))


class UnknownChatCapabilityError(Exception):
    def __init__(self, names: list[str]):
        self.names = tuple(sorted(names))
        super().__init__(", ".join(self.names))


def _normalize_chat_capability_preferences(patch: dict) -> dict:
    if not {"disabled_chat_skills", "disabled_chat_agents"} & patch.keys():
        return patch

    from app.agentic.agents.catalog import list_agent_profiles
    from app.agentic.bootstrap import register_all_capabilities
    from app.agentic.catalog import registry

    register_all_capabilities()
    known_names = {
        "disabled_chat_skills": [skill.name for skill in registry.list_skills()],
        "disabled_chat_agents": [profile.name for profile in list_agent_profiles()],
    }
    normalized = dict(patch)
    unknown: list[str] = []
    for field, catalog_names in known_names.items():
        if field not in patch:
            continue
        requested = set(patch[field])
        unknown.extend(sorted(requested - set(catalog_names)))
        normalized[field] = [name for name in catalog_names if name in requested]
    if unknown:
        raise UnknownChatCapabilityError(unknown)
    return normalized


def get_user_settings(user_id: int) -> config.Settings:
    return config.effective_settings_for_user(
        user_id,
        user_settings_loader=user_config_store.get_user_config,
    )


def update_user_settings(
    user_id: int,
    is_admin: bool,
    patch: dict,
) -> SettingsUpdateResult:
    if not patch:
        return SettingsUpdateResult(
            settings=get_user_settings(user_id),
            global_settings=None,
            global_patch={},
        )

    patch = _normalize_chat_capability_preferences(patch)

    private_patch = {key: value for key, value in patch.items() if key in config.PRIVATE_USER_KEYS}
    global_patch = {key: value for key, value in patch.items() if key in config.PERSISTED_GLOBAL_KEYS}
    if global_patch and not is_admin:
        raise GlobalSettingsPermissionError(list(global_patch))

    values_to_store = {key: value for key, value in private_patch.items() if not is_masked_secret(key, value)}
    global_values_to_store = {key: value for key, value in global_patch.items() if not is_masked_secret(key, value)}
    if {
        "llm_provider", "llm_api_mode", "llm_api_version", "llm_api_key",
        "llm_base_url", "llm_model",
    } & private_patch.keys():
        overrides = dict(user_config_store.get_user_config(user_id))
        overrides.update(values_to_store)
        candidate = overlay_private(config.get_settings(), overrides)
        resolve_llm_client_spec(candidate)
    if values_to_store:
        user_config_store.set_user_config(user_id, values_to_store)
        invalidate_settings_cache()

    updated_global_settings = None
    if global_values_to_store:
        global_config_store.set_global_config(global_values_to_store)
        updated_global_settings = config.update_settings(global_values_to_store)

    logger.info(
        "Config update by user=%s private=%s global=%s",
        user_id,
        list(private_patch),
        list(global_values_to_store),
    )
    return SettingsUpdateResult(
        settings=get_user_settings(user_id),
        global_settings=updated_global_settings,
        global_patch=global_values_to_store,
    )
