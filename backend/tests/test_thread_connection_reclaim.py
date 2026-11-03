"""线程退出时自动回收线程本地 SQLite 连接。

背景：项目有 10+ 处 provider 用 ``with ThreadPoolExecutor(...)`` 包住并发抓取，
worker 线程用完即销毁。线程本地连接原本只登记在全局注册表里，线程死了也没人
再能关闭它们，于是每调用一次就泄漏一个连接（``connection.py`` 每个连接还带
8 MB 页缓存）。``sqlite3.Connection`` 不支持 weakref，也没有线程退出回调，
因此改用「只被 threading.local 引用的持有者对象」承载连接：CPython 在线程结束
时清空该线程的 local 数据，从而释放持有者并触发 ``__del__`` 完成关闭 + 注销。
"""

from __future__ import annotations

import gc
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.infrastructure.persistence import connection as shared_connection
from app.modules.market_daily import repository as market_daily_repository
from app.modules.market_daily.repository import MarketDailyBarRepository


def _settle() -> None:
    """给解释器一点时间跑完线程收尾与 GC。"""
    for _ in range(3):
        gc.collect()
        time.sleep(0.02)


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """把共享连接层的库目录指向 tmp_path，避免污染真实数据。"""
    monkeypatch.setattr(shared_connection, "DB_DIR", tmp_path / "db")
    monkeypatch.setattr(shared_connection, "_ensure_database_storage_migrated", lambda: None)
    yield
    shared_connection.close_connection()
    market_daily_repository.close_all_connections()


def _run_in_short_lived_pool(work, *, rounds: int = 5, workers: int = 4) -> None:
    for _ in range(rounds):
        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(work, range(workers)))
        _settle()


def test_shared_connections_are_reclaimed_when_pool_threads_die() -> None:
    def work(_: int) -> None:
        shared_connection.get_connection("market").execute("SELECT 1").fetchone()

    work(0)
    baseline = len(shared_connection._all_connections)

    _run_in_short_lived_pool(work)
    _settle()

    # 修复前会累积到 baseline + 20。
    assert len(shared_connection._all_connections) <= baseline


def test_reclaimed_shared_connections_are_actually_closed() -> None:
    opened: list[object] = []

    def work(_: int) -> None:
        opened.append(shared_connection.get_connection("market"))

    work(0)
    _run_in_short_lived_pool(work)
    _settle()

    # 注册表里只剩主线程那一个，其余应已真正 close（再用会抛 ProgrammingError）。
    leaked = [conn for conn in opened if id(conn) in shared_connection._all_connections]
    assert len(leaked) == 1


def test_market_daily_connections_are_reclaimed_when_pool_threads_die(tmp_path: Path) -> None:
    database = tmp_path / "reclaim.sqlite3"
    MarketDailyBarRepository(path=database).initialize()

    def work(_: int) -> None:
        MarketDailyBarRepository(path=database)._connection().execute("SELECT 1").fetchone()

    work(0)
    baseline = len(market_daily_repository._open_connections)

    _run_in_short_lived_pool(work)
    _settle()

    assert len(market_daily_repository._open_connections) <= baseline


def test_close_all_connections_still_works_after_bundle_reclaim(tmp_path: Path) -> None:
    """回收后再走显式关闭路径不能因注册表变化而报错。"""
    database = tmp_path / "explicit.sqlite3"
    repo = MarketDailyBarRepository(path=database)
    repo.initialize()

    def work(_: int) -> None:
        MarketDailyBarRepository(path=database)._connection().execute("SELECT 1").fetchone()

    _run_in_short_lived_pool(work)
    _settle()

    market_daily_repository.close_all_connections()
    assert market_daily_repository._open_connections == {}

    # 关闭后仍能重新建立可用连接。
    repo._connection().execute("SELECT 1").fetchone()
