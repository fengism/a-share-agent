from app.core.security import hash_token, now_ts
from app.infrastructure.persistence.connection import get_connection


def _connection():
    return get_connection("user")


def create_invite(created_by: int, code: str, expires_at: str | None = None) -> dict:
    connection = _connection()
    connection.execute(
        "INSERT INTO invites (code, created_by, expires_at) VALUES (?, ?, ?)",
        (code, created_by, expires_at),
    )
    connection.commit()
    return get_invite(code)


def get_invite(code: str) -> dict | None:
    row = _connection().execute("SELECT * FROM invites WHERE code = ?", (code,)).fetchone()
    return dict(row) if row else None


def invite_is_valid(code: str) -> bool:
    invite = get_invite(code)
    if not invite or invite["used_by"] is not None:
        return False
    if invite["expires_at"] and invite["expires_at"] < now_ts():
        return False
    return True


def list_invites(created_by: int | None = None) -> list[dict]:
    if created_by is None:
        cursor = _connection().execute("SELECT * FROM invites ORDER BY created_at DESC")
    else:
        cursor = _connection().execute(
            "SELECT * FROM invites WHERE created_by = ? ORDER BY created_at DESC",
            (created_by,),
        )
    return [dict(row) for row in cursor.fetchall()]


def revoke_invite(code: str, created_by: int | None = None) -> str:
    invite = get_invite(code)
    if not invite:
        return "not_found"
    if invite["used_by"] is not None:
        return "used"
    connection = _connection()
    cursor = connection.execute(
        "DELETE FROM invites WHERE code = ? AND used_by IS NULL",
        (code,),
    )
    connection.commit()
    return "revoked" if cursor.rowcount == 1 else "used"


def cleanup_expired_invites() -> int:
    connection = _connection()
    current_time = now_ts()
    cursor = connection.execute(
        "DELETE FROM invites WHERE used_by IS NULL AND expires_at IS NOT NULL AND expires_at < ?",
        (current_time,),
    )
    connection.commit()
    return cursor.rowcount


def create_password_reset(user_id: int, created_by: int, token: str, expires_at: str) -> None:
    connection = _connection()
    connection.execute(
        "INSERT INTO password_resets (token_hash, user_id, created_by, expires_at) VALUES (?, ?, ?, ?)",
        (hash_token(token), user_id, created_by, expires_at),
    )
    connection.commit()


def consume_password_reset(token: str) -> int | None:
    connection = _connection()
    token_hash = hash_token(token)
    current_time = now_ts()
    cursor = connection.execute(
        "UPDATE password_resets SET used_at = ? "
        "WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
        (current_time, token_hash, current_time),
    )
    connection.commit()
    if cursor.rowcount != 1:
        return None
    row = connection.execute(
        "SELECT user_id FROM password_resets WHERE token_hash = ?",
        (token_hash,),
    ).fetchone()
    return row["user_id"] if row else None
