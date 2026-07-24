"""Authentication primitives — password hashing and session/invite tokens.

Uses only the Python standard library (PBKDF2-HMAC-SHA256), so no extra
dependency is required. Passwords are never stored in plaintext; session
tokens are stored only as SHA-256 hashes.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

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


def generate_session_token() -> str:
    """Generate an opaque, URL-safe session token (the plaintext given to the client)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a session/invite token for storage (never store the plaintext token)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry(days: int = SESSION_TTL_DAYS) -> str:
    """Return the session expiry timestamp string (local time)."""
    return (datetime.now() + timedelta(days=days)).strftime(_TS_FMT)


def now_ts() -> str:
    """Current local timestamp string, matching the DB timestamp format."""
    return datetime.now().strftime(_TS_FMT)


def invite_expiry(days: int) -> str:
    """Return an expiry timestamp `days` from now (for invite codes)."""
    return (datetime.now() + timedelta(days=days)).strftime(_TS_FMT)


def generate_invite_code() -> str:
    """Generate a URL-safe invite code."""
    return secrets.token_urlsafe(12)
