"""Bounded retention deletion helpers for SQLite stores."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.infrastructure.persistence.connection import unit_of_work

DEFAULT_PURGE_BATCH_SIZE = 1000
DEFAULT_PURGE_MAX_BATCHES = 4

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ORDER_BY_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\s+(?:ASC|DESC))?(?:,\s*[A-Za-z_][A-Za-z0-9_]*(?:\s+(?:ASC|DESC))?)*$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PurgeResult:
    deleted: int
    batches: int
    has_more: bool


def purge_rows_in_batches(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    predicate_sql: str,
    parameters: Sequence[Any] = (),
    order_by: str = "rowid",
    batch_size: int = DEFAULT_PURGE_BATCH_SIZE,
    max_batches: int = DEFAULT_PURGE_MAX_BATCHES,
) -> PurgeResult:
    """Delete matching rows through a bounded number of independently committed batches."""
    if not _IDENTIFIER_PATTERN.fullmatch(table_name):
        raise ValueError(f"非法 SQL 标识符: {table_name!r}")
    if not _ORDER_BY_PATTERN.fullmatch(order_by):
        raise ValueError(f"非法 SQL 排序表达式: {order_by!r}")
    effective_batch_size = max(1, batch_size)
    effective_max_batches = max(1, max_batches)
    total_deleted = 0
    completed_batches = 0
    for _ in range(effective_max_batches):
        with unit_of_work(connection=connection, immediate=True) as work:
            cursor = work.connection.execute(
                f"""
                DELETE FROM {table_name}
                WHERE rowid IN (
                    SELECT rowid FROM {table_name}
                    WHERE {predicate_sql}
                    ORDER BY {order_by}
                    LIMIT ?
                )
                """,
                (*parameters, effective_batch_size),
            )
        deleted = max(0, cursor.rowcount)
        total_deleted += deleted
        completed_batches += 1
        if deleted < effective_batch_size:
            return PurgeResult(total_deleted, completed_batches, False)

    has_more = connection.execute(
        f"SELECT EXISTS(SELECT 1 FROM {table_name} WHERE {predicate_sql} LIMIT 1)",
        parameters,
    ).fetchone()[0]
    return PurgeResult(total_deleted, completed_batches, bool(has_more))


__all__ = [
    "DEFAULT_PURGE_BATCH_SIZE",
    "DEFAULT_PURGE_MAX_BATCHES",
    "PurgeResult",
    "purge_rows_in_batches",
]
