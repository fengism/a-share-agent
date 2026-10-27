"""Authentication primitives — password hashing and session/invite tokens.

Uses only the Python standard library (PBKDF2-HMAC-SHA256), so no extra
dependency is required. Passwords are never stored in plaintext; session
tokens are stored only as SHA-256 hashes.
"""
import hashlib
import hmac
import secrets
from datetime import timedelta

from app.domain.timezones import market_now

_PBKDF2_ROUNDS = 200_000
_SALT_BYTES = 16
SESSION_TTL_DAYS = 14
# Sliding renewal: a still-valid session is extended back to a full TTL once it
# is within this many days of expiring (so active users stay logged in, while
# the DB is written at most once per (TTL - threshold) per session).
SESSION_RENEW_THRESHOLD_DAYS = 7
_TS_FMT = "%Y-%m-%d %H:%M:%S"


def hash_password(password: str) -> str:
    """Hash a password with a random salt using PBKDF2-HMAC-SHA256.

    Return:
        an encoded string: ``pbkdf2_sha256$<rounds>$<salt_hex>$<hash_hex>``.
    """
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verify a password against a stored PBKDF2 hash."""
    try:
        algo, rounds_s, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds_s))
        return hmac.compare_digest(dk, bytes.fromhex(hash_hex))
    except (ValueError, AttributeError):
        return False


# A valid-shaped hash of a random throwaway password. Verifying against it when a
# username does not exist makes a "no such user" path spend the same PBKDF2 time
# as a "wrong password" path, so response timing can't be used to enumerate valid
# usernames. Computed once at import.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


def dummy_verify() -> None:
    """Burn one PBKDF2 verification to equalise timing on the no-such-user path."""
    verify_password("timing-equaliser", _DUMMY_PASSWORD_HASH)


#: 高频弱口令（大小写不敏感比较）。刻意保持精简：这是"最低门槛"，
#: 不是完备的密码字典；更严格的要求应由部署方在边缘层（WAF/IdP）补齐。
WEAK_PASSWORDS: frozenset[str] = frozenset(
    {
        "12345678",
        "123456789",
        "1234567890",
        "password",
        "password1",
        "password123",
        "passw0rd",
        "p@ssw0rd",
        "qwerty123",
        "qwertyuiop",
        "abc123456",
        "abcd1234",
        "admin123",
        "admin1234",
        "root1234",
        "iloveyou",
        "letmein1",
        "welcome1",
        "1qaz2wsx",
        "1q2w3e4r",
        "zaq12wsx",
        "asdfghjkl",
        "a12345678",
        "88888888",
        "11111111",
        "00000000",
        "12341234",
        "aaa111111",
    }
)

MIN_PASSWORD_LENGTH = 8


class WeakPasswordError(ValueError):
    """密码不满足最低强度要求；``reason`` 用于面向用户的提示。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def validate_password_policy(password: str, username: str = "") -> None:
    """校验密码强度，不满足时抛 :class:`WeakPasswordError`。

    规则（与 ``app.modules.auth.schemas.validate_password_strength`` 的
    「长度 8-128 + 必须含字母和数字」互补，这里补的是弱口令/用户名/重复字符）：
    1. 长度 >= 8；
    2. 不在高频弱口令表里；
    3. 不等于用户名，也不包含用户名（用户名长度 >= 4 时才检查）；
    4. 不能是同一个字符的重复。
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(f"密码至少需要 {MIN_PASSWORD_LENGTH} 位")
    lowered = password.strip().lower()
    if lowered in WEAK_PASSWORDS:
        raise WeakPasswordError("密码过于常见，请更换更复杂的密码")
    if len(set(password)) == 1:
        raise WeakPasswordError("密码不能是同一个字符的重复")
    normalized_username = (username or "").strip().lower()
    if normalized_username and lowered == normalized_username:
        raise WeakPasswordError("密码不能与用户名相同")
    if len(normalized_username) >= 4 and normalized_username in lowered:
        raise WeakPasswordError("密码不能包含用户名")


def generate_session_token() -> str:
    """Generate an opaque, URL-safe session token (the plaintext given to the client)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a session/invite token for storage (never store the plaintext token)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry(days: int = SESSION_TTL_DAYS) -> str:
    """Return the session expiry timestamp string (local time)."""
    return (market_now() + timedelta(days=days)).strftime(_TS_FMT)


def now_ts() -> str:
    """Current local timestamp string, matching the DB timestamp format."""
    return market_now().strftime(_TS_FMT)


def invite_expiry(days: int) -> str:
    """Return an expiry timestamp `days` from now (for invite codes)."""
    return (market_now() + timedelta(days=days)).strftime(_TS_FMT)


def expiry_in_hours(hours: int) -> str:
    """Return an expiry timestamp `hours` from now (for password-reset links)."""
    return (market_now() + timedelta(hours=hours)).strftime(_TS_FMT)


def generate_invite_code() -> str:
    """Generate a URL-safe invite code."""
    return secrets.token_urlsafe(12)


def generate_temp_password() -> str:
    """Generate a random, typeable temporary password (for the seeded admin)."""
    part = secrets.token_urlsafe(12)
    if not any(c.isdigit() for c in part):
        part = f"{part[:10]}9{part[11:]}" if len(part) > 11 else f"{part}9"
    if not any(c.isalpha() for c in part):
        part = f"{part[:10]}a{part[11:]}" if len(part) > 11 else f"{part}a"
    return part
