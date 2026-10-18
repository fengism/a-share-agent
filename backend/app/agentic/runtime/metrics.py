"""Metrics port for the agent runtime.

The host installs its metrics registry at composition time. The default is a
no-op so the core package can run standalone in tests or as an extracted module.
"""

from __future__ import annotations

from typing import Protocol


class AgentMetrics(Protocol):
    def record_agentic_event(self, event: str) -> None: ...


class _NullMetrics:
    def record_agentic_event(self, event: str) -> None:
        return None


class _MetricsProxy:
    def __init__(self) -> None:
        self._target: AgentMetrics = _NullMetrics()

    def record_agentic_event(self, event: str) -> None:
        self._target.record_agentic_event(event)

    def configure(self, target: AgentMetrics) -> None:
        self._target = target


metrics = _MetricsProxy()


def configure_metrics(target: AgentMetrics) -> None:
    metrics.configure(target)


__all__ = ["AgentMetrics", "configure_metrics", "metrics"]
