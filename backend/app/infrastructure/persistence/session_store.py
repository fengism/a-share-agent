from typing import cast

from app.core.security import (
    SESSION_RENEW_THRESHOLD_DAYS,
    generate_session_token,
    hash_token,
    now_ts,
    session_expiry,
)
from app.domain.identity import UserRecord
from app.infrastructure.persistence.connection import get_connection, unit_of_work
from app.infrastructure.persistence.retention import PurgeResult, purge_rows_in_batches


def _connection():
    return get_connection("user")


def create_session(user_id: int) -> str:
    token = generate_session_token()
    with unit_of_work("user", immediate=True) as work:
        work.connection.execute(
            "INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (hash_token(token), user_id, session_expiry()),
        )
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
        with unit_of_work("user", immediate=True) as work:
            work.connection.execute(
                "UPDATE auth_sessions SET expires_at = ? WHERE token_hash = ?",
                (session_expiry(), token_hash),
            )
        renewed = True
    user = dict(row)
    user.pop("_session_expires", None)
    return cast(UserRecord, user), renewed


def resolve_and_renew_session(token: str) -> UserRecord | None:
    user, _ = resolve_and_renew_session_with_status(token)
    return user


def delete_session(token: str) -> None:
    with unit_of_work("user", immediate=True) as work:
        work.connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (hash_token(token),))


def purge_expired() -> dict[str, int]:
    return {name: result.deleted for name, result in purge_expired_with_status().items()}


def purge_expired_with_status() -> dict[str, PurgeResult]:
    connection = _connection()
    current_time = now_ts()
    sessions = purge_rows_in_batches(
        connection,
        table_name="auth_sessions",
        predicate_sql="expires_at <= ?",
        parameters=(current_time,),
        order_by="expires_at, rowid",
    )
    resets = purge_rows_in_batches(
        connection,
        table_name="password_resets",
        predicate_sql="expires_at <= ? OR used_at IS NOT NULL",
        parameters=(current_time,),
        order_by="expires_at, rowid",
    )
    return {"auth_sessions": sessions, "password_resets": resets}
