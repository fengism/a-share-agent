"""补齐行业股票名称：默认只读预览，--apply 先备份再只更新空名称。"""

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from app.configuration.paths import DATA_DIR
from app.domain.timezones import market_now
from app.infrastructure.persistence.master_data_repair import backfill_industry_stock_names


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATA_DIR / "db" / "industry_data.db")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    database = args.database.resolve(strict=True)
    mode = "rw" if args.apply else "ro"
    connection = sqlite3.connect(f"{database.as_uri()}?mode={mode}", uri=True, timeout=30)
    try:
        missing = connection.execute(
            "SELECT COUNT(*) FROM sw_industry_classifications WHERE TRIM(stock_name)=''"
        ).fetchone()[0]
        eligible = connection.execute(
            """SELECT COUNT(*) FROM sw_industry_classifications i
               JOIN stock_basic_profiles p ON p.stock_code=i.stock_code
               WHERE TRIM(i.stock_name)='' AND TRIM(p.stock_name)<>''"""
        ).fetchone()[0]
        result: dict[str, int | str] = {"missing": missing, "eligible": eligible, "applied": 0}
        if args.apply and eligible:
            backup_dir = database.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / f"industry-before-name-repair-{market_now():%Y%m%d-%H%M%S-%f}.db"
            with closing(sqlite3.connect(backup)) as destination:
                connection.backup(destination)
            result["applied"] = backfill_industry_stock_names(connection)
            result["backup"] = str(backup)
        result["remaining"] = connection.execute(
            "SELECT COUNT(*) FROM sw_industry_classifications WHERE TRIM(stock_name)=''"
        ).fetchone()[0]
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
