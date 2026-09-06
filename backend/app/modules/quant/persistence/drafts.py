"""在线量化策略草稿仓储。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Literal
from uuid import uuid4

from app.core.exceptions import ResourceNotFoundError
from app.infrastructure.persistence.connection import get_connection

DraftStatus = Literal["draft", "validated", "testing", "backtested", "published"]


@dataclass(frozen=True, slots=True)
class StrategyDraftRow:
    id: str
    created_by: int
    prompt: str
    definition: dict[str, Any]
    definition_hash: str
    status: str
    validation: dict[str, Any] | None
    backtest_run_id: str | None
    quality_gate: dict[str, Any] | None
    published_path: str | None
    last_error: str | None
    created_at: float
    updated_at: float
    published_at: float | None


def _loads(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    payload = json.loads(value)
    return payload if isinstance(payload, dict) else None


def _dumps(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _to_draft(row) -> StrategyDraftRow:
    return StrategyDraftRow(
        id=row["id"],
        created_by=row["created_by"],
        prompt=row["prompt"],
        definition=_loads(row["definition_json"]) or {},
        definition_hash=row["definition_hash"],
        status=row["status"],
        validation=_loads(row["validation_json"]),
        backtest_run_id=row["backtest_run_id"],
        quality_gate=_loads(row["quality_gate_json"]),
        published_path=row["published_path"],
        last_error=row["last_error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        published_at=row["published_at"],
    )


def _require_draft(draft_id: str) -> StrategyDraftRow:
    draft = get_draft(draft_id)
    if draft is None:
        # 有意为之的 404 信号；其余 KeyError(draft_id) 是并发冲突的内部标记，勿改
        raise ResourceNotFoundError(f"量化草稿不存在: {draft_id}")
    return draft


def create_draft(
    *,
    created_by: int,
    prompt: str,
    definition: dict[str, Any],
    definition_hash: str,
    status: DraftStatus = "draft",
    validation: dict[str, Any] | None = None,
    now: float | None = None,
) -> StrategyDraftRow:
    current_time = time.time() if now is None else now
    draft_id = uuid4().hex
    connection = get_connection("user")
    connection.execute(
        """
        INSERT INTO quant_strategy_drafts(
            id, created_by, prompt, definition_json, definition_hash, status,
            validation_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            draft_id,
            created_by,
            prompt,
            _dumps(definition),
            definition_hash,
            status,
            _dumps(validation),
            current_time,
            current_time,
        ),
    )
    connection.commit()
    return _require_draft(draft_id)


def get_draft(draft_id: str) -> StrategyDraftRow | None:
    row = get_connection("user").execute(
        "SELECT * FROM quant_strategy_drafts WHERE id = ?",
        (draft_id,),
    ).fetchone()
    return _to_draft(row) if row is not None else None


