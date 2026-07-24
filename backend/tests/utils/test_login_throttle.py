"""Unit tests for the in-process login throttle.

Thresholds (``_cfg``) and time (``_now``) are monkeypatched so lockout, expiry
and window-reset behaviour are deterministic — no pydantic settings and no
sleeping. Behaviour was also validated by direct execution.
"""
import pytest

from app.utils import login_throttle as lt

MAX, WINDOW, LOCK = 3, 300, 300


@pytest.fixture(autouse=True)
def _fixed_limits(monkeypatch):
    lt._reset_all()
    monkeypatch.setattr(lt, "_cfg", lambda: (MAX, WINDOW, LOCK))
    yield
    lt._reset_all()


def _clock(monkeypatch):
    t = {"v": 1000.0}
    monkeypatch.setattr(lt, "_now", lambda: t["v"])
    return t


def test_below_threshold_not_locked(monkeypatch):
    _clock(monkeypatch)
    for _ in range(MAX - 1):
        assert lt.record_failure("k") == 0
    assert lt.retry_after("k") == 0


def test_locks_at_threshold(monkeypatch):
    _clock(monkeypatch)
    remaining = 0
    for _ in range(MAX):
        remaining = lt.record_failure("k")
    assert remaining > 0
    assert lt.retry_after("k") > 0


def test_reset_clears_lock(monkeypatch):
    _clock(monkeypatch)
    for _ in range(MAX):
        lt.record_failure("k")
    assert lt.retry_after("k") > 0
    lt.reset("k")
    assert lt.retry_after("k") == 0


def test_lock_expires(monkeypatch):
    t = _clock(monkeypatch)
    for _ in range(MAX):
        lt.record_failure("k")
    assert lt.retry_after("k") > 0
    t["v"] += LOCK + 1
    assert lt.retry_after("k") == 0


def test_failures_outside_window_do_not_accumulate(monkeypatch):
    t = _clock(monkeypatch)
    for i in range(MAX + 3):
        lt.record_failure("k")
        t["v"] += WINDOW + 1  # each failure starts a fresh window
        assert lt.retry_after("k") == 0, i


def test_keys_are_independent(monkeypatch):
    _clock(monkeypatch)
    for _ in range(MAX):
        lt.record_failure("ip:1.2.3.4")
    assert lt.retry_after("ip:1.2.3.4") > 0
    assert lt.retry_after("user:bob") == 0


def test_threshold_comes_from_settings(monkeypatch):
    """_cfg wires to Settings; overriding it changes the lockout threshold."""
    _clock(monkeypatch)
    monkeypatch.setattr(lt, "_cfg", lambda: (2, WINDOW, LOCK))
    assert lt.record_failure("k") == 0  # 1st failure
    assert lt.record_failure("k") > 0   # 2nd hits the patched max of 2
