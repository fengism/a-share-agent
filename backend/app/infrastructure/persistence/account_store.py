import sqlite3
from collections.abc import Callable
from typing import Any, cast

from app.core.security import (
    dummy_verify,
    generate_temp_password,
    hash_password,
    hash_token,
    now_ts,
    verify_password,
)
from app.domain.identity import LoginAuditRecord, UserRecord
from app.infrastructure.persistence.connection import get_connection, unit_of_work


def _connection():
    return get_connection("user")


def count_users() -> int:
    return _connection().execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def get_user_by_username(username: str) -> UserRecord | None:
    row = _connection().execute(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE",
        (username.strip().lower(),),
    ).fetchone()
    return cast(UserRecord, dict(row)) if row else None


def get_user_by_id(user_id: int) -> UserRecord | None:
    row = _connection().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return cast(UserRecord, dict(row)) if row else None


def create_user(
    username: str,
    password: str,
    is_admin: bool = False,
    must_change_password: bool = False,
    is_active: bool = True,
) -> UserRecord:
    with unit_of_work(connection=_connection(), immediate=True) as work:
        cursor = work.connection.execute(
            "INSERT INTO users (username, password_hash, is_admin, must_change_password, is_active) VALUES (?, ?, ?, ?, ?)",
            (username.strip().lower(), hash_password(password), int(is_admin), int(must_change_password), int(is_active)),
        )
        user_id = cursor.lastrowid
    return cast(UserRecord, get_user_by_id(user_id))


def ensure_default_admin(user_count: Callable[[], int] | None = None) -> str | None:
    """在空实例中原子创建默认管理员。

    如果配置了 default_admin_password，则使用该密码且无需强制改密；
    否则生成随机临时密码，且必须改密。
    """
    if user_count is None:
        user_count = count_users
    if user_count() > 0:
        return None
    from app.configuration import get_settings

    settings = get_settings()
    username = (settings.default_admin_username or "admin").strip().lower() or "admin"
    custom_pwd = (settings.default_admin_password or "").strip()
    if custom_pwd:
        password = custom_pwd
        must_change_password = 0
        return_seed = None
    else:
        password = generate_temp_password()
        must_change_password = 1
        return_seed = password

    password_hash = hash_password(password)
    try:
        with unit_of_work(connection=_connection(), immediate=True) as work:
            connection = work.connection
            if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None:
                return None
            connection.execute(
                "INSERT INTO users (username, password_hash, is_admin, is_active, must_change_password) VALUES (?, ?, 1, 1, ?)",
                (username, password_hash, must_change_password),
            )
            return return_seed
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
    normalized_username = username.strip().lower()
    password_hash = hash_password(password)
    try:
        with unit_of_work(connection=_connection(), immediate=True) as work:
            connection = work.connection
            if connection.execute("SELECT 1 FROM users WHERE username = ? COLLATE NOCASE", (normalized_username,)).fetchone() is not None:
                return ("duplicate", None)
            if invite_code is None:
                bootstrap_open = connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None
                if not is_admin or not bootstrap_open:
                    return ("bootstrap_closed", None)
            else:
                is_admin = False
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash, is_admin, is_active) VALUES (?, ?, ?, 1)",
                (normalized_username, password_hash, int(is_admin)),
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
            "WHERE user_id = ? AND used_at IS NULL",
            (current_time, user_id),
        )
        if result.rowcount < 1:
            work.mark_rollback()
            return None
        return user_id


def list_users() -> list[UserRecord]:
    rows = _connection().execute(
        "SELECT id, username, is_admin, is_active, must_change_password, created_at FROM users ORDER BY id ASC"
    ).fetchall()
    return [cast(UserRecord, dict(row)) for row in rows]


def count_active_admins() -> int:
    row = _connection().execute(
        "SELECT COUNT(*) AS n FROM users WHERE is_admin = 1 AND is_active = 1"
    ).fetchone()
    return row["n"] if row else 0


