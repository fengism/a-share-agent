"""账号域时间戳必须与 market_now() 一致，不受进程 TZ 影响（P4）。

背景：``users`` / ``auth_sessions`` / ``invites`` / ``login_audit_logs`` 等表的
``created_at`` 原本依赖 DDL 里的 ``datetime('now','localtime')``。容器里
``TZ=Asia/Shanghai`` 时没问题，但裸机/k8s 未设 TZ 时会写 UTC，与业务时间戳
（``market_now()``，北京时间）相差 8 小时——「用户管理」里的注册时间就会显示错。

这里把进程时区强制改成 UTC 后写入记录，断言落库值仍是北京时间。
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta

import pytest

from app.domain.timezones import market_now


@pytest.fixture()
def utc_process_timezone():
    """把进程时区临时改成 UTC（模拟未设 TZ 的裸机/k8s）。"""
    original = getattr(time, "tzname", None)
    import os

    previous = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        time.tzset()
        assert original is None or isinstance(original, tuple)


def _parse(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _assert_market_time(value: str, *, tolerance_seconds: int = 120) -> None:
    recorded = _parse(value)
    expected = market_now()
    assert abs(recorded - expected) < timedelta(seconds=tolerance_seconds), (
        f"落库时间 {recorded} 与北京时间 {expected} 相差过大"
    )


def test_user_created_at_uses_market_time_under_utc_process(utc_process_timezone) -> None:
    from app.infrastructure.persistence import account_store

    user = account_store.create_user(f"tz_{uuid.uuid4().hex[:8]}", "Password123!")
    stored = account_store.get_user_by_id(user["id"])
    assert stored is not None
    _assert_market_time(str(stored["created_at"]))


def test_session_and_login_audit_use_market_time_under_utc_process(utc_process_timezone) -> None:
    from app.infrastructure.persistence import account_store, session_store

    user = account_store.create_user(f"tz_sess_{uuid.uuid4().hex[:8]}", "Password123!")
    token = session_store.create_session(user["id"], ip_address="127.0.0.1", user_agent="tz-test")
    sessions = session_store.list_user_sessions(user["id"], current_token=token)
    _assert_market_time(str(sessions[0]["created_at"]))

    account_store.record_login_audit(
        user["username"], user["id"], "127.0.0.1", "tz-test", "success"
    )
    logs, _ = account_store.list_login_audit_logs(
        limit=5, offset=0, username=user["username"]
    )
    _assert_market_time(str(logs[0]["created_at"]))


def test_invite_and_reset_timestamps_use_market_time_under_utc_process(
    utc_process_timezone,
) -> None:
    from app.infrastructure.persistence import account_store, invite_store

    admin = account_store.create_user(f"tz_admin_{uuid.uuid4().hex[:8]}", "Password123!", is_admin=True)
    invite = invite_store.create_invite(admin["id"], f"TZINV{uuid.uuid4().hex[:6].upper()}")
    _assert_market_time(str(invite["created_at"]))

    invite_store.create_password_reset(
        admin["id"], admin["id"], f"token-{uuid.uuid4().hex}", "2099-01-01 00:00:00"
    )
    from app.infrastructure.persistence.connection import get_connection

    row = get_connection("user").execute(
        "SELECT created_at FROM password_resets WHERE user_id = ? ORDER BY rowid DESC LIMIT 1",
        (admin["id"],),
    ).fetchone()
    assert row is not None
    _assert_market_time(str(row["created_at"]))
