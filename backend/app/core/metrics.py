"""进程内指标注册表。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import Lock

_MAX_PROVIDER_OPERATION_SERIES = 64
# agentic 事件名同时是低基数标签。当前实际取值上界约 45 个固定名
# + tool_called:/skill_core_tool_missed:<tool> 各至多「工具数」个 + skill 级事件，
# 取 512 留出工具增长空间；再涨就该怀疑有动态前缀失控。
_MAX_AGENTIC_EVENT_SERIES = 512
_AGENTIC_EVENT_OVERFLOW = "agentic_event_series_overflow"


@dataclass(slots=True)
class _DurationMetrics:
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    duration_ms_total: float = 0.0
    duration_ms_max: float = 0.0
    last_error_type: str | None = None


@dataclass(slots=True)
class _ProviderMetrics(_DurationMetrics):
    fallback_attempts: int = 0


@dataclass(slots=True)
class _PersistenceMetrics(_DurationMetrics):
    busy_failures: int = 0
    processed_total: int = 0
    last_processed: int = 0
    pending_runs: int = 0
    last_pending: bool = False


@dataclass(slots=True)
class _BrowserFetchMetrics(_DurationMetrics):
    content_characters_total: int = 0
    content_characters_max: int = 0
    queue_wait_ms_total: float = 0.0
    queue_wait_ms_max: float = 0.0


@dataclass(slots=True)
class _LlmMetrics(_DurationMetrics):
    cancellations: int = 0
    prompt_tokens: int = 0
    # 单次最大值：只看总量无法判断是否真有请求撞到上下文上限，
    # 调 chat_max_prompt_characters / completion 预算需要这个分布上界。
    prompt_tokens_max: int = 0
    completion_tokens: int = 0
    completion_tokens_max: int = 0
    queue_wait_ms_total: float = 0.0
    queue_wait_ms_max: float = 0.0
    ttft_ms_total: float = 0.0
    ttft_ms_max: float = 0.0
    ttft_samples: int = 0


def _record_duration_metrics(
    entry: _DurationMetrics,
    *,
    success: bool,
    duration_ms: float,
    error_type: str | None,
) -> None:
    entry.attempts += 1
    if success:
        entry.successes += 1
    else:
        entry.failures += 1
    entry.duration_ms_total += duration_ms
    entry.duration_ms_max = max(entry.duration_ms_max, duration_ms)
    if error_type:
        entry.last_error_type = error_type


def _duration_metrics_snapshot(entry: _DurationMetrics) -> dict:
    return {
        "attempts": entry.attempts,
        "successes": entry.successes,
        "failures": entry.failures,
        "duration_ms_max": round(entry.duration_ms_max, 2),
        "last_error_type": entry.last_error_type,
        "duration_ms_avg": round(entry.duration_ms_total / entry.attempts, 2),
    }


def _provider_metrics_snapshot(entry: _ProviderMetrics) -> dict:
    return {
        **_duration_metrics_snapshot(entry),
        "fallback_attempts": entry.fallback_attempts,
    }


def _persistence_metrics_snapshot(entry: _PersistenceMetrics) -> dict:
    return {
        **_duration_metrics_snapshot(entry),
        "busy_failures": entry.busy_failures,
        "processed_total": entry.processed_total,
        "last_processed": entry.last_processed,
        "pending_runs": entry.pending_runs,
        "last_pending": entry.last_pending,
    }


def _llm_metrics_snapshot(entry: _LlmMetrics) -> dict:
    return {
        **_duration_metrics_snapshot(entry),
        "cancellations": entry.cancellations,
        "prompt_tokens": entry.prompt_tokens,
        "prompt_tokens_max": entry.prompt_tokens_max,
        "completion_tokens": entry.completion_tokens,
        "completion_tokens_max": entry.completion_tokens_max,
        "queue_wait_ms_max": round(entry.queue_wait_ms_max, 2),
        "ttft_ms_max": round(entry.ttft_ms_max, 2),
        "queue_wait_ms_avg": round(entry.queue_wait_ms_total / entry.attempts, 2),
        "ttft_ms_avg": (
            round(entry.ttft_ms_total / entry.ttft_samples, 2)
            if entry.ttft_samples
            else 0.0
        ),
    }


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
        self._providers: dict[str, _ProviderMetrics] = defaultdict(_ProviderMetrics)
        self._provider_operations: dict[tuple[str, str], _ProviderMetrics] = defaultdict(
            _ProviderMetrics
        )
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
        self._bot_commands: dict[str, _DurationMetrics] = defaultdict(_DurationMetrics)
        self._workflow_events: dict[tuple[str, str], int] = defaultdict(int)
        self._workflow_runs: dict[str, _DurationMetrics] = defaultdict(_DurationMetrics)
        self._workflow_active_streams: dict[str, int] = defaultdict(int)
        self._llm_prompts: dict[tuple[str, str], _LlmMetrics] = defaultdict(_LlmMetrics)
        self._agentic_events: dict[str, int] = defaultdict(int)
        self._browser_fetches: dict[str, _BrowserFetchMetrics] = defaultdict(_BrowserFetchMetrics)
        self._persistence_operations: dict[
            tuple[str, str], _PersistenceMetrics
        ] = defaultdict(_PersistenceMetrics)

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
                _record_duration_metrics(
                    entry,
                    success=success,
                    duration_ms=duration_ms,
                    error_type=error_type,
                )
                entry.fallback_attempts += int(fallback)

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
            _record_duration_metrics(
                entry,
                success=success,
                duration_ms=duration_ms,
                error_type=error_type,
            )

    def record_workflow_event(self, kind: str, event: str) -> None:
        with self._lock:
            self._workflow_events[(kind, event)] += 1

    def record_workflow_run(
        self,
        kind: str,
        *,
        success: bool,
        duration_ms: float,
        error_type: str | None = None,
    ) -> None:
        with self._lock:
            entry = self._workflow_runs[kind]
            _record_duration_metrics(
                entry,
                success=success,
                duration_ms=duration_ms,
                error_type=error_type,
            )

    def adjust_workflow_streams(self, kind: str, delta: int) -> None:
        with self._lock:
            self._workflow_active_streams[kind] = max(
                0,
                self._workflow_active_streams[kind] + delta,
            )

    def record_llm_prompt(
        self,
        prompt: str,
        model: str,
        *,
        success: bool,
        duration_ms: float,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        queue_wait_ms: float = 0.0,
        ttft_ms: float | None = None,
        cancelled: bool = False,
        error_type: str | None = None,
    ) -> None:
        with self._lock:
            entry = self._llm_prompts[(prompt, model or "<unknown>")]
            _record_duration_metrics(
                entry,
                success=success,
                duration_ms=duration_ms,
                error_type=error_type,
            )
            if prompt_tokens:
                entry.prompt_tokens += max(0, prompt_tokens)
                entry.prompt_tokens_max = max(entry.prompt_tokens_max, prompt_tokens)
            if completion_tokens:
                entry.completion_tokens += max(0, completion_tokens)
                entry.completion_tokens_max = max(
                    entry.completion_tokens_max, completion_tokens
                )
            entry.queue_wait_ms_total += max(0.0, queue_wait_ms)
            entry.queue_wait_ms_max = max(entry.queue_wait_ms_max, queue_wait_ms)
            if ttft_ms is not None:
                entry.ttft_ms_total += max(0.0, ttft_ms)
                entry.ttft_ms_max = max(entry.ttft_ms_max, ttft_ms)
                entry.ttft_samples += 1
            entry.cancellations += int(cancelled)

    def record_agentic_event(self, event: str) -> None:
        with self._lock:
            # 事件名是低基数标签：一部分带工具/Skill 名（已由 registry 限定），
            # 但任何新接入的动态前缀都不应该能无限撑大内存与 /metrics 体积。
            if (
                event not in self._agentic_events
                and len(self._agentic_events) >= _MAX_AGENTIC_EVENT_SERIES
            ):
                self._agentic_events[_AGENTIC_EVENT_OVERFLOW] += 1
                return
            self._agentic_events[event] += 1

    def record_browser_fetch(
        self,
        mode: str,
        *,
        success: bool,
        duration_ms: float,
        content_characters: int = 0,
        queue_wait_ms: float = 0.0,
        error_type: str | None = None,
    ) -> None:
        with self._lock:
            entry = self._browser_fetches[mode]
            _record_duration_metrics(
                entry,
                success=success,
                duration_ms=duration_ms,
                error_type=error_type,
            )
            characters = max(0, content_characters)
            entry.content_characters_total += characters
            entry.content_characters_max = max(entry.content_characters_max, characters)
            entry.queue_wait_ms_total += max(0.0, queue_wait_ms)
            entry.queue_wait_ms_max = max(entry.queue_wait_ms_max, queue_wait_ms)

    def record_persistence_operation(
        self,
        database: str,
        operation: str,
        *,
        success: bool,
        duration_ms: float,
        busy: bool = False,
        processed: int = 0,
        pending: bool = False,
        error_type: str | None = None,
    ) -> None:
        with self._lock:
            entry = self._persistence_operations[(database, operation)]
            _record_duration_metrics(
                entry,
                success=success,
                duration_ms=duration_ms,
                error_type=error_type,
            )
            entry.busy_failures += int(busy)
            entry.processed_total += max(0, processed)
            entry.last_processed = max(0, processed)
            entry.pending_runs += int(pending)
            entry.last_pending = pending

    def snapshot(self) -> dict:
        with self._lock:
            requests = []
            for (method, path, status), request_entry in sorted(self._requests.items()):
                count = int(request_entry["count"])
                requests.append(
                    {
                        "method": method,
                        "path": path,
                        "status": status,
                        "count": count,
                        "duration_ms_avg": round(float(request_entry["duration_ms_total"]) / count, 2),
                        "duration_ms_max": round(float(request_entry["duration_ms_max"]), 2),
                    }
                )

            providers = {}
            for provider, provider_entry in sorted(self._providers.items()):
                providers[provider] = _provider_metrics_snapshot(provider_entry)

            provider_operations: dict[str, dict[str, dict]] = {}
            for (provider, operation), operation_entry in sorted(self._provider_operations.items()):
                provider_operations.setdefault(provider, {})[operation] = _provider_metrics_snapshot(operation_entry)

            bot_commands = {}
            for command, command_entry in sorted(self._bot_commands.items()):
                bot_commands[command] = _duration_metrics_snapshot(command_entry)

            workflow_events: dict[str, dict[str, int]] = {}
            for (kind, event), count in sorted(self._workflow_events.items()):
                workflow_events.setdefault(kind, {})[event] = count
            workflow_runs = {
                kind: _duration_metrics_snapshot(run_entry)
                for kind, run_entry in sorted(self._workflow_runs.items())
            }
            llm_prompts: dict[str, dict[str, dict]] = {}
            for (prompt, model), prompt_entry in sorted(self._llm_prompts.items()):
                llm_prompts.setdefault(prompt, {})[model] = _llm_metrics_snapshot(prompt_entry)

            browser_fetches = {
                mode: {
                    **_duration_metrics_snapshot(entry),
                    "content_characters_max": entry.content_characters_max,
                    "content_characters_avg": round(entry.content_characters_total / entry.attempts, 2),
                    "queue_wait_ms_max": round(entry.queue_wait_ms_max, 2),
                    "queue_wait_ms_avg": round(entry.queue_wait_ms_total / entry.attempts, 2),
                }
                for mode, entry in sorted(self._browser_fetches.items())
            }

            persistence_operations: dict[str, dict[str, dict]] = {}
            for (database, operation), persistence_entry in sorted(self._persistence_operations.items()):
                persistence_operations.setdefault(database, {})[operation] = (
                    _persistence_metrics_snapshot(persistence_entry)
                )

            return {
                "requests": requests,
                "providers": providers,
                "provider_operations": provider_operations,
                "caches": {name: dict(entry) for name, entry in sorted(self._caches.items())},
                "bot": {
                    "events": dict(sorted(self._bot_events.items())),
                    "commands": bot_commands,
                },
                "workflow": {
                    "events": workflow_events,
                    "runs": workflow_runs,
                    "active_streams": dict(sorted(self._workflow_active_streams.items())),
                },
                "llm": {"prompts": llm_prompts},
                "agentic": {
                    "events": dict(sorted(self._agentic_events.items())),
                    "browser_fetches": browser_fetches,
                },
                "persistence": {"operations": persistence_operations},
            }

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()
            self._providers.clear()
            self._provider_operations.clear()
            self._caches.clear()
            self._bot_events.clear()
            self._bot_commands.clear()
            self._workflow_events.clear()
            self._workflow_runs.clear()
            self._workflow_active_streams.clear()
            self._llm_prompts.clear()
            self._agentic_events.clear()
            self._browser_fetches.clear()
            self._persistence_operations.clear()


metrics = MetricsRegistry()