def list_drafts(*, limit: int = 100) -> list[StrategyDraftRow]:
    rows = get_connection("user").execute(
        "SELECT * FROM quant_strategy_drafts ORDER BY updated_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_to_draft(row) for row in rows]


def replace_definition(
    draft_id: str,
    definition: dict[str, Any],
    definition_hash: str,
    *,
    expected_definition_hash: str,
    now: float | None = None,
) -> StrategyDraftRow:
    current_time = time.time() if now is None else now
    connection = get_connection("user")
    cursor = connection.execute(
        """
        UPDATE quant_strategy_drafts
        SET definition_json = ?, definition_hash = ?, status = 'draft',
            validation_json = NULL, backtest_run_id = NULL,
            quality_gate_json = NULL, published_path = NULL,
            last_error = NULL, published_at = NULL, updated_at = ?
        WHERE id = ? AND definition_hash = ? AND status IN ('draft', 'validated')
        """,
        (_dumps(definition), definition_hash, current_time, draft_id, expected_definition_hash),
    )
    connection.commit()
    if cursor.rowcount != 1:
        raise KeyError(draft_id)
    return _require_draft(draft_id)


def record_validation(
    draft_id: str,
    validation: dict[str, Any],
    *,
    expected_definition_hash: str,
    now: float | None = None,
) -> StrategyDraftRow:
    current_time = time.time() if now is None else now
    connection = get_connection("user")
    cursor = connection.execute(
        """
        UPDATE quant_strategy_drafts
        SET status = 'validated', validation_json = ?, last_error = NULL, updated_at = ?
        WHERE id = ? AND definition_hash = ? AND status IN ('draft', 'validated')
        """,
        (_dumps(validation), current_time, draft_id, expected_definition_hash),
    )
    connection.commit()
    if cursor.rowcount != 1:
        raise KeyError(draft_id)
    return _require_draft(draft_id)


def record_backtest(
    draft_id: str,
    run_id: str,
    quality_gate: dict[str, Any] | None = None,
    *,
    expected_definition_hash: str,
    now: float | None = None,
) -> StrategyDraftRow:
    current_time = time.time() if now is None else now
    connection = get_connection("user")
    cursor = connection.execute(
        """
        UPDATE quant_strategy_drafts
        SET status = 'testing', backtest_run_id = ?, quality_gate_json = ?,
            last_error = NULL, updated_at = ?
        WHERE id = ? AND definition_hash = ? AND status IN ('validated', 'backtested')
        """,
        (run_id, _dumps(quality_gate), current_time, draft_id, expected_definition_hash),
    )
    connection.commit()
    if cursor.rowcount != 1:
        raise KeyError(draft_id)
    return _require_draft(draft_id)


def record_quality(
    draft_id: str,
    quality_gate: dict[str, Any],
    *,
    expected_definition_hash: str,
    expected_run_id: str,
    status: Literal["validated", "backtested"],
    error: str | None = None,
    now: float | None = None,
) -> StrategyDraftRow:
    current_time = time.time() if now is None else now
    connection = get_connection("user")
    cursor = connection.execute(
        """
        UPDATE quant_strategy_drafts
        SET status = ?, quality_gate_json = ?, last_error = ?, updated_at = ?
        WHERE id = ? AND definition_hash = ? AND backtest_run_id = ? AND status = 'testing'
        """,
        (
            status,
            _dumps(quality_gate),
            error,
            current_time,
            draft_id,
            expected_definition_hash,
            expected_run_id,
        ),
    )
    connection.commit()
    if cursor.rowcount != 1:
        raise KeyError(draft_id)
    return _require_draft(draft_id)


def record_error(
    draft_id: str,
    error: str,
    *,
    expected_definition_hash: str,
    status: Literal["draft", "validated"] = "draft",
    now: float | None = None,
) -> StrategyDraftRow:
    current_time = time.time() if now is None else now
    connection = get_connection("user")
    cursor = connection.execute(
        """
        UPDATE quant_strategy_drafts
        SET status = ?, last_error = ?, updated_at = ?
        WHERE id = ? AND definition_hash = ? AND status IN ('draft', 'validated')
        """,
        (status, error[:1000], current_time, draft_id, expected_definition_hash),
    )
    connection.commit()
    if cursor.rowcount != 1:
        raise KeyError(draft_id)
    return _require_draft(draft_id)


def record_publication(
    draft_id: str,
    published_path: str,
    *,
    expected_definition_hash: str,
    now: float | None = None,
) -> StrategyDraftRow:
    current_time = time.time() if now is None else now
    connection = get_connection("user")
    cursor = connection.execute(
        """
        UPDATE quant_strategy_drafts
        SET status = 'published', published_path = ?, published_at = ?,
            last_error = NULL, updated_at = ?
        WHERE id = ? AND definition_hash = ? AND status = 'backtested'
        """,
        (published_path, current_time, current_time, draft_id, expected_definition_hash),
    )
    connection.commit()
    if cursor.rowcount != 1:
        raise KeyError(draft_id)
    return _require_draft(draft_id)


def delete_draft(draft_id: str) -> bool:
    connection = get_connection("user")
    cursor = connection.execute(
        "DELETE FROM quant_strategy_drafts WHERE id = ? AND status IN ('draft', 'validated')",
        (draft_id,),
    )
    connection.commit()
    return cursor.rowcount == 1
