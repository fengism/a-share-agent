"""进程内指标注册表。"""

from __future__ import annotations

from collections import defaultdict
from threading import Lock

_MAX_PROVIDER_OPERATION_SERIES = 64


def _provider_metrics_entry() -> dict[str, float | int | str | None]:
    return {
        "attempts": 0,
        "successes": 0,
        "failures": 0,
        "fallback_attempts": 0,
        "duration_ms_total": 0.0,
        "duration_ms_max": 0.0,
        "last_error_type": None,
    }


def _provider_metrics_snapshot(entry: dict[str, float | int | str | None]) -> dict:
    attempts = int(entry["attempts"])
    result = {
        **entry,
        "duration_ms_avg": round(float(entry["duration_ms_total"]) / attempts, 2),
        "duration_ms_max": round(float(entry["duration_ms_max"]), 2),
    }
    result.pop("duration_ms_total")
    return result


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: dict[tuple[str, str, int], dict[str, float | int]] = defaultdict(
            lambda: {
                "count": 0,
                "duration_ms_total": 0.0,
                "duration_ms_max": 0.0,
            }
        )
        self._providers: dict[str, dict[str, float | int | str | None]] = defaultdict(_provider_metrics_entry)
        self._provider_operations: dict[
            tuple[str, str],
            dict[str, float | int | str | None],
        ] = defaultdict(_provider_metrics_entry)
        self._caches: dict[str, dict[str, int]] = defaultdict(
            lambda: {
                "hits": 0,
                "misses": 0,
                "evictions": 0,
                "expirations": 0,
                "stale_fallbacks": 0,
                "size": 0,
            }
        )
        self._bot_events: dict[str, int] = defaultdict(int)
        self._bot_commands: dict[str, dict[str, float | int | str | None]] = defaultdict(
            lambda: {
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "duration_ms_total": 0.0,
                "duration_ms_max": 0.0,
                "last_error_type": None,
            }
        )

    def record_request(self, method: str, path: str, status: int, duration_ms: float) -> None:
        with self._lock:
            entry = self._requests[(method, path, status)]
            entry["count"] += 1
            entry["duration_ms_total"] += duration_ms
            entry["duration_ms_max"] = max(entry["duration_ms_max"], duration_ms)

    def record_provider_attempt(
        self,
        provider: str,
        *,
        operation: str | None = None,
        success: bool,
        duration_ms: float,
        fallback: bool = False,
        error_type: str | None = None,
    ) -> None:
        with self._lock:
            entries = [self._providers[provider]]
            if operation:
                operation_key = (provider, operation)
                known_operations = sum(key_provider == provider for key_provider, _ in self._provider_operations)
                if (
                    operation_key not in self._provider_operations
                    and known_operations >= _MAX_PROVIDER_OPERATION_SERIES - 1
                ):
                    operation_key = (provider, "<other>")
                entries.append(self._provider_operations[operation_key])
            for entry in entries:
                entry["attempts"] += 1
                entry["successes" if success else "failures"] += 1
                entry["fallback_attempts"] += int(fallback)
                entry["duration_ms_total"] += duration_ms
                entry["duration_ms_max"] = max(entry["duration_ms_max"], duration_ms)
                if error_type:
                    entry["last_error_type"] = error_type

    def record_cache_event(self, cache_name: str, event: str, *, size: int) -> None:
        event_fields = {
            "hit": "hits",
            "miss": "misses",
            "eviction": "evictions",
            "expiration": "expirations",
            "stale_fallback": "stale_fallbacks",
        }
        with self._lock:
            entry = self._caches[cache_name]
            field = event_fields.get(event)
            if field:
                entry[field] += 1
            entry["size"] = size

    def record_bot_event(self, event: str) -> None:
        with self._lock:
            self._bot_events[event] += 1

    def record_bot_command(
        self,
        command: str,
        *,
        success: bool,
        duration_ms: float,
        error_type: str | None = None,
    ) -> None:
        with self._lock:
            entry = self._bot_commands[command]
            entry["attempts"] += 1
            entry["successes" if success else "failures"] += 1
            entry["duration_ms_total"] += duration_ms
            entry["duration_ms_max"] = max(entry["duration_ms_max"], duration_ms)
            if error_type:
                entry["last_error_type"] = error_type

    def snapshot(self) -> dict:
        with self._lock:
            requests = []
            for (method, path, status), entry in sorted(self._requests.items()):
                count = int(entry["count"])
                requests.append(
                    {
                        "method": method,
                        "path": path,
                        "status": status,
                        "count": count,
                        "duration_ms_avg": round(float(entry["duration_ms_total"]) / count, 2),
                        "duration_ms_max": round(float(entry["duration_ms_max"]), 2),
                    }
                )

            providers = {}
            for provider, entry in sorted(self._providers.items()):
                providers[provider] = _provider_metrics_snapshot(entry)

            provider_operations: dict[str, dict[str, dict]] = {}
            for (provider, operation), entry in sorted(self._provider_operations.items()):
                provider_operations.setdefault(provider, {})[operation] = _provider_metrics_snapshot(entry)

            bot_commands = {}
            for command, entry in sorted(self._bot_commands.items()):
                attempts = int(entry["attempts"])
                bot_commands[command] = {
                    **entry,
                    "duration_ms_avg": round(float(entry["duration_ms_total"]) / attempts, 2),
                    "duration_ms_max": round(float(entry["duration_ms_max"]), 2),
                }
                bot_commands[command].pop("duration_ms_total")

            return {
                "requests": requests,
                "providers": providers,
                "provider_operations": provider_operations,
                "caches": {name: dict(entry) for name, entry in sorted(self._caches.items())},
                "bot": {
                    "events": dict(sorted(self._bot_events.items())),
                    "commands": bot_commands,
                },
            }

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()
            self._providers.clear()
            self._provider_operations.clear()
            self._caches.clear()
            self._bot_events.clear()
            self._bot_commands.clear()


metrics = MetricsRegistry()
