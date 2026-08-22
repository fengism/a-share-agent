"""Prometheus text rendering for bounded in-process operational metrics."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

_METRIC_TOKEN = re.compile(r"[^a-zA-Z0-9_:]")


def _escape_label(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _metric_name(value: str) -> str:
    return _METRIC_TOKEN.sub("_", value)


def _sample(name: str, value: int | float | bool, **labels: object) -> str:
    label_text = ""
    if labels:
        rendered = ",".join(f'{key}="{_escape_label(label)}"' for key, label in sorted(labels.items()))
        label_text = f"{{{rendered}}}"
    if isinstance(value, bool):
        numeric = "1" if value else "0"
    else:
        number = float(value)
        numeric = "0" if not math.isfinite(number) else format(number, ".15g")
    return f"{_metric_name(name)}{label_text} {numeric}"


def render_prometheus_metrics(
    snapshot: Mapping[str, Any],
    *,
    background_tasks: Mapping[str, Mapping[str, Any]],
    workflow_queue: Mapping[str, Any],
    backups: Mapping[str, Mapping[str, Any]],
) -> str:
    lines = [
        "# TYPE a_share_http_requests_total counter",
    ]
    for request in snapshot.get("requests", []):
        labels = {
            "method": request.get("method", ""),
            "path": request.get("path", ""),
            "status": request.get("status", ""),
        }
        lines.append(_sample("a_share_http_requests_total", request.get("count", 0), **labels))
        lines.append(_sample("a_share_http_request_duration_milliseconds_avg", request.get("duration_ms_avg", 0), **labels))
        lines.append(_sample("a_share_http_request_duration_milliseconds_max", request.get("duration_ms_max", 0), **labels))

    for provider, values in snapshot.get("providers", {}).items():
        for field in ("attempts", "successes", "failures", "fallback_attempts"):
            lines.append(_sample(f"a_share_provider_{field}_total", values.get(field, 0), provider=provider))

    for prompt, models in snapshot.get("llm", {}).get("prompts", {}).items():
        for model, values in models.items():
            labels = {"prompt": prompt, "model": model}
            for field in (
                "attempts", "successes", "failures", "cancellations",
                "prompt_tokens", "completion_tokens",
            ):
                lines.append(
                    _sample(f"a_share_llm_{field}_total", values.get(field, 0), **labels)
                )
            for field in (
                "duration_ms_avg", "duration_ms_max", "queue_wait_ms_avg",
                "queue_wait_ms_max", "ttft_ms_avg", "ttft_ms_max",
            ):
                lines.append(_sample(f"a_share_llm_{field}", values.get(field, 0), **labels))

    for event, count in snapshot.get("agentic", {}).get("events", {}).items():
        lines.append(_sample("a_share_agentic_events_total", count, event=event))

    for mode, values in snapshot.get("agentic", {}).get("browser_fetches", {}).items():
        labels = {"mode": mode}
        for field in ("attempts", "successes", "failures"):
            lines.append(
                _sample(f"a_share_browser_fetch_{field}_total", values.get(field, 0), **labels)
            )
        for field in (
            "duration_ms_avg",
            "duration_ms_max",
            "content_characters_avg",
            "content_characters_max",
            "queue_wait_ms_avg",
            "queue_wait_ms_max",
        ):
            lines.append(_sample(f"a_share_browser_fetch_{field}", values.get(field, 0), **labels))

    workflow = snapshot.get("workflow", {})
    for kind, events in workflow.get("events", {}).items():
        for event, count in events.items():
            lines.append(_sample("a_share_workflow_events_total", count, kind=kind, event=event))
    for kind, values in workflow.get("runs", {}).items():
        for field in ("attempts", "successes", "failures"):
            lines.append(_sample(f"a_share_workflow_runs_{field}_total", values.get(field, 0), kind=kind))
    for kind, count in workflow.get("active_streams", {}).items():
        lines.append(_sample("a_share_workflow_active_streams", count, kind=kind))

    for status in ("pending", "running"):
        lines.append(_sample("a_share_workflow_queue_jobs", workflow_queue.get(status, 0), status=status))
    lines.append(_sample("a_share_workflow_queue_oldest_age_seconds", workflow_queue.get("oldest_age_seconds", 0)))
    lines.append(
        _sample(
            "a_share_workflow_queue_oldest_lease_age_seconds",
            workflow_queue.get("oldest_lease_age_seconds", 0),
        )
    )

    for task_name, task in sorted(background_tasks.items()):
        labels = {"task": task_name}
        lines.append(_sample("a_share_background_task_restarts_total", task.get("restart_count", 0), **labels))
        lines.append(_sample("a_share_background_task_consecutive_restarts", task.get("consecutive_restarts", 0), **labels))
        lines.append(_sample("a_share_background_task_consecutive_errors", task.get("consecutive_errors", 0), **labels))
        lines.append(_sample("a_share_background_task_unexpected_exit", task.get("unexpected_exit", False), **labels))

    for database, backup in sorted(backups.items()):
        labels = {"database": database}
        lines.append(_sample("a_share_database_backup_exists", backup.get("exists", False), **labels))
        lines.append(_sample("a_share_database_backup_checksum_exists", backup.get("checksum_exists", False), **labels))
        if backup.get("age_seconds") is not None:
            lines.append(_sample("a_share_database_backup_age_seconds", backup["age_seconds"], **labels))

    persistence = snapshot.get("persistence", {})
    for database, storage in sorted(persistence.get("databases", {}).items()):
        labels = {"database": database}
        for field in (
            "file_bytes",
            "wal_bytes",
            "shm_bytes",
            "page_count",
            "page_size",
            "freelist_count",
            "freelist_bytes",
            "freelist_ratio",
        ):
            lines.append(_sample(f"a_share_database_{field}", storage.get(field, 0), **labels))

    for database, operations in sorted(persistence.get("operations", {}).items()):
        for operation, values in sorted(operations.items()):
            labels = {"database": database, "operation": operation}
            for field in ("attempts", "successes", "failures", "busy_failures"):
                lines.append(
                    _sample(
                        f"a_share_persistence_operation_{field}_total",
                        values.get(field, 0),
                        **labels,
                    )
                )
            lines.append(
                _sample(
                    "a_share_persistence_operation_processed_total",
                    values.get("processed_total", 0),
                    **labels,
                )
            )
            lines.append(
                _sample(
                    "a_share_persistence_operation_last_pending",
                    values.get("last_pending", False),
                    **labels,
                )
            )
            lines.append(
                _sample(
                    "a_share_persistence_operation_duration_milliseconds_avg",
                    values.get("duration_ms_avg", 0),
                    **labels,
                )
            )
            lines.append(
                _sample(
                    "a_share_persistence_operation_duration_milliseconds_max",
                    values.get("duration_ms_max", 0),
                    **labels,
                )
            )

    for kind, history_index in sorted(persistence.get("history_indexes", {}).items()):
        labels = {"kind": kind}
        lines.append(_sample("a_share_history_index_ready", history_index.get("ready", False), **labels))
        lines.append(_sample("a_share_history_index_dirty", history_index.get("dirty", False), **labels))
        lines.append(
            _sample(
                "a_share_history_index_indexed_in_process",
                history_index.get("indexed_in_process", False),
                **labels,
            )
        )

    return "\n".join(lines) + "\n"


__all__ = ["render_prometheus_metrics"]
