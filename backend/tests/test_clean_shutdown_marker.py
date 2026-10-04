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


def test_lifecycle_skips_verify_after_clean_shutdown(tmp_path, monkeypatch) -> None:
    """lifecycle 默认实现在有标记时不会调用底层全量检查。"""
    from app.runtime import lifecycle

    marker = tmp_path / ".clean_shutdown"
    marker.write_text("2026-10-04T00:00:00+00:00", encoding="utf-8")
    monkeypatch.setattr(operations, "_clean_shutdown_marker_path", lambda: marker)

    called = False

    def _fail() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(
        "app.infrastructure.persistence.operations.verify_database_integrity", _fail,
    )
    lifecycle.verify_database_integrity()
    assert called is False, "正常关机后不应触发全库 quick_check"


def test_lifecycle_verifies_when_no_marker(tmp_path, monkeypatch) -> None:
    """无标记（非正常退出）时 lifecycle 仍会执行全量检查。"""
    from app.runtime import lifecycle

    marker = tmp_path / ".clean_shutdown"
    monkeypatch.setattr(operations, "_clean_shutdown_marker_path", lambda: marker)

    called = False

    def _spy() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(
        "app.infrastructure.persistence.operations.verify_database_integrity", _spy,
    )
    lifecycle.verify_database_integrity()
    assert called is True, "崩溃恢复后必须做完整性检查"