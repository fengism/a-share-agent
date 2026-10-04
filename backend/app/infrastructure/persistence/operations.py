"""SQLite 完整性检查与在线备份运维。"""

from __future__ import annotations

import gzip
import hashlib
import os
import shutil
import sqlite3
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path

from app.infrastructure.persistence.connection import ALL_DATABASES, DB_DIR, DatabaseName, get_connection
from app.infrastructure.persistence.json_storage import atomic_write_text, durable_replace, durable_unlink

ConnectionProvider = Callable[[DatabaseName], sqlite3.Connection]


def _clean_shutdown_marker_path() -> Path:
    """正常关机标记的存放位置。

    必须与数据库同目录：容器重建会重新挂载 data 卷，放到临时目录会让"上次正常
    关机"的判断在重启后失效，导致每次都退回全量 quick_check。
    """
    return Path(DB_DIR) / ".clean_shutdown"


def mark_clean_shutdown() -> None:
    """记录本次进程是正常关闭的。"""
    atomic_write_text(_clean_shutdown_marker_path(), datetime.now(UTC).isoformat())


def consume_clean_shutdown_marker() -> bool:
    """若存在正常关机标记则消费掉并返回 True。

    语义：正常关机后重启不需要全库 quick_check——损坏只可能来自非正常退出
    （崩溃、断电、kill -9），这时标记不存在（或陈旧）才付全量检查的成本。
    读取后立即删除，使下一次启动仍会检查，避免"检查过一次就永久信任"。
    """
    marker = _clean_shutdown_marker_path()
    if not marker.is_file():
        return False
    try:
        durable_unlink(marker)
    except OSError:
        # 删除失败时仍返回 True：本次启动跳过检查，下一次启动若标记仍在会再跳过一次，
        # 优于每次都卡在数小时的 quick_check 上。
        return True
    return True


def _quick_check(connection: sqlite3.Connection, *, label: str) -> None:
    rows = connection.execute("PRAGMA quick_check").fetchall()
    messages = [str(row[0]) for row in rows]
    if messages != ["ok"]:
        raise RuntimeError(f"SQLite 完整性检查失败: database={label} result={messages}")


def verify_database_integrity(
    databases: Iterable[DatabaseName] = ALL_DATABASES,
    *,
    connection_provider: ConnectionProvider = get_connection,
) -> None:
    for database in databases:
        _quick_check(connection_provider(database), label=database)


# 启动时同步做完整性检查的库：三个小库合计约 10 MiB，秒级完成，可以放心
# fail-fast——库坏了就直接拒绝启动。
STARTUP_CRITICAL_DATABASES: tuple[DatabaseName, ...] = ("market", "user", "industry")

# 启动时不做同步检查的大库。market_daily 实测 12.94 GiB，``quick_check`` 是
# 全量扫描，瓶颈在磁盘带宽（冷缓存单流约 49 MiB/s，全扫需数小时），且 CPU 仅
# 占用约 3%——把它放在 uvicorn 监听端口之前串行 await，会让端口迟迟不开、
# healthcheck 必然 refused。实测 mmap 与多线程并行都无法提升带宽上限
# （顺序读与 quick_check 同为约 530 MiB/s，2 线程仅 +12%），因此改为后台检查：
# 服务立即可用，检查在后台跑完并记录结果。
STARTUP_DEFERRED_DATABASES: tuple[DatabaseName, ...] = ("market_daily",)


def verify_startup_critical_databases(
    *,
    connection_provider: ConnectionProvider = get_connection,
) -> None:
    """启动关键路径的完整性检查：只查小库，失败即拒绝启动。"""
    verify_database_integrity(STARTUP_CRITICAL_DATABASES, connection_provider=connection_provider)


def verify_deferred_databases(
    *,
    connection_provider: ConnectionProvider = get_connection,
) -> None:
    """后台完整性检查：只查大库；失败只记日志，不影响已启动的服务。"""
    verify_database_integrity(STARTUP_DEFERRED_DATABASES, connection_provider=connection_provider)


