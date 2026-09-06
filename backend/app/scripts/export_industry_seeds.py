"""导出行业库种子表为压缩 CSV（backend/seeds/*.csv.gz），供空库自动播种。

用法: uv run python -m app.scripts.export_industry_seeds [--output DIR]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.configuration.paths import SEEDS_DIR
from app.infrastructure.persistence.connection import get_connection
from app.infrastructure.persistence.seeds import export_seed_tables


def main() -> None:
    parser = argparse.ArgumentParser(description="导出行业库种子表（供空库自动播种）")
    parser.add_argument("--output", default=str(SEEDS_DIR), help="输出目录，默认 backend/seeds")
    args = parser.parse_args()

    connection = get_connection("industry")
    paths = export_seed_tables(connection, Path(args.output))
    total = sum(path.stat().st_size for path in paths)
    print(f"导出完成: {len(paths)} 个文件，共 {total / 1024:.0f} KB -> {Path(args.output)}")


if __name__ == "__main__":
    main()
