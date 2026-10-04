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


def test_lifecycle_checks_only_small_libs(tmp_path, monkeypatch) -> None:
    """崩溃恢复：启动路径只查小库，且不触碰 12.94 GiB 的market_daily。"""
    from app.runtime import lifecycle

    marker = tmp_path / ".clean_shutdown"
    monkeypatch.setattr(operations, "_clean_shutdown_marker_path", lambda: marker)

    checked: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        operations,
        "verify_startup_critical_databases",
        lambda **_kw: checked.append(operations.STARTUP_CRITICAL_DATABASES),
    )

    lifecycle.verify_database_integrity()
    assert checked == [("market", "user", "industry")], "应只检查三个小库"


def test_startup_check_excludes_rebuildable_large_database() -> None:
    """market_daily 是可从 dump 重建的派生数据，不应出现在启动检查里。

    它的全量 quick_check 需数小时（冷缓存单流约 49 MiB/s，CPU 约 3%），
    期间挤占K 线拉取与 WAL 维护，且检查本身不能自愈。
    """
    assert "market_daily" not in operations.STARTUP_CRITICAL_DATABASES
    # 只查用户数据与元数据这类不可重建的库
    assert set(operations.STARTUP_CRITICAL_DATABASES) == {"market", "user", "industry"}


def test_deferred_database_check_is_gone() -> None:
    """大库后台检查已移除——不存在延迟检查入口，也不再注册后台任务。"""
    assert not hasattr(operations, "STARTUP_DEFERRED_DATABASES")
    assert not hasattr(operations, "verify_deferred_databases")

    from app.runtime import lifecycle

    assert not hasattr(lifecycle, "verify_deferred_database_integrity")
    spec_source = __import__("inspect").getsource(lifecycle.build_background_task_specs)
    assert "deferred_integrity_check" not in spec_source
