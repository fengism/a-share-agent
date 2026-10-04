"""正常关机标记：控制启动时是否执行全库 SQLite 完整性检查。

背景：market_daily 库可达 12GiB，``PRAGMA quick_check`` 是全量扫描，启动时
无条件执行要数小时。但损坏只可能来自非正常退出（崩溃/断电/kill -9）；正常关机
会在退出时留下标记，此时重查没有意义。因此"有标记则跳过、无标记则全查"。
"""

from pathlib import Path

from app.infrastructure.persistence import operations


def test_no_marker_means_verify_runs() -> None:
    """崩溃/首次启动：无标记，必须执行全量检查。"""
    assert operations.consume_clean_shutdown_marker() is False


def test_clean_shutdown_marker_is_consumed_once(tmp_path, monkeypatch) -> None:
    """正常关机重启：首次跳过检查，且标记被消费，下次启动仍会检查。"""
    marker = tmp_path / ".clean_shutdown"
    monkeypatch.setattr(operations, "_clean_shutdown_marker_path", lambda: marker)

    operations.mark_clean_shutdown()
    assert marker.is_file(), "正常关机应留下标记"

    assert operations.consume_clean_shutdown_marker() is True, "有标记时应跳过检查"
    assert not marker.exists(), "标记应被消费掉，避免永久信任"

    assert operations.consume_clean_shutdown_marker() is False, "标记已消费，下次启动应恢复检查"


def test_marker_lives_next_to_databases() -> None:
    """标记必须落在数据库目录，容器重建重新挂载卷后判断才依然有效。"""
    from app.infrastructure.persistence.connection import DB_DIR

    assert operations._clean_shutdown_marker_path().parent == Path(DB_DIR)


def test_lifecycle_checks_small_and_probes_large(tmp_path, monkeypatch) -> None:
    """崩溃恢复：启动路径对小库做 fail-fast 全检，对大库做轻量探针检查。"""
    from app.runtime import lifecycle

    marker = tmp_path / ".clean_shutdown"
    monkeypatch.setattr(operations, "_clean_shutdown_marker_path", lambda: marker)

    checked_critical: list[tuple[str, ...]] = []
    probed_large: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        operations,
        "verify_startup_critical_databases",
        lambda **_kw: checked_critical.append(operations.STARTUP_CRITICAL_DATABASES),
    )
    monkeypatch.setattr(
        operations,
        "verify_startup_large_databases",
        lambda **_kw: probed_large.append(operations.STARTUP_LARGE_DATABASES),
    )

    lifecycle.verify_database_integrity()
    assert checked_critical == [("market", "user", "industry")], "应检查三个小库"
    assert probed_large == [("market_daily",)], "应探针检查大库"


def test_lifecycle_skips_all_on_clean_shutdown(tmp_path, monkeypatch) -> None:
    """正常关机：跳过所有小库与大库的启动检查。"""
    from app.runtime import lifecycle

    marker = tmp_path / ".clean_shutdown"
    marker.write_text("2026-10-04T00:00:00Z", encoding="utf-8")
    monkeypatch.setattr(operations, "_clean_shutdown_marker_path", lambda: marker)

    called: list[str] = []
    monkeypatch.setattr(
        operations,
        "verify_startup_critical_databases",
        lambda **_kw: called.append("critical"),
    )
    monkeypatch.setattr(
        operations,
        "verify_startup_large_databases",
        lambda **_kw: called.append("large"),
    )

    lifecycle.verify_database_integrity()
    assert called == [], "正常关机后应跳过所有检查"


def test_startup_check_excludes_rebuildable_large_database_from_full_quick_check() -> None:
    """market_daily 是可从 dump 重建的派生数据，不应出现在全量 quick_check 里。

    它的全量 quick_check 需数小时（冷缓存单流约 49 MiB/s，CPU 约 3%），
    因此不放入 STARTUP_CRITICAL_DATABASES，而是由 STARTUP_LARGE_DATABASES
    执行毫秒级轻量探针检查。
    """
    assert "market_daily" not in operations.STARTUP_CRITICAL_DATABASES
    assert set(operations.STARTUP_CRITICAL_DATABASES) == {"market", "user", "industry"}
    assert operations.STARTUP_LARGE_DATABASES == ("market_daily",)


def test_deferred_database_check_is_gone() -> None:
    """大库后台检查已移除——不存在延迟检查入口，也不再注册后台任务。"""
    assert not hasattr(operations, "STARTUP_DEFERRED_DATABASES")
    assert not hasattr(operations, "verify_deferred_databases")

    from app.runtime import lifecycle

    assert not hasattr(lifecycle, "verify_deferred_database_integrity")
    spec_source = __import__("inspect").getsource(lifecycle.build_background_task_specs)
    assert "deferred_integrity_check" not in spec_source


def test_probe_large_database_integrity_on_empty_and_populated_db() -> None:
    """大表探针在空库与有数据的库上均可正常毫秒级完成。"""
    import sqlite3

    # 空库
    conn_empty = sqlite3.connect(":memory:")
    operations.probe_large_database_integrity(conn_empty, label="empty_test")

    # 构建带元数据小表与大表及索引的库
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE market_daily_schema_migrations (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO market_daily_schema_migrations VALUES (1)")
    conn.execute(
        "CREATE TABLE market_daily_bars (code TEXT, trade_date TEXT, close REAL, PRIMARY KEY (code, trade_date))"
    )
    conn.execute("CREATE INDEX idx_market_daily_bars_date ON market_daily_bars(trade_date)")
    conn.execute("INSERT INTO market_daily_bars VALUES ('000001', '2026-10-02', 15.5)")
    conn.commit()

    operations.probe_large_database_integrity(conn, label="populated_test")


def test_probe_large_database_catches_corruption(tmp_path) -> None:
    """大表探针在数据库损坏时应抛出 RuntimeError。"""
    import sqlite3

    import pytest

    db_file = tmp_path / "corrupt_test.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE market_daily_bars (id INTEGER PRIMARY KEY, content TEXT)")
    for i in range(100):
        conn.execute("INSERT INTO market_daily_bars VALUES (?, ?)", (i, "x" * 200))
    conn.commit()
    conn.close()

    # 破坏第 2 页
    with db_file.open("r+b") as f:
        f.seek(4096)
        f.write(b"\xff" * 500)

    corrupt_conn = sqlite3.connect(db_file)
    try:
        with pytest.raises(RuntimeError, match="探针"):
            operations.probe_large_database_integrity(corrupt_conn, label="corrupt_test")
    finally:
        corrupt_conn.close()
