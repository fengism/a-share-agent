"""市场日行情连接复用与复权因子健康缓存的测试。

背景：
- 此前每个仓库方法都新建 SQLite 连接（一次盘中 K 线读取约 7 个连接）。
  改为线程本地复用后，必须保证作用域的提交/回滚语义与逐方法新建时一致。
- ensure_adjustment_factors 此前每次读取都做 4 次 DB 点查；新增进程内健康缓存后，
  健康态应跳过点查，force / 失效必须绕过或清除缓存。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

import app.modules.market_daily.adjustment as adjustment
from app.modules.market_daily.repository import (
    MarketDailyBarRepository,
    close_all_connections,
)


@pytest.fixture(autouse=True)
def _cleanup_connections():
    yield
    close_all_connections()


def test_connection_is_reused_per_thread(tmp_path: Path) -> None:
    repo = MarketDailyBarRepository(path=tmp_path / "reuse.sqlite3")
    repo.initialize()
    assert repo._connection() is repo._connection()


def test_connection_scope_commits_on_success(tmp_path: Path) -> None:
    repo = MarketDailyBarRepository(path=tmp_path / "commit.sqlite3")
    repo.initialize()
    with repo._connect() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS t(x INTEGER)")
        connection.execute("INSERT INTO t VALUES (1)")
    # 新作用域应能看到上一个作用域已提交的数据
    with repo._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1


def test_connection_scope_rolls_back_on_error(tmp_path: Path) -> None:
    repo = MarketDailyBarRepository(path=tmp_path / "rollback.sqlite3")
    repo.initialize()
    with repo._connect() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS t(x INTEGER)")
        connection.execute("INSERT INTO t VALUES (1)")
    with pytest.raises(RuntimeError):
        with repo._connect() as connection:
            connection.execute("INSERT INTO t VALUES (2)")
            raise RuntimeError("boom")
    with repo._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1


def test_initialize_is_idempotent(tmp_path: Path) -> None:
    repo = MarketDailyBarRepository(path=tmp_path / "init.sqlite3")
    repo.initialize()
    repo.initialize()  # 第二次应为空操作，不报错也不重复建表


class _FakeFactorRepository:
    def __init__(self, trading_dates: list, state: dict) -> None:
        self._trading_dates = trading_dates
        self._state = state
        self.calls = 0

    def initialize(self) -> None:
        self.calls += 1

    def list_stock_dates(self, code: str):
        self.calls += 1
        return self._trading_dates

    def get_factor_state(self, code: str):
        self.calls += 1
        return self._state

    def list_adjustment_factor_dates(self, code: str):
        self.calls += 1
        return self._trading_dates

    def mark_factor_check(self, code: str, now, *, error: str | None = None, using_last_good: bool = False):
        self.calls += 1
        return None


def _healthy_state(count: int) -> dict:
    return {
        "algorithm_version": adjustment.ALGORITHM_VERSION,
        "factor_count": count,
        "last_checked_at": datetime.now(UTC).isoformat(),
        "last_error": None,
        "using_last_good": 0,
    }


@pytest.mark.asyncio
async def test_healthy_cache_skips_repository_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    adjustment._healthy_cache.clear()
    dates = [datetime(2026, 9, 29).date(), datetime(2026, 9, 30).date()]
    fake = _FakeFactorRepository(dates, _healthy_state(len(dates)))
    monkeypatch.setattr(adjustment, "_repository", fake)

    assert await adjustment.ensure_adjustment_factors("600519") is True
    assert fake.calls > 0
    fake.calls = 0
    # 第二次：健康缓存命中，跳过所有点查
    assert await adjustment.ensure_adjustment_factors("600519") is True
    assert fake.calls == 0


@pytest.mark.asyncio
async def test_force_bypasses_healthy_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    adjustment._healthy_cache.clear()
    dates = [datetime(2026, 9, 29).date(), datetime(2026, 9, 30).date()]
    fake = _FakeFactorRepository(dates, _healthy_state(len(dates)))
    # force 时会走向上游；这里让上游失败但保留 last-good，从而仍返回 True
    monkeypatch.setattr(adjustment, "_repository", fake)

    def _boom(*args, **kwargs):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(adjustment, "call_blocking", _boom)
    monkeypatch.setattr(adjustment, "get_provider", lambda name: object())

    assert await adjustment.ensure_adjustment_factors("600519") is True
    fake.calls = 0
    assert await adjustment.ensure_adjustment_factors("600519", force=True) is True
    # force 必须重新查询仓库，不能被健康缓存短路
    assert fake.calls > 0


@pytest.mark.asyncio
async def test_invalidate_clears_healthy_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    adjustment._healthy_cache.clear()
    adjustment._healthy_cache_set("600519", 0.0)
    assert "600519" in adjustment._healthy_cache

    async def _noop(*args, **kwargs):
        return None

    class _Repo:
        def initialize(self):
            return None

        def invalidate_adjustment_factors(self, code, market="cn"):
            return (0, 0)

        def get_adjustment_summary(self, code, market="cn"):
            return {}

    monkeypatch.setattr(adjustment, "_repository", _Repo())

    await adjustment.invalidate_adjustment_factors("600519")
    assert "600519" not in adjustment._healthy_cache


def test_clear_adjustment_health_cache_empties_module_cache() -> None:
    """库结构修复路径（日行情库 v2 迁移）依赖这个入口丢弃旧的「已确认健康」结论。

    此前由 app.core.cache 反向 import 本模块的私有字典来清空；改为对外暴露入口后，
    core 不再依赖业务模块，本用例锁定该入口确实会清空缓存。
    """
    adjustment._healthy_cache.clear()
    adjustment._healthy_cache_set("600519", 0.0)
    adjustment._healthy_cache_set("000001", 0.0)
    assert len(adjustment._healthy_cache) == 2

    adjustment.clear_adjustment_health_cache()

    assert adjustment._healthy_cache == {}


def test_canonical_adjustment_anchor_matches_internal_constant() -> None:
    """对账脚本改用公开访问器后，取值必须与内部常量一致。"""
    assert adjustment.canonical_adjustment_anchor() == adjustment._CANONICAL_ANCHOR
