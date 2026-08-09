"""用户量化策略仓储。"""

import json
import time
from dataclasses import dataclass
from typing import Any

from app.infrastructure.persistence.connection import get_connection


@dataclass(frozen=True)
class SavedStrategyRow:
    id: int
    user_id: int
    name: str
    config: dict[str, Any]
    created_at: float
    updated_at: float


def _to_strategy(row) -> SavedStrategyRow:
    return SavedStrategyRow(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        config=json.loads(row["config_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def save_strategy(
    user_id: int,
    name: str,
    config: dict[str, Any],
    *,
    now: float | None = None,
) -> SavedStrategyRow:
    current_time = time.time() if now is None else now
    connection = get_connection("user")
    connection.execute(
        """
        INSERT INTO quant_strategies(user_id, name, config_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, name) DO UPDATE SET
            config_json = excluded.config_json,
            updated_at = excluded.updated_at
        """,
        (
            user_id,
            name,
            json.dumps(config, ensure_ascii=False, separators=(",", ":")),
            current_time,
            current_time,
        ),
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM quant_strategies WHERE user_id = ? AND name = ?",
        (user_id, name),
    ).fetchone()
    return _to_strategy(row)


def list_strategies(user_id: int) -> list[SavedStrategyRow]:
    rows = get_connection("user").execute(
        "SELECT * FROM quant_strategies WHERE user_id = ? ORDER BY updated_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    return [_to_strategy(row) for row in rows]


def delete_strategy(user_id: int, strategy_id: int) -> bool:
    connection = get_connection("user")
    cursor = connection.execute(
        "DELETE FROM quant_strategies WHERE id = ? AND user_id = ?",
        (strategy_id, user_id),
    )
    connection.commit()
    return cursor.rowcount == 1
