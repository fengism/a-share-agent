from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

WorkflowKind = Literal["analysis", "industry_chain", "screener_strategy", "daily_review"]
WorkflowStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]


@dataclass(frozen=True, slots=True)
class WorkflowJobSnapshot:
    id: str
    kind: WorkflowKind
    user_id: int
    dedupe_key: str
    request: dict[str, Any]
    status: WorkflowStatus
    attempts: int
    max_attempts: int
    available_at: float
    last_error: str | None
    created_at: float
    updated_at: float
    completed_at: float | None


@dataclass(frozen=True, slots=True)
class WorkflowSubmissionSnapshot:
    job: WorkflowJobSnapshot
    attached: bool


class WorkflowRequestConflictError(RuntimeError):
    """An active deduplicated workflow has incompatible request semantics."""


class WorkflowCapacityError(RuntimeError):
    def __init__(self, scope: Literal["user", "global"], limit: int) -> None:
        super().__init__(f"Workflow capacity reached: scope={scope} limit={limit}")
        self.scope = scope
        self.limit = limit


class WorkflowExecutionError(RuntimeError):
    def __init__(self, message: str, *, cancelled: bool = False) -> None:
        super().__init__(message)
        self.cancelled = cancelled


__all__ = [
    "WorkflowCapacityError",
    "WorkflowExecutionError",
    "WorkflowJobSnapshot",
    "WorkflowKind",
    "WorkflowRequestConflictError",
    "WorkflowStatus",
    "WorkflowSubmissionSnapshot",
]
