"""正常关机标记：控制启动时是否执行全库 SQLite 完整性检查。

背景：market_daily 库可达 12GiB，``PRAGMA quick_check`` 是全量扫描，启动时
无条件执行要数小时。但损坏只可能来自非正常退出（崩溃/断电/kill -9）；正常关机
会在退出时留下标记，此时重查没有意义。因此"有标记则跳过、无标记则全查"。
"""

from pathlib import Path

from app.infrastructure.persistence import operations
from app.infrastructure.persistence.connection import ALL_DATABASES


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


def test_lifecycle_skips_everything_after_clean_shutdown(tmp_path, monkeypatch) -> None:
    """上次正常关机：启动检查与后台大库检查都跳过。"""
    import asyncio

    from app.runtime import lifecycle

    marker = tmp_path / ".clean_shutdown"
    marker.write_text("2026-10-04T00:00:00+00:00", encoding="utf-8")
    monkeypatch.setattr(operations, "_clean_shutdown_marker_path", lambda: marker)

    critical_called = False
    deferred_called = False

    def _fail_critical(**_kwargs) -> None:
        nonlocal critical_called
        critical_called = True

    def _fail_deferred(**_kwargs) -> None:
        nonlocal deferred_called
        deferred_called = True

    monkeypatch.setattr(
        "app.infrastructure.persistence.operations.verify_startup_critical_databases", _fail_critical,
    )
    monkeypatch.setattr(
        "app.infrastructure.persistence.operations.verify_deferred_databases", _fail_deferred,
    )

    lifecycle.verify_database_integrity()
    asyncio.run(lifecycle.verify_deferred_database_integrity())
    assert critical_called is False, "正常关机后不应检查小库"
    assert deferred_called is False, "正常关机后不应白跑数小时检查大库"


def test_lifecycle_checks_only_small_libs_synchronously(tmp_path, monkeypatch) -> None:
    """崩溃恢复：启动路径只查小库，大库交给后台。"""
    import asyncio

    from app.runtime import lifecycle

    marker = tmp_path / ".clean_shutdown"
    monkeypatch.setattr(operations, "_clean_shutdown_marker_path", lambda: marker)

    checked: list[str] = []
    monkeypatch.setattr(
        operations, "verify_startup_critical_databases", lambda **_kw: checked.append("small"),
    )
    monkeypatch.setattr(
        operations, "verify_deferred_databases", lambda **_kw: checked.append("big"),
    )

    lifecycle.verify_database_integrity()
    # 启动关键路径此刻只能有 small，big 必须还没开始
    assert checked == ["small"], f"启动路径不应同步检查大库，实际={checked}"

    asyncio.run(lifecycle.verify_deferred_database_integrity())
    assert checked == ["small", "big"], "大库应在后台阶段检查"


def test_startup_and_deferred_partition_all_databases() -> None:
    """分层必须覆盖全部库且不重叠，否则某个库会永远不被检查。"""
    assert set(operations.STARTUP_CRITICAL_DATABASES) | set(operations.STARTUP_DEFERRED_DATABASES) == set(
        ALL_DATABASES
    )
    assert not set(operations.STARTUP_CRITICAL_DATABASES) & set(operations.STARTUP_DEFERRED_DATABASES)
    # market_daily 必须落在延迟侧——它才是那个 12.94 GiB 的大库
    assert "market_daily" in operations.STARTUP_DEFERRED_DATABASES
    assert "market_daily" not in operations.STARTUP_CRITICAL_DATABASES


def test_deferred_check_failure_does_not_raise(monkeypatch) -> None:
    """后台检查失败只记日志，不得把已经启动的服务带崩。"""
    import asyncio

    from app.runtime import lifecycle

    monkeypatch.setattr(lifecycle, "_last_exit_was_clean", False)

    def _boom(**_kwargs) -> None:
        raise RuntimeError("SQLite 完整性检查失败: database=market_daily")

    monkeypatch.setattr(operations, "verify_deferred_databases", _boom)
    # 不应抛异常
    asyncio.run(lifecycle.verify_deferred_database_integrity())