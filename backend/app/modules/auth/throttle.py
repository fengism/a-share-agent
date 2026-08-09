"""In-memory login throttle — a brute-force speed bump.

After too many *consecutive* failed attempts for a given key (we key logins by
both username and client IP), the key is locked for a short cool-down. A
successful login clears the key. State lives in-process (no DB round-trip on the
hot path) and resets on restart, which is acceptable for slowing password
guessing.

Thresholds come from application Settings (``login_max_failures`` /
``login_window_seconds`` / ``login_lock_seconds``), loaded from ``.env`` via
pydantic-settings, so dev and Docker read them the same way. The Settings import
is lazy (inside ``_cfg``) to keep this module import-light and easy to unit-test.

Not a substitute for a network-edge rate limiter in a multi-process deployment
(each worker keeps its own counters); it raises the cost of guessing without new
infrastructure.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict

_lock = threading.Lock()
_MAX_STATE_KEYS = 10_000
# key -> {"fails": int, "first": float, "until": float}
_state: OrderedDict[str, dict] = OrderedDict()


def _now() -> float:
    # monotonic: immune to wall-clock changes (all comparisons are durations)
    return time.monotonic()


def _cfg() -> tuple[int, int, int]:
    """(max_failures, window_seconds, lock_seconds) from Settings."""
    from app.configuration import get_settings

    s = get_settings()
    return s.login_max_failures, s.login_window_seconds, s.login_lock_seconds


def _remaining(entry: dict, now: float) -> int:
    left = entry["until"] - now
    return int(left) + 1 if left > 0 else 0


def retry_after(key: str) -> int:
    """Seconds remaining on the lock for key, or 0 if not locked."""
    with _lock:
        entry = _state.get(key)
        if entry is None:
            return 0
        now = _now()
        remaining = _remaining(entry, now)
        if remaining == 0:
            _, window_seconds, _ = _cfg()
            if now - entry["first"] > window_seconds:
                _state.pop(key, None)
        return remaining


def record_failure(key: str) -> int:
    """Record a failed attempt for key.

    Returns the remaining lock seconds if this failure triggered/continues a
    lockout, else 0. Counting resets when the window elapses since the first
    failure and the key is not currently locked.
    """
    max_failures, window_seconds, lock_seconds = _cfg()
    with _lock:
        now = _now()
        entry = _state.get(key)
        if entry is None or (now - entry["first"] > window_seconds and entry["until"] <= now):
            entry = {"fails": 0, "first": now, "until": 0.0}
        entry["fails"] += 1
        if entry["fails"] >= max_failures:
            entry["until"] = now + lock_seconds
        _state[key] = entry
        _state.move_to_end(key)
        while len(_state) > max(1, _MAX_STATE_KEYS):
            _state.popitem(last=False)
        return _remaining(entry, now)


def reset(key: str) -> None:
    """Clear a key's failure/lock state (called on successful login)."""
    with _lock:
        _state.pop(key, None)


def _reset_all() -> None:
    """Test helper: wipe all throttle state."""
    with _lock:
        _state.clear()
