import sqlite3
from collections.abc import Callable
from typing import cast

from app.core.security import (
    dummy_verify,
    generate_temp_password,
    hash_password,
    hash_token,
    now_ts,
    verify_password,
)
from app.domain.identity import UserRecord
from app.infrastructure.persistence.connection import get_connection, unit_of_work


def _connection():
    return get_connection("user")


def count_users() -> int:
    return _connection().execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def get_user_by_username(username: str) -> UserRecord | None:
    row = _connection().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return cast(UserRecord, dict(row)) if row else None


def get_user_by_id(user_id: int) -> UserRecord | None:
    row = _connection().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return cast(UserRecord, dict(row)) if row else None


def create_user(
    username: str,
    password: str,
    is_admin: bool = False,
    must_change_password: bool = False,
) -> UserRecord:
    connection = _connection()
    cursor = connection.execute(
        "INSERT INTO users (username, password_hash, is_admin, must_change_password) VALUES (?, ?, ?, ?)",
        (username, hash_password(password), int(is_admin), int(must_change_password)),
    )
    connection.commit()
    return cast(UserRecord, get_user_by_id(cursor.lastrowid))


def ensure_default_admin(user_count: Callable[[], int] | None = None) -> str | None:
    """在空实例中原子创建必须改密的默认管理员。"""
    if user_count is None:
        user_count = count_users
    if user_count() > 0:
        return None
    from app.configuration import get_settings

    username = (get_settings().default_admin_username or "admin").strip() or "admin"
    password = generate_temp_password()
    password_hash = hash_password(password)
    try:
        with unit_of_work(connection=_connection(), immediate=True) as work:
            connection = work.connection
            if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None:
                return None
            connection.execute(
                "INSERT INTO users (username, password_hash, is_admin, must_change_password) VALUES (?, ?, 1, 1)",
                (username, password_hash),
            )
            return password
    except sqlite3.IntegrityError:
        return None


def create_account(
    username: str,
    password: str,
    *,
    is_admin: bool,
    invite_code: str | None,
) -> tuple[str, UserRecord | None]:
    """在同一事务中创建账户并消费邀请码。"""
    password_hash = hash_password(password)
    try:
        with unit_of_work(connection=_connection(), immediate=True) as work:
            connection = work.connection
            if connection.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone() is not None:
                return ("duplicate", None)
            if invite_code is None:
                bootstrap_open = connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None
                if not is_admin or not bootstrap_open:
                    return ("bootstrap_closed", None)
            else:
                is_admin = False
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
                (username, password_hash, int(is_admin)),
            )
            user_id = cursor.lastrowid
            if invite_code is not None:
                current_time = now_ts()
                result = connection.execute(
                    "UPDATE invites SET used_by = ?, used_at = ? "
                    "WHERE code = ? AND used_by IS NULL AND (expires_at IS NULL OR expires_at > ?)",
                    (user_id, current_time, invite_code, current_time),
                )
                if result.rowcount != 1:
                    work.mark_rollback()
                    return ("invite_taken", None)
        return ("ok", get_user_by_id(user_id))
    except sqlite3.IntegrityError:
        return ("duplicate", None)


def verify_credentials(username: str, password: str) -> UserRecord | None:
    user = get_user_by_username(username)
    if not user:
        dummy_verify()
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def change_password_and_revoke_sessions(
    user_id: int,
    new_password: str,
    keep_token_hash: str | None,
) -> int:
    password_hash = hash_password(new_password)
    with unit_of_work(connection=_connection(), immediate=True) as work:
        connection = work.connection
        connection.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
            (password_hash, user_id),
        )
        if keep_token_hash:
            cursor = connection.execute(
                "DELETE FROM auth_sessions WHERE user_id = ? AND token_hash != ?",
                (user_id, keep_token_hash),
            )
        else:
            cursor = connection.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))
        return cursor.rowcount


def reset_password_with_token(token: str, new_password: str) -> int | None:
    connection = _connection()
    token_hash = hash_token(token)
    current_time = now_ts()
    reset_query = (
        "SELECT user_id FROM password_resets "
        "WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?"
    )
    if connection.execute(reset_query, (token_hash, current_time)).fetchone() is None:
        return None
    password_hash = hash_password(new_password)
    with unit_of_work(connection=connection, immediate=True) as work:
        row = connection.execute(reset_query, (token_hash, current_time)).fetchone()
        if row is None:
            return None

        user_id = row["user_id"]
        connection.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
            (password_hash, user_id),
        )
        connection.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))
        result = connection.execute(
            "UPDATE password_resets SET used_at = ? "
            "WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
            (current_time, token_hash, current_time),
        )
        if result.rowcount != 1:
            work.mark_rollback()
            return None
        return user_id


_ACCOUNT_TABLES = (
    "users",
    "auth_sessions",
    "invites",
    "user_config",
    "password_resets",
    "bot_command_jobs",
    "bot_rate_limit_events",
)


def count_all_accounts() -> dict[str, int]:
    connection = _connection()
    return {
        table: connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
        for table in _ACCOUNT_TABLES
    }


def reset_all_accounts() -> dict[str, int]:
    before = count_all_accounts()
    connection = _connection()
    for table in (
        "bot_command_jobs",
        "bot_rate_limit_events",
        "auth_sessions",
        "password_resets",
        "invites",
        "user_config",
        "users",
    ):
        connection.execute(f"DELETE FROM {table}")
    connection.commit()
    return before
