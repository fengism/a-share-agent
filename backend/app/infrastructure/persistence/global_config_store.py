import json
import logging

from app.configuration import PERSISTED_GLOBAL_KEYS
from app.configuration import crypto as config_crypto
from app.configuration.crypto_contracts import GLOBAL_CONFIG_SCOPE_ID
from app.infrastructure.persistence.connection import get_connection, unit_of_work

logger = logging.getLogger(__name__)
_LEGACY_REPAIR_TIMEOUT_KEY = "industry_chain_repair_timeout_seconds"
_REPAIR_TIMEOUT_KEYS = (
    "industry_chain_repair_research_timeout_seconds",
    "industry_chain_repair_synthesis_timeout_seconds",
)

def _connection():
    return get_connection("user")


def _serialize_value(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _deserialize_value(value: str):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def get_global_config() -> dict:
    from app.configuration import SECRET_KEYS

    rows = _connection().execute("SELECT key, value FROM global_config").fetchall()
    result = {}
    secrets_to_encrypt = {}
    for row in rows:
        key = row["key"]
        value = row["value"]
        if key not in PERSISTED_GLOBAL_KEYS:
            continue
        if key not in SECRET_KEYS or not value:
            result[key] = _deserialize_value(value)
            continue
        if config_crypto.is_encrypted(value):
            decrypted = config_crypto.decrypt_config_value_with_metadata(
                GLOBAL_CONFIG_SCOPE_ID,
                key,
                value,
            )
            result[key] = decrypted.value
            if decrypted.needs_rotation:
                secrets_to_encrypt[key] = decrypted.value
            continue
        result[key] = value
        secrets_to_encrypt[key] = value

    legacy_timeout = next((row["value"] for row in rows if row["key"] == _LEGACY_REPAIR_TIMEOUT_KEY), None)
    if legacy_timeout is not None:
        legacy_value = _deserialize_value(legacy_timeout)
        for key in _REPAIR_TIMEOUT_KEYS:
            result.setdefault(key, legacy_value)

    if secrets_to_encrypt:
        if config_crypto.encryption_available():
            with unit_of_work("user", immediate=True) as work:
                work.connection.executemany(
                    "UPDATE global_config SET value = ?, updated_at = datetime('now','localtime') WHERE key = ?",
                    [
                        (
                            config_crypto.encrypt_config_value(
                                GLOBAL_CONFIG_SCOPE_ID,
                                key,
                                value,
                            ),
                            key,
                        )
                        for key, value in secrets_to_encrypt.items()
                    ],
                )
            logger.info("已迁移或轮换全局敏感配置 keys=%s", sorted(secrets_to_encrypt))
        else:
            logger.warning(
                "检测到未加密的全局敏感配置 keys=%s，请配置 CONFIG_ENCRYPTION_KEY",
                sorted(secrets_to_encrypt),
            )
    return result


def set_global_config(items: dict) -> None:
    from app.configuration import SECRET_KEYS

    persisted_items = {key: value for key, value in items.items() if key in PERSISTED_GLOBAL_KEYS}
    if not persisted_items:
        return

    values = []
    for key, value in persisted_items.items():
        serialized = "" if value is None else _serialize_value(value)
        if key in SECRET_KEYS:
            secret_value = "" if value is None else str(value)
            serialized = (
                config_crypto.encrypt_config_value(
                    GLOBAL_CONFIG_SCOPE_ID,
                    key,
                    secret_value,
                )
                if secret_value
                else ""
            )
        values.append((key, serialized))

    with unit_of_work("user", immediate=True) as work:
        work.connection.executemany(
            "INSERT INTO global_config(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now','localtime')",
            values,
        )
    if SECRET_KEYS.intersection(persisted_items):
        from app.infrastructure.persistence.user_config_store import (
            invalidate_config_encryption_status_cache,
        )

        invalidate_config_encryption_status_cache()
