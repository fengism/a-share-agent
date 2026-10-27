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


#: 单用户最多保留的有效会话数；超出时淘汰最久未使用的，避免会话表被无限撑大。
MAX_SESSIONS_PER_USER = 10


def create_session(user_id: int, *, ip_address: str = "", user_agent: str = "") -> str:
    """创建会话。

    显式写入 ``created_at``（北京时间）而不是依赖 DDL 的 ``datetime('now','localtime')``：
    容器/裸机 TZ 不一致时，默认值会写成本地时间，与业务时间戳差 8 小时。
    """
    token = generate_session_token()
    with unit_of_work("user", immediate=True) as work:
        work.connection.execute(
            """
            INSERT INTO auth_sessions (
                token_hash, user_id, created_at, expires_at, ip_address, user_agent, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hash_token(token),
                user_id,
                now_ts(),
                session_expiry(),
                ip_address[:64],
                user_agent[:512],
                now_ts(),
            ),
        )
        # 超出上限时淘汰最久未活跃的会话（含已过期的）。放在同一事务里，
        # 避免并发登录后残留一堆僵尸会话。同一秒内创建的会话时间戳相同，
        # 因此用 rowid 兜底排序，保证"保留最新的那几个"。
        work.connection.execute(
            """
            DELETE FROM auth_sessions
            WHERE user_id = ?
              AND token_hash NOT IN (
                SELECT token_hash FROM auth_sessions
                WHERE user_id = ?
                ORDER BY COALESCE(last_seen_at, created_at) DESC, rowid DESC
                LIMIT ?
              )
            """,
            (user_id, user_id, MAX_SESSIONS_PER_USER),
        )
    return token


#: 设备句柄长度：token_hash 前 N 个十六进制字符（足够区分同一用户的少数设备，且不暴露完整哈希）。
SESSION_HANDLE_LENGTH = 12


def _session_handle(token_hash: str) -> str:
    return token_hash[:SESSION_HANDLE_LENGTH]


def list_user_sessions(user_id: int, *, current_token: str | None = None) -> list[dict[str, object]]:
    """列出该用户仍有效的会话（供「登录设备」自助管理）。"""
    current_hash = hash_token(current_token) if current_token else ""
    rows = _connection().execute(
        """
        SELECT token_hash, created_at, expires_at, ip_address, user_agent, last_seen_at
        FROM auth_sessions
        WHERE user_id = ? AND expires_at > ?
        ORDER BY created_at DESC
        """,
        (user_id, now_ts()),
    ).fetchall()
    sessions: list[dict[str, object]] = []
    for row in rows:
        record = dict(row)
        sessions.append(
            {
                "session_id": _session_handle(str(record["token_hash"])),
                "created_at": record["created_at"],
                "expires_at": record["expires_at"],
                "ip_address": record.get("ip_address") or "",
                "user_agent": record.get("user_agent") or "",
                # 老库升级后 last_seen_at 为空，回退到创建时间，避免前端显示空白
                "last_seen_at": record.get("last_seen_at") or record["created_at"],
                "is_current": bool(current_hash) and record["token_hash"] == current_hash,
            }
        )
    return sessions


def revoke_user_session(user_id: int, session_handle: str) -> bool:
    """按句柄撤销该用户自己的一个会话；句柄必须属于该用户。"""
    handle = session_handle.strip().lower()
    if len(handle) < 8 or any(char not in "0123456789abcdef" for char in handle):
        return False
    with unit_of_work("user", immediate=True) as work:
        cursor = work.connection.execute(
            "DELETE FROM auth_sessions WHERE user_id = ? AND token_hash LIKE ?",
            (user_id, f"{handle}%"),
        )
        return cursor.rowcount > 0


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
                "UPDATE auth_sessions SET expires_at = ?, last_seen_at = ? WHERE token_hash = ?",
                (session_expiry(), now_ts(), token_hash),
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
