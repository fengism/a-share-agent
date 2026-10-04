"""SQLite 持久化租约任务的通用状态机。"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from app.infrastructure.persistence.connection import unit_of_work
from app.infrastructure.persistence.retention import (
    DEFAULT_PURGE_BATCH_SIZE,
    DEFAULT_PURGE_MAX_BATCHES,
    PurgeResult,
    purge_rows_in_batches,
)

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

ConnectionProvider = Callable[[], sqlite3.Connection]


def _validate_identifier(identifier: str) -> str:
    if not _IDENTIFIER_PATTERN.fullmatch(identifier):
        raise ValueError(f"非法 SQL 标识符: {identifier!r}")
    return identifier


@dataclass(frozen=True, slots=True)
class LeasedJobSpec:
    table_name: str
    terminal_statuses: tuple[str, ...] = ("succeeded", "failed")
    expired_lease_error: str = "任务租约过期且已达到最大重试次数"

    def __post_init__(self) -> None:
        _validate_identifier(self.table_name)
        if not self.terminal_statuses:
            raise ValueError("终态列表不能为空")


class LeasedJobStateStore:
    """Operate the shared lifecycle columns of one leased-job table."""

    def __init__(self, spec: LeasedJobSpec, connection_provider: ConnectionProvider) -> None:
        self._spec = spec
        self._connection_provider = connection_provider

    @property
    def table_name(self) -> str:
        return self._spec.table_name

    def claim_next(
        self,
        owner_id: str,
        lease_seconds: float,
        *,
        now: float,
    ) -> sqlite3.Row | None:
        table_name = self.table_name
        with unit_of_work(
            connection=self._connection_provider(),
            immediate=True,
        ) as work:
            connection = work.connection
            connection.execute(
                f"""
                UPDATE {table_name}
                SET status = 'failed',
                    last_error = CASE
                        WHEN last_error IS NULL OR last_error = '' THEN ?
                        ELSE substr(last_error || '; ' || ?, 1, 1000)
                    END,
                    completed_at = ?, updated_at = ?,
                    lease_owner = NULL, lease_until = NULL
                WHERE status = 'running'
                  AND lease_until IS NOT NULL
                  AND lease_until <= ?
                  AND attempts >= max_attempts
                """,
                (
                    self._spec.expired_lease_error,
                    self._spec.expired_lease_error,
                    now,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                f"""
                SELECT id FROM {table_name}
                WHERE attempts < max_attempts
                  AND (
                      (status = 'pending' AND available_at <= ?)
                      OR (status = 'running' AND lease_until <= ?)
                  )
                ORDER BY created_at, id
                LIMIT 1
                """,
                (now, now),
            ).fetchone()
            if row is None:
                return None
            cursor = connection.execute(
                f"""
                UPDATE {table_name}
                SET status = 'running', attempts = attempts + 1,
                    lease_owner = ?, lease_until = ?, updated_at = ?
                WHERE id = ? AND attempts < max_attempts
                  AND (
                      (status = 'pending' AND available_at <= ?)
                      OR (status = 'running' AND lease_until <= ?)
                  )
                """,
                (
                    owner_id,
                    now + max(1.0, lease_seconds),
                    now,
                    row["id"],
                    now,
                    now,
                ),
            )
            if cursor.rowcount != 1:
                return None
            return cast(
                sqlite3.Row | None,
                connection.execute(
                    f"SELECT * FROM {table_name} WHERE id = ?",
                    (row["id"],),
                ).fetchone(),
            )

    def renew_lease(
        self,
        job_id: str,
        owner_id: str,
        lease_seconds: float,
        *,
        now: float,
    ) -> bool:
        with unit_of_work(connection=self._connection_provider(), immediate=True) as work:
            cursor = work.connection.execute(
                f"""
                UPDATE {self.table_name}
                SET lease_until = ?, updated_at = ?
                WHERE id = ? AND status = 'running' AND lease_owner = ?
                  AND lease_until > ?
                """,
                (now + max(1.0, lease_seconds), now, job_id, owner_id, now),
            )
            return bool(cursor.rowcount == 1)

    def complete(
        self,
        job_id: str,
        owner_id: str,
        *,
        now: float,
        updates: Mapping[str, Any] | None = None,
    ) -> bool:
        assignments = [
            "status = 'succeeded'",
            "completed_at = ?",
            "updated_at = ?",
            "lease_owner = NULL",
            "lease_until = NULL",
            "last_error = NULL",
        ]
        values: list[Any] = [now, now]
        for column, value in (updates or {}).items():
            assignments.append(f"{_validate_identifier(column)} = ?")
            values.append(value)
        values.extend((job_id, owner_id))
        with unit_of_work(connection=self._connection_provider(), immediate=True) as work:
            cursor = work.connection.execute(
                f"""
                UPDATE {self.table_name}
                SET {', '.join(assignments)}
                WHERE id = ? AND status = 'running' AND lease_owner = ?
                """,
                values,
            )
            return bool(cursor.rowcount == 1)

    def release(
        self,
        job_id: str,
        owner_id: str,
        reason: str,
        *,
        now: float,
    ) -> bool:
        with unit_of_work(connection=self._connection_provider(), immediate=True) as work:
            cursor = work.connection.execute(
                f"""
                UPDATE {self.table_name}
                SET status = 'pending', attempts = MAX(0, attempts - 1),
                    available_at = ?, last_error = ?, updated_at = ?,
                    lease_owner = NULL, lease_until = NULL
                WHERE id = ? AND status = 'running' AND lease_owner = ?
                """,
                (now, reason[:1000], now, job_id, owner_id),
            )
            return bool(cursor.rowcount == 1)

    def cancel_owned(
        self,
        job_id: str,
        owner_id: str,
        reason: str,
        *,
        now: float,
    ) -> bool:
        with unit_of_work(connection=self._connection_provider(), immediate=True) as work:
            cursor = work.connection.execute(
                f"""
                UPDATE {self.table_name}
                SET status = 'cancelled', completed_at = ?, updated_at = ?,
                    lease_owner = NULL, lease_until = NULL, last_error = ?
                WHERE id = ? AND status = 'running' AND lease_owner = ?
                """,
                (now, now, reason[:1000], job_id, owner_id),
            )
            return bool(cursor.rowcount == 1)

    def fail(
        self,
        job_id: str,
        owner_id: str,
        error: str,
        retry_delay_seconds: float,
        *,
        now: float,
    ) -> str | None:
        with unit_of_work(
            connection=self._connection_provider(),
            immediate=True,
        ) as work:
            connection = work.connection
            row = connection.execute(
                f"""
                SELECT attempts, max_attempts FROM {self.table_name}
                WHERE id = ? AND status = 'running' AND lease_owner = ?
                """,
                (job_id, owner_id),
            ).fetchone()
            if row is None:
                return None
            retrying = row["attempts"] < row["max_attempts"]
            status = "pending" if retrying else "failed"
            cursor = connection.execute(
                f"""
                UPDATE {self.table_name}
                SET status = ?, available_at = ?, last_error = ?, updated_at = ?,
                    completed_at = ?, lease_owner = NULL, lease_until = NULL
                WHERE id = ? AND status = 'running' AND lease_owner = ?
                """,
                (
                    status,
                    now + max(0.0, retry_delay_seconds),
                    error[:1000],
                    now,
                    None if retrying else now,
                    job_id,
                    owner_id,
                ),
            )
            return status if cursor.rowcount == 1 else None

    def retry_failed(
        self,
        job_id: str,
        *,
        now: float,
        filters: Mapping[str, Any] | None = None,
    ) -> bool:
        predicates = ["id = ?", "status = 'failed'"]
        values: list[Any] = [now, now, job_id]
        for column, value in (filters or {}).items():
            predicates.append(f"{_validate_identifier(column)} = ?")
            values.append(value)
        with unit_of_work(connection=self._connection_provider(), immediate=True) as work:
            cursor = work.connection.execute(
                f"""
                UPDATE {self.table_name}
                SET status = 'pending', attempts = 0, available_at = ?,
                    updated_at = ?, lease_owner = NULL, lease_until = NULL,
                    last_error = NULL, completed_at = NULL
                WHERE {' AND '.join(predicates)}
                """,
                values,
            )
            return bool(cursor.rowcount == 1)

    def purge_completed_with_status(
        self,
        retention_seconds: float,
        *,
        now: float,
        batch_size: int = DEFAULT_PURGE_BATCH_SIZE,
        max_batches: int = DEFAULT_PURGE_MAX_BATCHES,
    ) -> PurgeResult:
        placeholders = ", ".join("?" for _ in self._spec.terminal_statuses)
        return purge_rows_in_batches(
            self._connection_provider(),
            table_name=self.table_name,
            predicate_sql=f"""
                status IN ({placeholders})
                AND completed_at IS NOT NULL
                AND completed_at <= ?
            """,
            parameters=(*self._spec.terminal_statuses, now - max(0.0, retention_seconds)),
            order_by="completed_at, rowid",
            batch_size=batch_size,
            max_batches=max_batches,
        )

    def purge_completed(
        self,
        retention_seconds: float,
        *,
        now: float,
        batch_size: int = DEFAULT_PURGE_BATCH_SIZE,
        max_batches: int = DEFAULT_PURGE_MAX_BATCHES,
    ) -> int:
        return int(
            self.purge_completed_with_status(
                retention_seconds,
                now=now,
                batch_size=batch_size,
                max_batches=max_batches,
            ).deleted
        )
