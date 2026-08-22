import hashlib
import sqlite3
import time
from dataclasses import dataclass
from typing import TypeAlias, cast

from app.infrastructure.persistence.connection import get_connection as get_db_connection
from app.infrastructure.persistence.connection import unit_of_work


@dataclass(frozen=True, slots=True)
class ChatStateRecord:
    user_id: int
    payload_json: str
    revision: int
    updated_at: float


@dataclass(frozen=True, slots=True)
class ChatStateWriteSuccess:
    state: ChatStateRecord
    changed: bool


@dataclass(frozen=True, slots=True)
class ChatStateWriteConflict:
    current_state: ChatStateRecord | None


ChatStateWriteResult: TypeAlias = ChatStateWriteSuccess | ChatStateWriteConflict


def get_connection() -> sqlite3.Connection:
    return cast(sqlite3.Connection, get_db_connection("user"))


def _record_from_row(row: sqlite3.Row) -> ChatStateRecord:
    return ChatStateRecord(
        user_id=int(row["user_id"]),
        payload_json=str(row["payload_json"]),
        revision=int(row["revision"]),
        updated_at=float(row["updated_at"]),
    )


def get_state(
    user_id: int,
    *,
    connection: sqlite3.Connection | None = None,
) -> ChatStateRecord | None:
    row = (connection or get_connection()).execute(
        "SELECT user_id, payload_json, revision, updated_at FROM chat_states WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return _record_from_row(row) if row is not None else None


def compare_and_swap_state(
    user_id: int,
    payload_json: str,
    expected_revision: int,
    *,
    connection: sqlite3.Connection | None = None,
) -> ChatStateWriteResult:
    target = connection or get_connection()
    updated_at = time.time()
    payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    with unit_of_work(connection=target, immediate=True) as work:
        current = work.connection.execute(
            "SELECT user_id, payload_json, payload_hash, revision, updated_at FROM chat_states WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        changed = False
        conflict = False
        if current is None:
            if expected_revision != 0:
                conflict = True
            else:
                work.connection.execute(
                    """
                    INSERT INTO chat_states(user_id, payload_json, payload_hash, revision, updated_at)
                    VALUES (?, ?, ?, 1, ?)
                    """,
                    (user_id, payload_json, payload_hash, updated_at),
                )
                changed = True
        elif int(current["revision"]) != expected_revision:
            conflict = True
        elif current["payload_hash"] != payload_hash:
            work.connection.execute(
                """
                UPDATE chat_states
                SET payload_json = ?, payload_hash = ?, revision = revision + 1, updated_at = ?
                WHERE user_id = ? AND revision = ?
                """,
                (payload_json, payload_hash, updated_at, user_id, expected_revision),
            )
            changed = True
        row = work.connection.execute(
            "SELECT user_id, payload_json, revision, updated_at FROM chat_states WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    current_state = _record_from_row(row) if row is not None else None
    if conflict:
        return ChatStateWriteConflict(current_state=current_state)
    if current_state is None:
        raise RuntimeError("聊天状态写入成功后未能读取持久化记录")
    return ChatStateWriteSuccess(state=current_state, changed=changed)
