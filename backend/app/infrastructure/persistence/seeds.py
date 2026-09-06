"""行业库种子数据：空库首次初始化时从 backend/seeds/*.csv.gz 自动播种。

设计动机：industry_data.db 是运行时可写的 SQLite 库，提交进 git 会导致
随机运行时状态入库、多机冲突与历史膨胀。改为仓库只携带可 diff 的压缩
CSV 种子（申万行业分类、概念映射、个股资料），库本体在首次初始化时重建。

种子契约：
- 种子内容 = 表的"逻辑内容"，自增主键列（id）不进种子，由数据库生成；
- 导出（export_seed_tables）与加载（seed_industry_database）共享同一套
  列计算，加载时校验种子表头与表结构匹配，列不齐整表跳过；
- 播种在单个事务内完成，任一表失败整体回滚，不产生半播种状态；
- 只在目标表为空时播种——运行时产生的数据永远不会被种子覆盖。

种子由 `make backend-export-seeds` 从当前库导出；派生表（stock_concepts）
与运行时状态表不入种子。
"""

from __future__ import annotations

import csv
import gzip
import logging
import sqlite3
from pathlib import Path

from app.configuration.paths import SEEDS_DIR

logger = logging.getLogger(__name__)

# 播种顺序即依赖顺序；均为种子内容表，运行时状态表不入列
SEED_TABLES: tuple[str, ...] = (
    "sw_industry_classifications",
    "stock_concept_mappings",
    "stock_basic_profiles",
)


def _table_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()]


def _autoincrement_column(connection: sqlite3.Connection, table: str) -> str | None:
    """返回单列整型主键（rowid 别名，自增 id），无则 None。"""
    info = connection.execute(f"PRAGMA table_info({table})").fetchall()
    pk_columns = [str(row[1]) for row in info if int(row[5]) > 0]
    if len(pk_columns) != 1:
        return None
    pk_type = next((str(row[2]).upper() for row in info if str(row[1]) == pk_columns[0]), "")
    return pk_columns[0] if pk_type == "INTEGER" else None


def seedable_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    columns = _table_columns(connection, table)
    autoinc = _autoincrement_column(connection, table)
    if autoinc is not None:
        return [column for column in columns if column != autoinc]
    return columns


def export_seed_tables(connection: sqlite3.Connection, output_dir: Path) -> list[Path]:
    """把种子表全量导出为 gzip CSV（不含自增主键），返回写出的文件列表。"""
    try:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:  # noqa: BLE001 - WAL 不可用时直接读，读路径仍可见 WAL 数据
        pass

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for table in SEED_TABLES:
        columns = seedable_columns(connection, table)
        rows = connection.execute(f"SELECT {','.join(columns)} FROM {table}").fetchall()
        path = output_dir / f"{table}.csv.gz"
        with gzip.open(path, "wt", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(columns)
            writer.writerows(rows)
        logger.info("种子导出: %s %s 行 -> %s", table, len(rows), path)
        written.append(path)
    return written


def seed_industry_database(
    connection: sqlite3.Connection,
    *,
    seeds_dir: Path | None = None,
) -> dict[str, int]:
    """目标表为空时从种子文件导入；返回各表导入行数（未导入的表不在结果中）。

    单事务全成全败：任一表导入失败即整体回滚，下次启动重试。
    """
    seeds_dir = seeds_dir or SEEDS_DIR
    if not seeds_dir.is_dir():
        logger.debug("种子目录不存在，跳过播种: %s", seeds_dir)
        return {}

    imported: dict[str, int] = {}
    try:
        connection.execute("BEGIN IMMEDIATE")
        for table in SEED_TABLES:
            seed_path = seeds_dir / f"{table}.csv.gz"
            if not seed_path.is_file():
                continue
            existing = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            if existing:
                continue

            valid_columns = set(seedable_columns(connection, table))
            with gzip.open(seed_path, "rt", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                fieldnames = list(reader.fieldnames or [])
                unknown = sorted(set(fieldnames) - valid_columns)
                if not fieldnames or unknown:
                    logger.warning(
                        "种子文件列与表结构不匹配，跳过 %s: unknown=%s", table, unknown
                    )
                    continue
                rows = [[row.get(column) for column in fieldnames] for row in reader]
            if not rows:
                continue

            placeholders = ",".join("?" for _ in fieldnames)
            connection.executemany(
                f"INSERT INTO {table} ({','.join(fieldnames)}) VALUES ({placeholders})",
                rows,
            )
            imported[table] = len(rows)
        connection.commit()
    except sqlite3.Error as error:
        connection.rollback()
        logger.warning("行业库种子播种失败，已整体回滚: %s", error)
        return {}

    if imported:
        logger.info("行业库种子播种完成: %s", imported)
    return imported