def _verify_backup(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        _quick_check(connection, label=str(path))
    finally:
        connection.close()


def _checksum_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.sha256")


def _file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_checksum(path: Path, *, content_path: Path | None = None) -> Path:
    checksum = _checksum_path(path)
    atomic_write_text(
        checksum,
        f"{_file_checksum(content_path or path)}  {path.name}\n",
    )
    return checksum


def _verify_checksum(path: Path) -> None:
    checksum = _checksum_path(path)
    if not checksum.exists():
        return
    expected = checksum.read_text(encoding="utf-8").split(maxsplit=1)[0]
    actual = _file_checksum(path)
    if not expected or actual != expected:
        raise RuntimeError(f"SQLite 备份校验和不匹配: path={path}")


def _list_backups(backup_dir: Path, database: str) -> list[Path]:
    if not backup_dir.is_dir():
        return []
    backups = [
        *backup_dir.glob(f"{database}-*.sqlite3"),
        *backup_dir.glob(f"{database}-*.sqlite3.gz"),
    ]
    return [path for path in backups if path.is_file()]


def _prune_backups(backup_dir: Path, database: str, retention_count: int) -> None:
    backups = sorted(
        _list_backups(backup_dir, database),
        key=lambda path: (_backup_created_at(path), path.name),
        reverse=True,
    )
    for expired in backups[max(1, retention_count):]:
        durable_unlink(expired)
        durable_unlink(_checksum_path(expired))


def _cleanup_incomplete_backups(backup_dir: Path, database: str) -> None:
    for pattern in (
        f"{database}-*.sqlite3.tmp",
        f"{database}-*.sqlite3.gz.tmp",
        f".{database}-*.sqlite3.tmp",
        f".{database}-*.sqlite3.gz.*.tmp",
    ):
        for temporary in backup_dir.glob(pattern):
            durable_unlink(temporary)
    for checksum in backup_dir.glob(f"{database}-*.sqlite3*.sha256"):
        backup = checksum.with_name(checksum.name.removesuffix(".sha256"))
        if not backup.is_file():
            durable_unlink(checksum)


def _backup_created_at(path: Path) -> float:
    name = path.name
    for suffix in (".sqlite3.gz", ".sqlite3"):
        if name.endswith(suffix):
            name = name.removesuffix(suffix)
            break
    timestamp = name.rsplit("-", maxsplit=1)[-1]
    try:
        return datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC).timestamp()
    except ValueError:
        return path.stat().st_mtime


def backup_freshness_snapshot(
    backup_dir: Path,
    *,
    databases: Iterable[DatabaseName] = ALL_DATABASES,
    now: datetime | None = None,
) -> dict[str, dict[str, float | bool | str | None]]:
    reference_time = (now or datetime.now(UTC)).astimezone(UTC).timestamp()
    snapshot: dict[str, dict[str, float | bool | str | None]] = {}
    for database in databases:
        backups = _list_backups(backup_dir, database)
        if not backups:
            snapshot[database] = {
                "exists": False,
                "age_seconds": None,
                "checksum_exists": False,
                "latest_file": None,
            }
            continue
        latest = max(backups, key=_backup_created_at)
        snapshot[database] = {
            "exists": True,
            "age_seconds": max(0.0, reference_time - _backup_created_at(latest)),
            "checksum_exists": _checksum_path(latest).is_file(),
            "latest_file": latest.name,
        }
    return snapshot


def backup_databases_due(
    backup_dir: Path,
    *,
    interval_seconds: int,
    databases: Iterable[DatabaseName] = ALL_DATABASES,
    now: datetime | None = None,
) -> tuple[DatabaseName, ...]:
    """返回缺失、缺校验和或已经超过备份周期的数据库。"""
    selected = tuple(databases)
    snapshot = backup_freshness_snapshot(backup_dir, databases=selected, now=now)
    return tuple(
        database
        for database in selected
        if not snapshot[database]["exists"]
        or not snapshot[database]["checksum_exists"]
        or float(snapshot[database]["age_seconds"] or 0) >= interval_seconds
    )


def _compress_sqlite(source: Path, destination: Path, *, compresslevel: int = 9) -> None:
    durable_unlink(destination)
    try:
        with source.open("rb") as raw_source, destination.open("wb") as raw_destination:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                compresslevel=compresslevel,
                fileobj=raw_destination,
                mtime=0,
            ) as compressed:
                shutil.copyfileobj(raw_source, compressed, length=1024 * 1024)
            raw_destination.flush()
            os.fsync(raw_destination.fileno())
        os.chmod(destination, 0o600)
    except Exception:
        durable_unlink(destination)
        raise


