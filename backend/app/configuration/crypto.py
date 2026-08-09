import base64
import binascii
import hashlib
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.configuration.crypto_contracts import ConfigEncryptionError

ENCRYPTED_PREFIX = "enc:v1:"
_NONCE_SIZE = 12
_KEY_SIZE = 32


@dataclass(frozen=True)
class DecryptedConfigValue:
    value: str
    needs_rotation: bool


def _get_encryption_key() -> str:
    from app.configuration import get_settings

    return get_settings().config_encryption_key


def _get_previous_encryption_keys() -> list[str]:
    from app.configuration import get_settings

    raw_keys = get_settings().config_encryption_previous_keys
    return [item.strip() for item in raw_keys.split(",") if item.strip()]


def _decode_key(encoded_key: str) -> bytes:
    if not encoded_key:
        raise ConfigEncryptionError("CONFIG_ENCRYPTION_KEY 未配置，无法安全存储敏感配置")
    try:
        padding = "=" * (-len(encoded_key) % 4)
        key = base64.b64decode(encoded_key + padding, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ConfigEncryptionError("CONFIG_ENCRYPTION_KEY 格式无效，必须是 Base64 编码的 32 字节密钥") from exc
    if len(key) != _KEY_SIZE:
        raise ConfigEncryptionError("CONFIG_ENCRYPTION_KEY 格式无效，必须是 Base64 编码的 32 字节密钥")
    return key


def encryption_available() -> bool:
    encoded_key = _get_encryption_key()
    if not encoded_key:
        return False
    _decode_key(encoded_key)
    return True


def validate_keyring() -> bool:
    current_key = _get_encryption_key()
    previous_keys = _get_previous_encryption_keys()
    if current_key:
        _decode_key(current_key)
    for previous_key in previous_keys:
        _decode_key(previous_key)
    if previous_keys and not current_key:
        raise ConfigEncryptionError("配置了历史加密密钥，但 CONFIG_ENCRYPTION_KEY 当前密钥未配置")
    return bool(current_key)


def keyring_fingerprint() -> str:
    """Return a non-secret identity for the validated encryption keyring."""
    current_key = _get_encryption_key()
    previous_keys = _get_previous_encryption_keys()
    validate_keyring()
    digest = hashlib.sha256()
    for encoded_key in (current_key, *previous_keys):
        key_bytes = encoded_key.encode("utf-8")
        digest.update(len(key_bytes).to_bytes(4, "big"))
        digest.update(key_bytes)
    return digest.hexdigest()


def is_encrypted(value: str) -> bool:
    return value.startswith(ENCRYPTED_PREFIX)


def _associated_data(user_id: int, key_name: str) -> bytes:
    return f"user_config:{user_id}:{key_name}".encode("utf-8")


def encrypt_config_value(user_id: int, key_name: str, value: str) -> str:
    key = _decode_key(_get_encryption_key())
    nonce = os.urandom(_NONCE_SIZE)
    ciphertext = AESGCM(key).encrypt(
        nonce,
        value.encode("utf-8"),
        _associated_data(user_id, key_name),
    )
    token = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return ENCRYPTED_PREFIX + token


def decrypt_config_value(user_id: int, key_name: str, value: str) -> str:
    return decrypt_config_value_with_metadata(user_id, key_name, value).value


def decrypt_config_value_with_metadata(
    user_id: int,
    key_name: str,
    value: str,
) -> DecryptedConfigValue:
    if not is_encrypted(value):
        return DecryptedConfigValue(value=value, needs_rotation=False)
    current_key = _get_encryption_key()
    keyring = [current_key, *_get_previous_encryption_keys()]
    if not current_key:
        raise ConfigEncryptionError("CONFIG_ENCRYPTION_KEY 未配置，无法解密敏感配置")
    try:
        payload = base64.b64decode(
            value[len(ENCRYPTED_PREFIX) :],
            altchars=b"-_",
            validate=True,
        )
        if len(payload) <= _NONCE_SIZE:
            raise ValueError("encrypted payload is too short")
    except (binascii.Error, ValueError) as exc:
        raise ConfigEncryptionError("敏感配置解密失败，请检查 CONFIG_ENCRYPTION_KEY 是否与写入时一致") from exc

    for index, encoded_key in enumerate(keyring):
        key = _decode_key(encoded_key)
        try:
            plaintext = AESGCM(key).decrypt(
                payload[:_NONCE_SIZE],
                payload[_NONCE_SIZE:],
                _associated_data(user_id, key_name),
            )
            return DecryptedConfigValue(
                value=plaintext.decode("utf-8"),
                needs_rotation=index > 0,
            )
        except InvalidTag:
            continue
        except UnicodeDecodeError as exc:
            raise ConfigEncryptionError("敏感配置明文编码无效") from exc
    raise ConfigEncryptionError("敏感配置解密失败，请检查当前或历史 CONFIG_ENCRYPTION_KEY 是否正确")
