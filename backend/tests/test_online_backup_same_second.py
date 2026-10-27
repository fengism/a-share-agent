"""create_online_backups: same-second reruns must not collide on the destination name."""

from datetime import UTC, datetime
from pathlib import Path

from app.infrastructure.persistence.operations import (
    _backup_created_at,
    create_online_backups,
)


def _tmp_backup_dir(tmp_path: Path) -> Path:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    return backup_dir


def test_same_second_rerun_bumps_timestamp_instead_of_failing(tmp_path: Path) -> None:
    backup_dir = _tmp_backup_dir(tmp_path)
    now = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)

    first = create_online_backups(
        backup_dir, retention_count=5, databases=("user",), compression=False, now=now
    )
    second = create_online_backups(
        backup_dir, retention_count=5, databases=("user",), compression=False, now=now
    )

    assert len(first) == 1 and len(second) == 1
    assert first[0] != second[0]
    assert first[0].exists() and second[0].exists()
    # Bumped name must still carry a parseable UTC timestamp.
    assert _backup_created_at(second[0]) == datetime(
        2026, 10, 22, 12, 0, 1, tzinfo=UTC
    ).timestamp()
