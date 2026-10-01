"""Offline SQLite restore command. Stop the backend before running it."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.infrastructure.persistence.connection import ALL_DATABASES, database_path
from app.infrastructure.persistence.operations import restore_database_backup


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore a verified stock-agent SQLite backup")
    parser.add_argument("database", choices=ALL_DATABASES)
    parser.add_argument("source", type=Path)
    parser.add_argument("--safety-dir", type=Path)
    parser.add_argument(
        "--confirm-backend-stopped",
        action="store_true",
        help="Confirm that no backend process is using the target database",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if not args.confirm_backend_stopped:
        raise SystemExit("拒绝恢复：请先停止后端，并传入 --confirm-backend-stopped")
    target = database_path(args.database)
    safety_copy = restore_database_backup(
        args.source,
        target,
        safety_dir=args.safety_dir,
    )
    print(f"数据库恢复完成: database={args.database} target={target}")
    if safety_copy is not None:
        print(f"恢复前安全副本: {safety_copy}")


if __name__ == "__main__":
    main()
