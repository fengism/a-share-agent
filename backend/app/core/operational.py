from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

ProviderCircuitStatus = Literal["closed", "open", "half_open_ready", "half_open"]


class ProviderCircuitSnapshot(TypedDict):
    status: ProviderCircuitStatus
    consecutive_failures: int
    retry_in_seconds: float


@dataclass(frozen=True, slots=True)
class OperationalSnapshot:
    metrics: Mapping[str, Any]
    background_tasks: Mapping[str, Mapping[str, Any]]
    workflow_queue: Mapping[str, Any]
    backups: Mapping[str, Mapping[str, Any]]
    global_cache: Mapping[str, int]
    market_cache: Mapping[str, int]
    reference_cache: Mapping[str, int]
    analysis_cache: Mapping[str, int]
    series_cache: Mapping[str, int]
    provider_circuits: Mapping[str, ProviderCircuitSnapshot]


__all__ = ["OperationalSnapshot", "ProviderCircuitSnapshot", "ProviderCircuitStatus"]
