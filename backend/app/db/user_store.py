"""Data access for accounts: users, sessions, invites and per-user config."""
import logging

from app.db.connection import get_connection
from app.utils.auth import (
    hash_password,
    verify_password,
    hash_token,
    generate_session_token,
    session_expiry,
    now_ts,
)

logger = logging.getLogger(__name__)


# ── Users ──────────────────────────────────────────────
def count_users() -> int:
    return get_connection().execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def get_user_by_username(username: str) -> dict | None:
    row = get_connection().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    row = get_connection().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def create_user(username: str, password: str, is_admin: bool = False) -> dict:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
        (username, hash_password(password), 1 if is_admin else 0),
    )
    conn.commit()
    return get_user_by_id(cur.lastrowid)


def verify_credentials(username: str, password: str) -> dict | None:
    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        return None
    return user


# ── Sessions ───────────────────────────────────────────
def create_session(user_id: int) -> str:
    token = generate_session_token()
    conn = get_connection()
    conn.execute(
        "INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (hash_token(token), user_id, session_expiry()),
    )
    conn.commit()
    return token


def get_user_by_token(token: str) -> dict | None:
    row = get_connection().execute(
        """SELECT u.* FROM auth_sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token_hash = ? AND s.expires_at > ?""",
        (hash_token(token), now_ts()),
    ).fetchone()
    return dict(row) if row else None


def delete_session(token: str) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (hash_token(token),))
    conn.commit()


# ── Invites ────────────────────────────────────────────
def create_invite(created_by: int, code: str, expires_at: str | None = None) -> dict:
    conn = get_connection()
    conn.execute(
        "INSERT INTO invites (code, created_by, expires_at) VALUES (?, ?, ?)",
        (code, created_by, expires_at),
    )
    conn.commit()
    return get_invite(code)


def get_invite(code: str) -> dict | None:
    row = get_connection().execute("SELECT * FROM invites WHERE code = ?", (code,)).fetchone()
    return dict(row) if row else None


def invite_is_valid(code: str) -> bool:
    inv = get_invite(code)
    if not inv or inv["used_by"] is not None:
        return False
    if inv["expires_at"] and inv["expires_at"] < now_ts():
        return False
    return True


def consume_invite(code: str, used_by: int) -> bool:
    """Atomically mark an unused, unexpired invite as used. Returns True on success."""
    conn = get_connection()
    cur = conn.execute(
        "UPDATE invites SET used_by = ?, used_at = ? WHERE code = ? AND used_by IS NULL",
        (used_by, now_ts(), code),
    )
    conn.commit()
    return cur.rowcount == 1


def list_invites(created_by: int) -> list[dict]:
    cur = get_connection().execute(
        "SELECT * FROM invites WHERE created_by = ? ORDER BY created_at DESC", (created_by,)
    )
    return [dict(r) for r in cur.fetchall()]


# ── Per-user config ────────────────────────────────────
def get_user_config(user_id: int) -> dict[str, str]:
    cur = get_connection().execute("SELECT key, value FROM user_config WHERE user_id = ?", (user_id,))
    return {r["key"]: r["value"] for r in cur.fetchall()}


def set_user_config(user_id: int, items: dict) -> None:
    if not items:
        return
    conn = get_connection()
    conn.executemany(
        "INSERT INTO user_config (user_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
        [(user_id, k, "" if v is None else str(v)) for k, v in items.items()],
    )
    conn.commit()