def set_user_active(user_id: int, is_active: bool) -> bool:
    with unit_of_work(connection=_connection(), immediate=True) as work:
        cursor = work.connection.execute(
            "UPDATE users SET is_active = ? WHERE id = ?",
            (int(is_active), user_id),
        )
        if not is_active:
            work.connection.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))
        return cursor.rowcount > 0


def set_user_role(user_id: int, is_admin: bool) -> bool:
    with unit_of_work(connection=_connection(), immediate=True) as work:
        cursor = work.connection.execute(
            "UPDATE users SET is_admin = ? WHERE id = ?",
            (int(is_admin), user_id),
        )
        return cursor.rowcount > 0


def delete_user(user_id: int) -> bool:
    with unit_of_work(connection=_connection(), immediate=True) as work:
        connection = work.connection
        connection.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM user_config WHERE user_id = ?", (user_id,))
        cursor = connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return cursor.rowcount > 0


def revoke_user_sessions(user_id: int) -> int:
    with unit_of_work(connection=_connection(), immediate=True) as work:
        cursor = work.connection.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))
        return cursor.rowcount


def set_user_must_change_password(user_id: int, must_change: bool) -> bool:
    with unit_of_work(connection=_connection(), immediate=True) as work:
        cursor = work.connection.execute(
            "UPDATE users SET must_change_password = ? WHERE id = ?",
            (int(must_change), user_id),
        )
        return cursor.rowcount > 0


def reset_password_direct(
    username: str,
    new_password: str,
    ensure_admin: bool = False,
    ensure_active: bool = True,
) -> bool:
    """运维/CLI 直接重置指定用户密码，原子清理旧会话与待处理 Token。"""
    user = get_user_by_username(username)
    if not user:
        return False
    user_id = user["id"]
    new_hash = hash_password(new_password)
    with unit_of_work(connection=_connection(), immediate=True) as work:
        conn = work.connection
        updates = ["password_hash = ?", "must_change_password = 0"]
        params: list[Any] = [new_hash]
        if ensure_active:
            updates.append("is_active = 1")
        if ensure_admin:
            updates.append("is_admin = 1")
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", tuple(params))
        conn.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
    return True


def record_login_audit(
    username: str,
    user_id: int | None,
    ip_address: str,
    user_agent: str,
    status: str,
    details: str = "",
) -> None:
    with unit_of_work(connection=_connection(), immediate=True) as work:
        work.connection.execute(
            """
            INSERT INTO login_audit_logs (username, user_id, ip_address, user_agent, status, details)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, user_id, ip_address, user_agent, status, details),
        )


def list_login_audit_logs(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    username: str | None = None,
) -> tuple[list[LoginAuditRecord], int]:
    connection = _connection()
    where_clauses: list[str] = []
    params: list[Any] = []
    if status:
        where_clauses.append("status = ?")
        params.append(status)
    if username:
        where_clauses.append("username LIKE ?")
        params.append(f"%{username}%")
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    count_row = connection.execute(
        f"SELECT COUNT(*) AS n FROM login_audit_logs {where_sql}",
        tuple(params),
    ).fetchone()
    total = count_row["n"] if count_row else 0

    query = f"""
        SELECT id, username, user_id, ip_address, user_agent, status, details, created_at
        FROM login_audit_logs
        {where_sql}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
    """
    rows = connection.execute(query, (*params, limit, offset)).fetchall()
    return [cast(LoginAuditRecord, dict(row)) for row in rows], total


_ACCOUNT_TABLES = (
    "users",
    "auth_sessions",
    "invites",
    "user_config",
    "password_resets",
    "login_audit_logs",
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
    with unit_of_work(connection=_connection(), immediate=True) as work:
        for table in (
            "bot_command_jobs",
            "bot_rate_limit_events",
            "auth_sessions",
            "password_resets",
            "invites",
            "user_config",
            "users",
        ):
            work.connection.execute(f"DELETE FROM {table}")
    return before