def _decompress_sqlite(source: Path, destination: Path) -> None:
    durable_unlink(destination)
    try:
        with gzip.open(source, "rb") as compressed, destination.open("wb") as raw:
            shutil.copyfileobj(compressed, raw, length=1024 * 1024)
            raw.flush()
            os.fsync(raw.fileno())
        os.chmod(destination, 0o600)
    except Exception as error:
        durable_unlink(destination)
        raise RuntimeError(f"SQLite gzip 备份解压失败: path={source}") from error


def _verify_compressed_backup(path: Path) -> None:
    """流式读完整个 gzip 包以校验 header、CRC 和未压缩长度。"""
    try:
        with gzip.open(path, "rb") as compressed:
            for _chunk in iter(lambda: compressed.read(1024 * 1024), b""):
                pass
    except Exception as error:
        raise RuntimeError(f"SQLite gzip 备份校验失败: path={path}") from error


def _verify_backup_artifact(path: Path) -> None:
    if path.name.endswith(".sqlite3.gz"):
        _verify_compressed_backup(path)
    else:
        _verify_backup(path)


def _publish_compressed_backup(
    sqlite_temporary: Path,
    destination: Path,
    *,
    compresslevel: int = 9,
) -> None:
    _verify_backup(sqlite_temporary)
    compressed_temporary = destination.with_name(f".{destination.name}.compress.tmp")
    checksum_path = _checksum_path(destination)
    if destination.exists() or checksum_path.exists():
        raise FileExistsError(destination)
    try:
        _compress_sqlite(sqlite_temporary, compressed_temporary, compresslevel=compresslevel)
        _verify_compressed_backup(compressed_temporary)
        checksum = _write_checksum(destination, content_path=compressed_temporary)
        try:
            durable_replace(compressed_temporary, destination)
        except Exception:
            durable_unlink(destination)
            durable_unlink(checksum)
            raise
    finally:
        durable_unlink(compressed_temporary)


def _publish_verified_backup(temporary: Path, destination: Path) -> None:
    _verify_backup(temporary)
    os.chmod(temporary, 0o600)
    checksum_path = _checksum_path(destination)
    if destination.exists() or checksum_path.exists():
        raise FileExistsError(destination)
    checksum = _write_checksum(destination, content_path=temporary)
    try:
        durable_replace(temporary, destination)
    except Exception:
        try:
            durable_unlink(destination)
        finally:
            durable_unlink(checksum)
        raise


def _copy_verified_backup(source: Path, destination: Path) -> None:
    temporary = destination.with_name(f".{destination.name}.copy.tmp")
    durable_unlink(temporary)
    _verify_checksum(source)
    _verify_backup_artifact(source)
    checksum_path = _checksum_path(destination)
    if destination.exists() or checksum_path.exists():
        raise FileExistsError(destination)
    try:
        shutil.copy2(source, temporary)
        os.chmod(temporary, 0o600)
        checksum = _write_checksum(destination, content_path=temporary)
        try:
            durable_replace(temporary, destination)
        except Exception:
            durable_unlink(destination)
            durable_unlink(checksum)
            raise
    finally:
        durable_unlink(temporary)


def _database_file_group(path: Path) -> tuple[Path, Path, Path]:
    return (
        path,
        path.with_name(f"{path.name}-wal"),
        path.with_name(f"{path.name}-shm"),
    )


