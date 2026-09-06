from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.infrastructure.persistence import init_db
from app.modules.stock_concept import importer, repository


def main():
    parser = argparse.ArgumentParser(description="从 CSV/Excel 导入个股概念数据")
    parser.add_argument("file_path", help="CSV 或 Excel 文件路径")
    parser.add_argument("--override", action="store_true", help="是否强制覆盖手工维护的数据")
    args = parser.parse_args()

    file_path = Path(args.file_path)
    if not file_path.exists():
        print(f"错误: 文件不存在: {file_path}", file=sys.stderr)
        sys.exit(1)

    print(f"正在初始化数据库并解析文件: {file_path.name} ...")
    init_db()

    with open(file_path, "rb") as f:
        content = f.read()

    parsed = importer.parse_data(content, file_path.name)
    print(f"文件读取完成: 总行数 {parsed.total_rows}，有效记录 {len(parsed.records)}，无效 {parsed.invalid_rows}")

    counts = repository.upsert_import_records(
        parsed.records,
        source_version=importer.default_source_version(file_path.name),
        force_override=args.override,
    )
    print(f"导入完成: 新增 {counts['added']}，更新 {counts['updated']}，未变更 {counts['unchanged']}，跳过 {counts['skipped']}")

    st = repository.stats()
    print(f"当前数据库统计: 股票数 {st['total_stocks']}, 概念去重总数 {st['total_concepts']}, 市场分布 {st['market_counts']}")


if __name__ == "__main__":
    main()
