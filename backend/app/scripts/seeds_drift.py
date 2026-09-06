"""对比运行时行业库与种子快照的差异（只读，不修改任何数据）。

用途：判断当前库状态是否值得固化为新种子。运行库因在线刷新/导入/enrich
持续演进，种子只在人工执行 `make backend-export-seeds` 时更新——本命令
把两者差异摆在明面上，由人来决定是否重导。

用法: uv run python -m app.scripts.seeds_drift [--seeds-dir DIR]
"""

from __future__ import annotations

import argparse
import csv
import gzip
from dataclasses import dataclass, field
from pathlib import Path

from app.configuration.paths import SEEDS_DIR
from app.infrastructure.persistence.connection import get_connection
from app.infrastructure.persistence.seeds import SEED_TABLES, seedable_columns

_SAMPLE_LIMIT = 3


@dataclass(frozen=True)
class TableDrift:
    """单张表的种子 vs 运行库对比结果。"""

    table: str
    seed_rows: int
    runtime_rows: int
    runtime_only: frozenset[tuple[str, ...]] = field(default_factory=frozenset)
    seed_only: frozenset[tuple[str, ...]] = field(default_factory=frozenset)
    schema_mismatch: bool = False
    mismatched_columns: tuple[str, ...] = ()
    seed_missing: bool = False

    @property
    def has_drift(self) -> bool:
        return self.seed_missing or self.schema_mismatch or bool(self.runtime_only or self.seed_only)


def _normalize(rows) -> frozenset[tuple[str, ...]]:
    # CSV 往返不保留类型与 NULL：统一按字符串、NULL→空串比较
    return frozenset(
        tuple("" if value is None else str(value) for value in row) for row in rows
    )


def compare_table(connection, table: str, seeds_dir) -> TableDrift:
    seed_path = seeds_dir / f"{table}.csv.gz"
    columns = seedable_columns(connection, table)
    runtime_rows = connection.execute(f"SELECT {','.join(columns)} FROM {table}").fetchall()
    runtime_set = _normalize(runtime_rows)

    if not seed_path.is_file():
        return TableDrift(
            table=table,
            seed_rows=0,
            runtime_rows=len(runtime_set),
            runtime_only=runtime_set,
            seed_missing=True,
        )

    with gzip.open(seed_path, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        seed_fieldnames = list(reader.fieldnames or [])
        seed_rows = [
            tuple(row.get(column) for column in seed_fieldnames) for row in reader
        ]
    seed_set = _normalize(seed_rows)

    # 种子列与当前表结构不一致时（schema 演进未重导），按交集列比较并显式报告
    mismatched = tuple(sorted(set(seed_fieldnames).symmetric_difference(columns)))
    if mismatched:
        common = [c for c in seed_fieldnames if c in columns]
        seed_idx = [seed_fieldnames.index(c) for c in common]
        runtime_idx = [columns.index(c) for c in common]
        seed_set = _normalize(
            [[row[i] for i in seed_idx] for row in seed_rows]
        )
        runtime_set = _normalize(
            [[row[i] for i in runtime_idx] for row in runtime_rows]
        )
        return TableDrift(
            table=table,
            seed_rows=len(seed_set),
            runtime_rows=len(runtime_set),
            runtime_only=runtime_set - seed_set,
            seed_only=seed_set - runtime_set,
            schema_mismatch=True,
            mismatched_columns=mismatched,
        )

    return TableDrift(
        table=table,
        seed_rows=len(seed_set),
        runtime_rows=len(runtime_set),
        runtime_only=runtime_set - seed_set,
        seed_only=seed_set - runtime_set,
    )


def _print_samples(rows: frozenset[tuple[str, ...]], label: str) -> None:
    if not rows:
        return
    print(f"    {label} {len(rows)} 行，示例:")
    for row in sorted(rows)[:_SAMPLE_LIMIT]:
        print(f"      {row}")


def build_report(connection, seeds_dir) -> list[TableDrift]:
    return [compare_table(connection, table, seeds_dir) for table in SEED_TABLES]


def main() -> None:
    parser = argparse.ArgumentParser(description="对比运行行业库与种子快照（只读）")
    parser.add_argument("--seeds-dir", default=str(SEEDS_DIR), help="种子目录，默认 backend/seeds")
    args = parser.parse_args()
    seeds_dir = Path(args.seeds_dir)

    connection = get_connection("industry")
    reports = build_report(connection, seeds_dir)

    drifted = [report for report in reports if report.has_drift]
    print("行业库 vs 种子快照对比（只读，不修改数据）")
    print(f"种子目录: {seeds_dir}\n")
    for report in reports:
        print(f"{report.table}")
        print(f"  行数: 运行库 {report.runtime_rows} / 种子 {report.seed_rows}")
        if report.seed_missing:
            print("  状态: 种子文件缺失")
            _print_samples(report.runtime_only, "运行库存在而种子缺失，")
            continue
        if report.schema_mismatch:
            print(f"  状态: 表结构漂移（差异列: {list(report.mismatched_columns)}），请重导种子")
            continue
        if not report.has_drift:
            print("  状态: 无差异")
            continue
        print("  状态: 存在差异")
        _print_samples(report.runtime_only, "运行库新增（种子缺失），")
        _print_samples(report.seed_only, "种子残留（运行库已无），")

    print(f"\n汇总: {len(reports) - len(drifted)}/{len(reports)} 张表无差异")
    if drifted:
        print("如需将当前库状态固化为新种子: make backend-export-seeds")


if __name__ == "__main__":
    main()
