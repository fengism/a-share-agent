import concurrent.futures
import sqlite3
from unittest.mock import patch

import pytest

from app.infrastructure.persistence import init_db, task_lease_store
from app.infrastructure.persistence.connection import get_connection, reset_for_tests
from app.infrastructure.persistence.task_leader import TaskLeaderLease


@pytest.fixture(scope="session", autouse=True)
def _schema_ready():
    """会话级建表一次。

    reset_for_tests() 只关连接并重置迁移标记，不会建表；CI 上数据库是全新的，
    必须先跑一次 init_db() 让表结构存在，否则会报 "no such table"。
    建表本身很快（~0.4s），但对每个用例都跑会拖慢整轮，故只在会话开始时执行一次。
    """
    reset_for_tests()
    init_db()
    yield


@pytest.fixture(autouse=True)
def _clean_database():
    reset_for_tests()
    yield
    reset_for_tests()


def test_acquire_renew_and_release_task_lease():
    task_name = "test_task_single"
    owner_1 = "worker_1"
    owner_2 = "worker_2"

    # Acquire by owner_1
    assert task_lease_store.acquire_task_lease(task_name, owner_1, lease_seconds=10.0, now=1000.0) is True

    # Renew by owner_1
    assert task_lease_store.renew_task_lease(task_name, owner_1, lease_seconds=15.0, now=1005.0) is True

    # Owner_2 cannot acquire while owner_1's lease is active
    assert task_lease_store.acquire_task_lease(task_name, owner_2, lease_seconds=10.0, now=1005.0) is False

    # Owner_2 can acquire once expired (now=1025.0 > 1005.0 + 15.0)
    assert task_lease_store.acquire_task_lease(task_name, owner_2, lease_seconds=10.0, now=1025.0) is True

    # Release by owner_2
    assert task_lease_store.release_task_lease(task_name, owner_2) is True

    # After release, owner_1 can acquire immediately
    assert task_lease_store.acquire_task_lease(task_name, owner_1, lease_seconds=10.0, now=1026.0) is True


def test_purge_expired_task_leases():
    task_lease_store.acquire_task_lease("task_expire_1", "worker_1", lease_seconds=5.0, now=1000.0)
    task_lease_store.acquire_task_lease("task_expire_2", "worker_1", lease_seconds=20.0, now=1000.0)

    # At now=1010.0, task_expire_1 is expired, task_expire_2 is still valid
    deleted = task_lease_store.purge_expired_task_leases(now=1010.0)
    assert deleted == 1

    # Verify task_expire_2 remains
    conn = get_connection("market")
    row = conn.execute("SELECT task_name FROM background_task_leases WHERE task_name = 'task_expire_2'").fetchone()
    assert row is not None


def test_concurrent_release_leases():
    """Simulate multiple background tasks releasing their leases simultaneously on shutdown."""
    task_names = [f"shutdown_task_{i}" for i in range(12)]
    for name in task_names:
        assert task_lease_store.acquire_task_lease(name, f"owner_{name}", lease_seconds=30.0) is True

    def release_worker(name: str):
        return task_lease_store.release_task_lease(name, f"owner_{name}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(release_worker, task_names))

    assert all(results)

    conn = get_connection("market")
    remaining = conn.execute(
        f"SELECT COUNT(*) FROM background_task_leases WHERE task_name IN ({','.join('?' for _ in task_names)})",
        task_names,
    ).fetchone()[0]
    assert remaining == 0


@pytest.mark.asyncio
async def test_task_leader_lease_lifecycle():
    lease = TaskLeaderLease("lifecycle_task", "node_1", lease_seconds=5.0)
    acquired = await lease.try_acquire()
    assert acquired is True
    assert lease.lost is False

    # Closing lease cancels heartbeat and releases lease
    await lease.close()
    assert lease.lost is False


@pytest.mark.asyncio
async def test_task_leader_lease_close_graceful_on_locked_database():
    lease = TaskLeaderLease("locked_task", "node_1", lease_seconds=5.0)
    acquired = await lease.try_acquire()
    assert acquired is True

    # Simulate database is locked during shutdown release
    locked_error = sqlite3.OperationalError("database is locked")
    with patch("app.infrastructure.persistence.task_lease_store.release_task_lease", side_effect=locked_error):
        # Should handle gracefully without raising exception
        await lease.close()


def test_orphaned_transaction_recovery():
    """Verify that a dirty uncommitted transaction on the connection is automatically rolled back on next uow."""
    from app.infrastructure.persistence.connection import unit_of_work

    conn = get_connection("market")
    # Simulate an orphaned raw transaction left behind by an unhandled thread exception
    conn.execute("BEGIN")
    conn.execute("INSERT OR REPLACE INTO background_task_leases(task_name, owner_id, lease_until, updated_at) VALUES ('dirty', 'bad', 9999, 9999)")
    assert conn.in_transaction is True

    # Entering a new unit of work should detect depth==0 and in_transaction==True, rolling it back
    with unit_of_work("market", immediate=True) as uow:
        uow.connection.execute("INSERT OR REPLACE INTO background_task_leases(task_name, owner_id, lease_until, updated_at) VALUES ('clean', 'good', 8888, 8888)")

    # Verify 'clean' exists and 'dirty' was rolled back
    row_dirty = conn.execute("SELECT * FROM background_task_leases WHERE task_name = 'dirty'").fetchone()
    row_clean = conn.execute("SELECT * FROM background_task_leases WHERE task_name = 'clean'").fetchone()
    assert row_dirty is None
    assert row_clean is not None


def test_user_config_and_account_store_with_uow():
    """Verify account and user config store operations with unit_of_work."""
    import time

    from app.infrastructure.persistence import account_store, user_config_store

    uname = f"test_uow_{time.time_ns()}"
    user = account_store.create_user(uname, "password123", is_admin=False)
    assert user["username"] == uname

    account_store.set_user_role(user["id"], is_admin=True)
    updated_user = account_store.get_user_by_id(user["id"])
    assert updated_user["is_admin"] == 1

    user_config_store.set_user_config(user["id"], {"theme": "dark", "locale": "zh-CN"})
    config = user_config_store.get_user_config(user["id"])
    assert config.get("theme") == "dark"
    assert config.get("locale") == "zh-CN"

    deleted = account_store.delete_user(user["id"])
    assert deleted is True
    assert account_store.get_user_by_id(user["id"]) is None


def test_invite_store_with_uow():
    """Verify invite_store functions run cleanly with unit_of_work."""
    import time

    from app.infrastructure.persistence import invite_store

    code = f"INV_{time.time_ns()}"
    invite = invite_store.create_invite(1, code, expires_at=None)
    assert invite["code"] == code
    assert invite_store.invite_is_valid(code) is True

    revoked = invite_store.revoke_invite(code)
    assert revoked == "revoked"
    assert invite_store.invite_is_valid(code) is False
