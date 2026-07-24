"""Data access for accounts: users, sessions, invites and per-user config."""
import logging
import sqlite3

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


def create_account(
    username: str,
    password: str,
    *,
    is_admin: bool,
    invite_code: str | None,
) -> tuple[str, dict | None]:
    """Create a user and, when invite_code is given, consume the invite in the
    SAME transaction.

    Registration used to create the user first and consume the invite second, so
    a lost race (or any consume failure) left an orphan account that could still
    log in. Here the invite is claimed with an atomic guarded UPDATE inside the
    same transaction as the INSERT; if it can't be claimed, the whole transaction
    is rolled back and no user row survives.

    Returns (status, user):
      - ("ok", user)            success
      - ("invite_taken", None)  invite already used / expired / lost the race
      - ("duplicate", None)     username already exists (UNIQUE-constraint race)
    """
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
            (username, hash_password(password), 1 if is_admin else 0),
        )
        user_id = cur.lastrowid
        if invite_code is not None:
            now = now_ts()
            res = conn.execute(
                "UPDATE invites SET used_by = ?, used_at = ? "
                "WHERE code = ? AND used_by IS NULL AND (expires_at IS NULL OR expires_at > ?)",
                (user_id, now, invite_code, now),
            )
            if res.rowcount != 1:
                conn.rollback()  # undo the INSERT — no orphan account
                return ("invite_taken", None)
        conn.commit()
        return ("ok", get_user_by_id(user_id))
    except sqlite3.IntegrityError:
        conn.rollback()
        return ("duplicate", None)


def verify_credentials(username: str, password: str) -> dict | None:
    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        return None
    return user


def update_password(user_id: int, new_password: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(new_password), user_id),
    )
    conn.commit()


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


def delete_other_sessions(user_id: int, keep_token_hash: str | None) -> int:
    """Revoke all of a user's sessions except the one whose token hash is kept.

    Pass keep_token_hash=None to revoke every session. Returns rows deleted.
    """
    conn = get_connection()
    if keep_token_hash:
        cur = conn.execute(
            "DELETE FROM auth_sessions WHERE user_id = ? AND token_hash != ?",
            (user_id, keep_token_hash),
        )
    else:
        cur = conn.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    return cur.rowcount


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


def revoke_invite(code: str, created_by: int) -> str:
    """Delete an unused invite created by this admin. Returns:
    "revoked" (deleted) | "used" (already consumed, kept) | "not_found".

    The DELETE is guarded by ``used_by IS NULL`` so a concurrent consumption
    (someone registering with it right now) wins the race and the invite is
    reported as "used" rather than silently deleted.
    """
    inv = get_invite(code)
    if not inv or inv["created_by"] != created_by:
        return "not_found"
    if inv["used_by"] is not None:
        return "used"
    conn = get_connection()
    cur = conn.execute(
        "DELETE FROM invites WHERE code = ? AND created_by = ? AND used_by IS NULL",
        (code, created_by),
    )
    conn.commit()
    return "revoked" if cur.rowcount == 1 else "used"


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
