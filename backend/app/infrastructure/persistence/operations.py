"""SQLite 完整性检查与在线备份运维。"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path

from app.infrastructure.persistence.connection import ALL_DATABASES, DatabaseName, get_connection
from app.infrastructure.persistence.json_storage import atomic_write_text, durable_replace, durable_unlink

ConnectionProvider = Callable[[DatabaseName], sqlite3.Connection]


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


def _prune_backups(backup_dir: Path, database: str, retention_count: int) -> None:
    backups = sorted(backup_dir.glob(f"{database}-*.sqlite3"), reverse=True)
    for expired in backups[max(1, retention_count):]:
        durable_unlink(expired)
        durable_unlink(_checksum_path(expired))


def _cleanup_incomplete_backups(backup_dir: Path, database: str) -> None:
    for temporary in backup_dir.glob(f"{database}-*.sqlite3.tmp"):
        durable_unlink(temporary)
    for checksum in backup_dir.glob(f"{database}-*.sqlite3.sha256"):
        backup = checksum.with_name(checksum.name.removesuffix(".sha256"))
        if not backup.is_file():
            durable_unlink(checksum)


def _backup_created_at(path: Path) -> float:
    timestamp = path.stem.rsplit("-", maxsplit=1)[-1]
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
        backups = list(backup_dir.glob(f"{database}-*.sqlite3")) if backup_dir.is_dir() else []
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
    temporary = destination.with_name(f"{destination.name}.tmp")
    durable_unlink(temporary)
    _verify_checksum(source)
    try:
        shutil.copy2(source, temporary)
        _publish_verified_backup(temporary, destination)
    except Exception:
        durable_unlink(temporary)
        raise


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
        destination = backup_dir / f"{database}-{timestamp}.sqlite3"
        temporary = destination.with_suffix(".sqlite3.tmp")
        durable_unlink(temporary)
        try:
            target = sqlite3.connect(temporary)
            try:
                connection_provider(database).backup(target)
            finally:
                target.close()
            _publish_verified_backup(temporary, destination)
        except Exception:
            durable_unlink(temporary)
            raise
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
    _verify_backup(source)

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
    "backup_freshness_snapshot",
    "create_online_backups",
    "restore_database_backup",
    "verify_database_integrity",
]
