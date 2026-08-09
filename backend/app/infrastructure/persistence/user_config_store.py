import json
import logging
import time
from threading import Lock

from app.configuration import crypto as config_crypto
from app.configuration.crypto_contracts import GLOBAL_CONFIG_SCOPE_ID
from app.infrastructure.persistence.connection import database_path, get_connection

logger = logging.getLogger(__name__)

_ENCRYPTION_STATUS_CACHE_SECONDS = 60.0
_encryption_status_cache_lock = Lock()
_encryption_status_cache: tuple[tuple[str, str], float] | None = None


def _serialize_value(value) -> str:
    if isinstance(value, (list, dict, tuple)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _deserialize_value(value: str):
    if not value.lstrip().startswith(("[", "{")):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _connection():
    return get_connection("user")


def invalidate_config_encryption_status_cache() -> None:
    global _encryption_status_cache
    with _encryption_status_cache_lock:
        _encryption_status_cache = None


def _cached_encryption_status(cache_key: tuple[str, str]) -> str | None:
    with _encryption_status_cache_lock:
        cached = _encryption_status_cache
    if cached is None or cached[0] != cache_key or cached[1] <= time.monotonic():
        return None
    return "ready"


def _cache_ready_encryption_status(cache_key: tuple[str, str]) -> None:
    global _encryption_status_cache
    with _encryption_status_cache_lock:
        _encryption_status_cache = (
            cache_key,
            time.monotonic() + _ENCRYPTION_STATUS_CACHE_SECONDS,
        )


def get_user_config(user_id: int) -> dict[str, str]:
    from app.configuration import SECRET_KEYS

    connection = _connection()
    rows = connection.execute(
        "SELECT key, value FROM user_config WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    result: dict[str, str] = {}
    secrets_to_encrypt: dict[str, str] = {}
    for row in rows:
        key = row["key"]
        value = row["value"]
        if key not in SECRET_KEYS or not value:
            result[key] = _deserialize_value(value)
            continue
        if config_crypto.is_encrypted(value):
            decrypted = config_crypto.decrypt_config_value_with_metadata(user_id, key, value)
            result[key] = decrypted.value
            if decrypted.needs_rotation:
                secrets_to_encrypt[key] = decrypted.value
            continue
        result[key] = value
        secrets_to_encrypt[key] = value

    if secrets_to_encrypt:
        if config_crypto.encryption_available():
            connection.executemany(
                "UPDATE user_config SET value = ? WHERE user_id = ? AND key = ?",
                [
                    (config_crypto.encrypt_config_value(user_id, key, value), user_id, key)
                    for key, value in secrets_to_encrypt.items()
                ],
            )
            connection.commit()
            logger.info("已迁移或轮换用户敏感配置 user_id=%s keys=%s", user_id, sorted(secrets_to_encrypt))
        else:
            logger.warning(
                "检测到未加密的用户敏感配置 user_id=%s keys=%s，请配置 CONFIG_ENCRYPTION_KEY",
                user_id,
                sorted(secrets_to_encrypt),
            )
    return result


def config_encryption_status() -> str:
    from app.configuration import SECRET_KEYS
    has_current_key = config_crypto.validate_keyring()
    cache_key = (
        str(database_path("user")),
        config_crypto.keyring_fingerprint(),
    )
    cached_status = _cached_encryption_status(cache_key)
    if cached_status is not None:
        return cached_status
    placeholders = ",".join("?" for _ in SECRET_KEYS)
    user_rows = (
        _connection()
        .execute(
            f"SELECT user_id, key, value FROM user_config WHERE key IN ({placeholders}) AND value <> ''",
            tuple(SECRET_KEYS),
        )
        .fetchall()
    )
    global_rows = (
        _connection()
        .execute(
            f"SELECT key, value FROM global_config WHERE key IN ({placeholders}) AND value <> ''",
            tuple(SECRET_KEYS),
        )
        .fetchall()
    )
    rows = [(row["user_id"], row["key"], row["value"]) for row in user_rows] + [
        (GLOBAL_CONFIG_SCOPE_ID, row["key"], row["value"]) for row in global_rows
    ]
    if not rows:
        return "ready" if has_current_key else "not_configured"
    if not has_current_key:
        raise config_crypto.ConfigEncryptionError("数据库存在敏感配置，但 CONFIG_ENCRYPTION_KEY 未配置")
    for scope_id, key, value in rows:
        if config_crypto.is_encrypted(value):
            config_crypto.decrypt_config_value_with_metadata(scope_id, key, value)
    _cache_ready_encryption_status(cache_key)
    return "ready"


def set_user_config(user_id: int, items: dict) -> None:
    if not items:
        return
    from app.configuration import SECRET_KEYS

    values = []
    for key, value in items.items():
        serialized = "" if value is None else _serialize_value(value)
        if key in SECRET_KEYS and serialized:
            serialized = config_crypto.encrypt_config_value(user_id, key, str(value))
        values.append((user_id, key, serialized))

    connection = _connection()
    connection.executemany(
        "INSERT INTO user_config (user_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
        values,
    )
    connection.commit()
    if SECRET_KEYS.intersection(items):
        invalidate_config_encryption_status_cache()
