from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock

from app.infrastructure.providers.provider_policy import ProviderCircuitOpenError


@dataclass
class CircuitState:
    consecutive_failures: int = 0
    opened_at: float | None = None
    half_open_in_flight: bool = False


class ProviderCircuitBreaker:
    def __init__(self) -> None:
        self.lock = Lock()
        self.circuits: dict[tuple[str, str], CircuitState] = {}

    def before_call(self, key: tuple[str, str], open_seconds: float, now: float) -> bool:
        with self.lock:
            state = self.circuits.setdefault(key, CircuitState())
            if state.opened_at is None:
                return False
            if now - state.opened_at < open_seconds or state.half_open_in_flight:
                provider, operation = key
                raise ProviderCircuitOpenError(f"provider circuit is open: {provider}.{operation}")
            state.half_open_in_flight = True
            return True

    def record_success(self, key: tuple[str, str]) -> None:
        with self.lock:
            self.circuits[key] = CircuitState()

    def record_failure(
        self,
        key: tuple[str, str],
        *,
        retryable: bool,
        threshold: int,
        half_open: bool,
        clock: Callable[[], float],
    ) -> None:
        with self.lock:
            state = self.circuits.setdefault(key, CircuitState())
            state.half_open_in_flight = False
            if not retryable:
                self.circuits[key] = CircuitState()
                return
            state.consecutive_failures = threshold if half_open else state.consecutive_failures + 1
            if state.consecutive_failures >= threshold:
                state.opened_at = clock()

    def release_half_open(self, key: tuple[str, str]) -> None:
        with self.lock:
            state = self.circuits.get(key)
            if state is not None:
                state.half_open_in_flight = False

    def snapshot(self, open_seconds: float, now: float) -> dict[str, dict]:
        with self.lock:
            result = {}
            for (provider, operation), state in sorted(self.circuits.items()):
                status = "closed"
                retry_in_seconds = 0.0
                if state.opened_at is not None:
                    elapsed = now - state.opened_at
                    if state.half_open_in_flight:
                        status = "half_open"
                    elif elapsed >= open_seconds:
                        status = "half_open_ready"
                    else:
                        status = "open"
                        retry_in_seconds = round(open_seconds - elapsed, 2)
                result[f"{provider}:{operation}"] = {
                    "status": status,
                    "consecutive_failures": state.consecutive_failures,
                    "retry_in_seconds": retry_in_seconds,
                }
            return result

    def reset(self) -> None:
        with self.lock:
            self.circuits.clear()