def _copy_file_durable(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    temporary = destination.with_name(f".{destination.name}.copy.tmp")
    durable_unlink(temporary)
    try:
        shutil.copy2(source, temporary)
        os.chmod(temporary, 0o600)
        durable_replace(temporary, destination)
    except Exception:
        try:
            durable_unlink(temporary)
        finally:
            durable_unlink(destination)
        raise


def _create_safety_file_group(
    destination: Path,
    safety_copy: Path,
) -> dict[Path, Path]:
    safety_files: dict[Path, Path] = {}
    try:
        for source in _database_file_group(destination):
            if not source.is_file():
                continue
            suffix = source.name.removeprefix(destination.name)
            target = safety_copy.with_name(f"{safety_copy.name}{suffix}")
            _copy_file_durable(source, target)
            safety_files[source] = target
    except Exception:
        for target in safety_files.values():
            durable_unlink(target)
        raise
    return safety_files


def _remove_database_file_group(destination: Path) -> None:
    for path in _database_file_group(destination):
        durable_unlink(path)


def _restore_safety_file_group(destination: Path, safety_files: dict[Path, Path]) -> None:
    _remove_database_file_group(destination)
    for target, safety_file in safety_files.items():
        _copy_file_durable(safety_file, target)


def create_online_backups(
    backup_dir: Path,
    *,
    retention_count: int,
    databases: Iterable[DatabaseName] = ALL_DATABASES,
    connection_provider: ConnectionProvider = get_connection,
    mirror_dir: Path | None = None,
    now: datetime | None = None,
    compression: bool = True,
    compression_level: int = 9,
) -> tuple[Path, ...]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    if mirror_dir is not None:
        mirror_dir.mkdir(parents=True, exist_ok=True)
        if mirror_dir.resolve() == backup_dir.resolve():
            raise ValueError("SQLite 备份镜像目录不能与主备份目录相同")
    timestamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    created: list[Path] = []
    for database in databases:
        _cleanup_incomplete_backups(backup_dir, database)
        if mirror_dir is not None:
            _cleanup_incomplete_backups(mirror_dir, database)
        suffix = ".sqlite3.gz" if compression else ".sqlite3"
        destination = backup_dir / f"{database}-{timestamp}{suffix}"
        temporary = backup_dir / f".{database}-{timestamp}.sqlite3.tmp"
        durable_unlink(temporary)
        try:
            target = sqlite3.connect(temporary)
            try:
                connection_provider(database).backup(target)
            finally:
                target.close()
            if compression:
                _publish_compressed_backup(
                    temporary,
                    destination,
                    compresslevel=compression_level,
                )
            else:
                _publish_verified_backup(temporary, destination)
        except Exception:
            durable_unlink(temporary)
            raise
        finally:
            durable_unlink(temporary)
        created.append(destination)
        _prune_backups(backup_dir, database, retention_count)
        if mirror_dir is not None:
            _copy_verified_backup(destination, mirror_dir / destination.name)
            _prune_backups(mirror_dir, database, retention_count)
    return tuple(created)


def restore_database_backup(
    source: Path,
    destination: Path,
    *,
    safety_dir: Path | None = None,
    now: datetime | None = None,
) -> Path | None:
    """Restore one SQLite database from a verified backup while the app is stopped."""
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    _verify_checksum(source)
    _verify_backup_artifact(source)

    destination.parent.mkdir(parents=True, exist_ok=True)
    timestamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    safety_copy: Path | None = None
    safety_files: dict[Path, Path] = {}
    if destination.exists():
        target_dir = (safety_dir or destination.parent / "pre-restore").resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        safety_copy = target_dir / f"{destination.stem}-pre-restore-{timestamp}{destination.suffix}"
        safety_files = _create_safety_file_group(destination, safety_copy)

    temporary = destination.with_name(f"{destination.name}.restore.tmp")
    durable_unlink(temporary)
    destination_modified = False
    try:
        if source.name.endswith(".sqlite3.gz"):
            _decompress_sqlite(source, temporary)
        else:
            _copy_file_durable(source, temporary)
        _verify_backup(temporary)
        for stale_sidecar in _database_file_group(destination)[1:]:
            destination_modified = destination_modified or stale_sidecar.exists()
            durable_unlink(stale_sidecar)
        destination_modified = True
        durable_replace(temporary, destination)
        _verify_backup(destination)
    except Exception:
        durable_unlink(temporary)
        if destination_modified:
            if safety_files:
                _restore_safety_file_group(destination, safety_files)
            else:
                _remove_database_file_group(destination)
        raise
    return safety_copy


__all__ = [
    "backup_databases_due",
    "backup_freshness_snapshot",
    "create_online_backups",
    "restore_database_backup",
    "verify_database_integrity",
]
