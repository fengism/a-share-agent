"""In-memory login throttle — a brute-force speed bump.

After too many *consecutive* failed attempts for a given key (we key logins by
both username and client IP), the key is locked for a short cool-down. A
successful login clears the key. State lives in-process (no DB round-trip on the
hot path) and resets on restart, which is acceptable for slowing password
guessing. Thresholds are tunable via environment variables.

Not a substitute for a network-edge rate limiter in a multi-process deployment
(each worker keeps its own counters); it raises the cost of guessing without new
infrastructure.
"""
from __future__ import annotations

import os
import threading
import time

MAX_FAILURES = int(os.getenv("LOGIN_MAX_FAILURES", "5"))       # failures before lockout
WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "300"))  # rolling window for counting
LOCK_SECONDS = int(os.getenv("LOGIN_LOCK_SECONDS", "300"))      # cool-down once locked

_lock = threading.Lock()
# key -> {"fails": int, "first": float, "until": float}
_state: dict[str, dict] = {}


def _now() -> float:
    # monotonic: immune to wall-clock changes (all comparisons are durations)
    return time.monotonic()


def _remaining(entry: dict, now: float) -> int:
    left = entry["until"] - now
    return int(left) + 1 if left > 0 else 0


def retry_after(key: str) -> int:
    """Seconds remaining on the lock for key, or 0 if not locked."""
    with _lock:
        entry = _state.get(key)
        return _remaining(entry, _now()) if entry else 0


def record_failure(key: str) -> int:
    """Record a failed attempt for key.

    Returns the remaining lock seconds if this failure triggered/continues a
    lockout, else 0. Counting resets when the window elapses since the first
    failure and the key is not currently locked.
    """
    with _lock:
        now = _now()
        entry = _state.get(key)
        if entry is None or (now - entry["first"] > WINDOW_SECONDS and entry["until"] <= now):
            entry = {"fails": 0, "first": now, "until": 0.0}
        entry["fails"] += 1
        if entry["fails"] >= MAX_FAILURES:
            entry["until"] = now + LOCK_SECONDS
        _state[key] = entry
        return _remaining(entry, now)


def reset(key: str) -> None:
    """Clear a key's failure/lock state (called on successful login)."""
    with _lock:
        _state.pop(key, None)


def _reset_all() -> None:
    """Test helper: wipe all throttle state."""
    with _lock:
        _state.clear()
