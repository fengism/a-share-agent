from typing import cast

from app.contracts.auth import UserRecord
from app.core.security import (
    SESSION_RENEW_THRESHOLD_DAYS,
    generate_session_token,
    hash_token,
    now_ts,
    session_expiry,
)
from app.infrastructure.persistence.connection import get_connection


def _connection():
    return get_connection("user")


def create_session(user_id: int) -> str:
    token = generate_session_token()
    connection = _connection()
    connection.execute(
        "INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (hash_token(token), user_id, session_expiry()),
    )
    connection.commit()
    return token


def get_user_by_token(token: str) -> UserRecord | None:
    row = _connection().execute(
        """SELECT u.* FROM auth_sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token_hash = ? AND s.expires_at > ?""",
        (hash_token(token), now_ts()),
    ).fetchone()
    return cast(UserRecord, dict(row)) if row else None


def resolve_and_renew_session_with_status(token: str) -> tuple[UserRecord | None, bool]:
    connection = _connection()
    token_hash = hash_token(token)
    row = connection.execute(
        """SELECT u.*, s.expires_at AS _session_expires
           FROM auth_sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token_hash = ? AND s.expires_at > ?""",
        (token_hash, now_ts()),
    ).fetchone()
    if not row:
        return None, False
    renewed = False
    if row["_session_expires"] <= session_expiry(SESSION_RENEW_THRESHOLD_DAYS):
        connection.execute(
            "UPDATE auth_sessions SET expires_at = ? WHERE token_hash = ?",
            (session_expiry(), token_hash),
        )
        connection.commit()
        renewed = True
    user = dict(row)
    user.pop("_session_expires", None)
    return cast(UserRecord, user), renewed


def resolve_and_renew_session(token: str) -> UserRecord | None:
    user, _ = resolve_and_renew_session_with_status(token)
    return user


def delete_session(token: str) -> None:
    connection = _connection()
    connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (hash_token(token),))
    connection.commit()


def purge_expired() -> dict[str, int]:
    connection = _connection()
    current_time = now_ts()
    sessions = connection.execute(
        "DELETE FROM auth_sessions WHERE expires_at <= ?",
        (current_time,),
    ).rowcount
    resets = connection.execute(
        "DELETE FROM password_resets WHERE expires_at <= ? OR used_at IS NOT NULL",
        (current_time,),
    ).rowcount
    connection.commit()
    return {"auth_sessions": sessions, "password_resets": resets}
