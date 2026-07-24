"""Unit tests for the in-process login throttle.

Time is controlled by monkeypatching login_throttle._now, so lock expiry and
window resets are deterministic (no sleeping). Behaviour was also validated by
direct execution.
"""
import pytest

from app.utils import login_throttle as lt


@pytest.fixture(autouse=True)
def _clean():
    lt._reset_all()
    yield
    lt._reset_all()


def _fixed_clock(monkeypatch):
    t = {"v": 1000.0}
    monkeypatch.setattr(lt, "_now", lambda: t["v"])
    return t


def test_below_threshold_not_locked(monkeypatch):
    _fixed_clock(monkeypatch)
    for _ in range(lt.MAX_FAILURES - 1):
        assert lt.record_failure("k") == 0
    assert lt.retry_after("k") == 0


def test_locks_at_threshold(monkeypatch):
    _fixed_clock(monkeypatch)
    remaining = 0
    for _ in range(lt.MAX_FAILURES):
        remaining = lt.record_failure("k")
    assert remaining > 0
    assert lt.retry_after("k") > 0


def test_reset_clears_lock(monkeypatch):
    _fixed_clock(monkeypatch)
    for _ in range(lt.MAX_FAILURES):
        lt.record_failure("k")
    assert lt.retry_after("k") > 0
    lt.reset("k")
    assert lt.retry_after("k") == 0


def test_lock_expires(monkeypatch):
    t = _fixed_clock(monkeypatch)
    for _ in range(lt.MAX_FAILURES):
        lt.record_failure("k")
    assert lt.retry_after("k") > 0
    t["v"] += lt.LOCK_SECONDS + 1
    assert lt.retry_after("k") == 0


def test_failures_outside_window_do_not_accumulate(monkeypatch):
    t = _fixed_clock(monkeypatch)
    for i in range(lt.MAX_FAILURES + 3):
        lt.record_failure("k")
        t["v"] += lt.WINDOW_SECONDS + 1  # each failure starts a fresh window
        assert lt.retry_after("k") == 0, i


def test_keys_are_independent(monkeypatch):
    _fixed_clock(monkeypatch)
    for _ in range(lt.MAX_FAILURES):
        lt.record_failure("ip:1.2.3.4")
    assert lt.retry_after("ip:1.2.3.4") > 0
    assert lt.retry_after("user:bob") == 0
