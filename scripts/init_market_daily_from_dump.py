#!/usr/bin/env python3
"""把 Fuyao 全市场 dump 导入 market_daily 历史行情库（历史数据初始化）。

数据源（data/ 目录，可用 scripts/read_market_dump.py 检查）:
  - a_share_daily_k_1d_none_10y_YYYYMMDD.parquet
      全市场日 K，不复权。行键 (thscode, date_ms)，volume 单位为股，turnover 为成交额（元）。
  - a_share_adjustment_factors_event_none_all_YYYYMMDD.parquet
      全部除权除息事件（每股口径）。行键 (thscode, ex_date_ms)。

写入目标（backend/app/modules/market_daily/repository.py 定义的 schema）:
  - market_daily_bars                 未复权日 K（verification_status='confirmed'）
  - market_corporate_actions          公司行为（category=1 除权除息）
  - market_daily_adjustment_factors   仿射复权因子（tdxhub-gbbq 算法，与运行时一致）
  - market_adjustment_factor_state    因子状态

注意:
  - 本脚本只做一次性历史初始化，不写 observations / refresh_jobs / refresh_runs
    （那些表属于盘后刷新流水线的审计轨迹）。
  - 复权因子用与运行时相同的 tdxhub.gbbq 算法和 ALGORITHM_VERSION 计算，
    因此初始化后 apply_adjustment 可直接本地复权；24h TTL 到期后运行时会按
    action_hash 差异自动从 TDX 重新拉取并覆盖，无需人工干预。
  - 默认 --on-conflict skip：已存在的键一律保留（流水线写入的行绝不会被覆盖），
    只有同源 market-dump:* 的行才允许被刷新，换新 dump 重跑是安全的。
    --on-conflict overwrite 才会用 dump 值覆盖已有行。
  - 复权侧 skip 模式下，已覆盖完整因子的股票会整票跳过（保留运行时从 TDX 算的版本）。
  - 幂等：重复执行按 content_hash 跳过未变化行，revision 不会被无谓累加。

用法（必须用 backend 虚拟环境，依赖 tdxhub/pydantic/pyarrow）:
  backend/.venv/bin/python scripts/init_market_daily_from_dump.py
  backend/.venv/bin/python scripts/init_market_daily_from_dump.py --skip-factors
  backend/.venv/bin/python scripts/init_market_daily_from_dump.py --codes 600519,000001
  backend/.venv/bin/python scripts/init_market_daily_from_dump.py --on-conflict overwrite
  backend/.venv/bin/python scripts/init_market_daily_from_dump.py --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd
import pyarrow.parquet as pq
from app.modules.market_daily.adjustment import (
    ALGORITHM_VERSION,
    _build_factors,
)
from app.modules.market_daily.models import (
    MarketCorporateAction,
    MarketDailyBarRecord,
)
from app.modules.market_daily.paths import MARKET_DAILY_DATABASE_PATH
from app.modules.market_daily.repository import (
    MarketDailyBarRepository,
    _content_hash,
    _iso,
    _provenance_hash,
    _record_hash,
)
from pydantic import ValidationError

ZONE = ZoneInfo("Asia/Shanghai")
DEFAULT_DAILY_K = Path("data/a_share_daily_k_1d_none_10y_20261002.parquet")
DEFAULT_FACTORS = Path("data/a_share_adjustment_factors_event_none_all_20261002.parquet")
CATEGORY_EX_DIVIDEND = 1  # tdxhub CATEGORY_NAMES[1] = 除权除息
_PROGRESS_ROWS = 1_000_000
_PROGRESS_CODES = 250

_BAR_COLUMNS = [
    "thscode",
    "currency",
    "date_ms",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
    "turnover",
]

_UPSERT_BAR_SQL = """
INSERT INTO market_daily_bars (
    market, instrument_type, code, name, trade_date, currency, open, high, low,
    close, pre_close, change_amount, change_pct, volume, amount, adjustment,
    source, source_quote_time, verification_status, first_refreshed_at,
    last_refreshed_at, revision, data_hash, content_hash, provenance_hash
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
ON CONFLICT(market, instrument_type, code, trade_date, adjustment) DO UPDATE SET
    name=CASE WHEN excluded.name='' THEN market_daily_bars.name ELSE excluded.name END,
    currency=excluded.currency, open=excluded.open,
    high=excluded.high, low=excluded.low, close=excluded.close,
    pre_close=excluded.pre_close, change_amount=excluded.change_amount,
    change_pct=excluded.change_pct, volume=excluded.volume, amount=excluded.amount,
    source=excluded.source, source_quote_time=excluded.source_quote_time,
    verification_status=CASE
        WHEN excluded.verification_status='confirmed' THEN 'confirmed'
        ELSE market_daily_bars.verification_status
    END,
    last_refreshed_at=excluded.last_refreshed_at,
    revision=market_daily_bars.revision + CASE
        WHEN market_daily_bars.content_hash <> excluded.content_hash THEN 1 ELSE 0 END,
    data_hash=excluded.data_hash, content_hash=excluded.content_hash,
    provenance_hash=excluded.provenance_hash
WHERE {conflict_clause}
"""

# 默认 skip：只补空缺；只有同样是 dump 导入的行才允许被刷新（支持换新 dump 重跑），
# 流水线写入的行（source 不是 market-dump:*）一律不动。
_SKIP_CONFLICT_CLAUSE = """
    market_daily_bars.source LIKE 'market-dump:%'
    AND (
        market_daily_bars.content_hash <> excluded.content_hash
        OR market_daily_bars.provenance_hash <> excluded.provenance_hash
    )
"""
_OVERWRITE_CONFLICT_CLAUSE = """
    market_daily_bars.content_hash <> excluded.content_hash
    OR market_daily_bars.provenance_hash <> excluded.provenance_hash
"""


def bar_upsert_sql(on_conflict: str) -> str:
    clause = _OVERWRITE_CONFLICT_CLAUSE if on_conflict == "overwrite" else _SKIP_CONFLICT_CLAUSE
    return _UPSERT_BAR_SQL.format(conflict_clause=clause)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把 Fuyao 市场 dump 导入 market_daily 历史行情库。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--daily-k", type=Path, default=DEFAULT_DAILY_K, help="日 K parquet 路径")
    parser.add_argument("--factors", type=Path, default=DEFAULT_FACTORS, help="复权事件 parquet 路径")
    parser.add_argument(
        "--db",
        type=Path,
        default=MARKET_DAILY_DATABASE_PATH,
        help="market_daily SQLite 数据库路径",
    )
    parser.add_argument("--skip-bars", action="store_true", help="跳过日 K 导入")
    parser.add_argument("--skip-factors", action="store_true", help="跳过复权因子导入")
    parser.add_argument(
        "--codes",
        help="只导入指定 6 位代码（逗号分隔），用于试跑",
    )
    parser.add_argument("--batch-size", type=int, default=50000, help="日 K 每事务行数")
    parser.add_argument(
        "--on-conflict",
        choices=["skip", "overwrite"],
        default="skip",
        help=(
            "已存在同一 (market, instrument_type, code, trade_date, adjustment) 时的策略。"
            "skip=只补空缺（默认，不覆盖流水线写入的数据）；overwrite=用 dump 值覆盖。"
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="只统计数据量，不写库")
    return parser.parse_args()


def _date_from_ms(value: int) -> date:
    return datetime.fromtimestamp(value / 1000, ZONE).date()


def _code_from_thscode(thscode: str) -> str:
    return thscode.split(".", 1)[0]


def import_daily_bars(
    parquet_path: Path,
    repository: MarketDailyBarRepository,
    codes: set[str] | None,
    batch_size: int,
    on_conflict: str,
    dry_run: bool,
) -> None:
    source = f"market-dump:{parquet_path.stem}"
    upsert_sql = bar_upsert_sql(on_conflict)
    parquet_file = pq.ParquetFile(parquet_path)
    captured = _iso(datetime.now(UTC))
    scanned = written = invalid = 0
    invalid_samples: list[str] = []
    pending: list[tuple[object, ...]] = []

    with repository._connect() as probe:  # 预检：既有行只会被跳过，不会被覆盖
        existing = int(probe.execute(
            "SELECT COUNT(*) FROM market_daily_bars "
            "WHERE market='cn' AND instrument_type='stock'"
        ).fetchone()[0])
    existing_dump = 0
    if not dry_run and on_conflict == "skip":
        with repository._connect() as probe:
            existing_dump = int(probe.execute(
                "SELECT COUNT(*) FROM market_daily_bars "
                "WHERE market='cn' AND instrument_type='stock' AND source LIKE 'market-dump:%'"
            ).fetchone()[0])
    print(
        f"existing_cn_stock_bars={existing} (其中 dump 导入 {existing_dump} 行会被允许刷新) "
        f"on_conflict={on_conflict}"
    )

    connection: sqlite3.Connection | None = None
    if not dry_run:
        connection = repository._connect()  # 批量导入需要长事务连接
        connection.execute("PRAGMA cache_size=-64000")
        connection.execute("PRAGMA temp_store=MEMORY")

    def flush() -> None:
        nonlocal written
        if not pending:
            return
        if connection is not None:
            connection.execute("BEGIN IMMEDIATE")
            connection.executemany(upsert_sql, pending)
            connection.commit()
        written += len(pending)
        pending.clear()

    started = time.perf_counter()
    try:
        for batch in parquet_file.iter_batches(batch_size=batch_size, columns=_BAR_COLUMNS):
            for row in batch.to_pylist():
                scanned += 1
                code = _code_from_thscode(row["thscode"])
                if codes is not None and code not in codes:
                    continue
                try:
                    record = MarketDailyBarRecord(
                        market="cn",
                        instrument_type="stock",
                        code=code,
                        trade_date=_date_from_ms(row["date_ms"]),
                        currency="CNY",
                        open=row["open_price"],
                        high=row["high_price"],
                        low=row["low_price"],
                        close=row["close_price"],
                        pre_close=None,
                        change_amount=None,
                        change_pct=None,
                        volume=row["volume"],
                        amount=row["turnover"],
                        adjustment="none",
                        source=source,
                        source_quote_time=None,
                    )
                except ValidationError as error:
                    invalid += 1
                    if len(invalid_samples) < 10:
                        first = error.errors()[0]
                        invalid_samples.append(
                            f"{row['thscode']} {_date_from_ms(row['date_ms'])}: "
                            f"{first['loc']} {first['msg']}"
                        )
                    continue
                pending.append((
                    record.market, record.instrument_type, record.code, record.name,
                    record.trade_date.isoformat(), record.currency, record.open, record.high,
                    record.low, record.close, record.pre_close, record.change_amount,
                    record.change_pct, record.volume, record.amount, record.adjustment,
                    record.source, _iso(record.source_quote_time), "confirmed",
                    captured, captured,
                    _record_hash(record), _content_hash(record), _provenance_hash(record),
                ))
                if len(pending) >= batch_size:
                    flush()
                if scanned % _PROGRESS_ROWS == 0:
                    elapsed = time.perf_counter() - started
                    print(
                        f"  bars: scanned={scanned} queued_written={written} "
                        f"invalid={invalid} elapsed={elapsed:.0f}s",
                        flush=True,
                    )
        flush()
    finally:
        if connection is not None:
            connection.close()

    elapsed = time.perf_counter() - started
    print(
        f"bars_done: scanned={scanned} written={written} invalid={invalid} "
        f"elapsed={elapsed:.0f}s dry_run={dry_run}"
    )
    if invalid_samples:
        print("invalid_samples:")
        for sample in invalid_samples:
            print(f"  {sample}")


def load_and_merge_actions(factors_path: Path) -> pd.DataFrame:
    """读取除权除息事件并按 (thscode, ex_date) 合并重复行。

    dump 中存在同一除权日拆成多行的情况（现金与送转分列、特别分红单列），
    合并规则：现金分红/送转/配股比例按分量求和，配股价按配股比例加权平均。
    """
    frame = pd.read_parquet(factors_path)
    duplicated = frame.duplicated(subset=["thscode", "ex_date_ms"], keep=False)
    if duplicated.any():
        pairs = frame.loc[duplicated, ["thscode", "ex_date_ms"]].drop_duplicates()
        print(f"merge_duplicate_events: {len(pairs)} 组 (thscode, ex_date_ms) 需要合并")
    frame["_ratio_price"] = frame["allotment_ratio"] * frame["allotment_price"]
    merged = (
        frame.groupby(["thscode", "ex_date_ms"], as_index=False)
        .agg(
            dividend_per_share=("dividend_per_share", "sum"),
            per_share_bonus=("per_share_bonus", "sum"),
            allotment_ratio=("allotment_ratio", "sum"),
            _ratio_price=("_ratio_price", "sum"),
        )
    )
    ratio = merged["allotment_ratio"]
    merged["allotment_price"] = (merged["_ratio_price"] / ratio).where(ratio > 0, 0.0)
    return merged.drop(columns=["_ratio_price"]).sort_values(["thscode", "ex_date_ms"])


def build_actions_for_code(
    code: str,
    events: pd.DataFrame,
    source: str,
) -> tuple[pd.DataFrame, list[MarketCorporateAction], str]:
    """把每股口径事件转成 tdxhub gbbq 口径（每 10 股）并生成公司行为记录。"""
    frame = pd.DataFrame(
        {
            "category": CATEGORY_EX_DIVIDEND,
            # tdxhub 口径：fenhong/songzhuangu/peigu 均为每 10 股
            "fenhong": events["dividend_per_share"].to_numpy() * 10.0,
            "songzhuangu": events["per_share_bonus"].to_numpy() * 10.0,
            "peigu": events["allotment_ratio"].to_numpy() * 10.0,
            "peigujia": events["allotment_price"].to_numpy(),
        },
        index=pd.DatetimeIndex(
            pd.to_datetime(events["ex_date_ms"], unit="ms", utc=True)
            .dt.tz_convert("Asia/Shanghai")
            .dt.normalize()
            .dt.tz_localize(None),
            name="date",
        ),
    )
    actions: list[MarketCorporateAction] = []
    serializable: list[dict[str, object]] = []
    for action_date, row in frame.iterrows():
        action_text = pd.Timestamp(action_date).date().isoformat()
        payload = {key: float(row[key]) for key in sorted(frame.columns)}
        payload["category"] = CATEGORY_EX_DIVIDEND
        canonical = {"date": action_text, "sequence": 0, **payload}
        serializable.append(canonical)
        actions.append(MarketCorporateAction(
            code=code,
            action_date=pd.Timestamp(action_date).date(),
            sequence=0,
            category=CATEGORY_EX_DIVIDEND,
            category_name="除权除息",
            cash_dividend=float(row["fenhong"]),
            rights_shares=float(row["peigu"]),
            rights_price=float(row["peigujia"]),
            bonus_shares=float(row["songzhuangu"]),
            split_ratio=0.0,
            raw_json=json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            source=source,
        ))
    encoded = json.dumps(serializable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return frame, actions, hashlib.sha256(encoded.encode()).hexdigest()


def import_adjustment_factors(
    factors_path: Path,
    repository: MarketDailyBarRepository,
    codes: set[str] | None,
    on_conflict: str,
    dry_run: bool,
) -> None:
    action_source = f"market-dump:{factors_path.stem}"
    events = load_and_merge_actions(factors_path)
    calculated_at = datetime.now(UTC)
    # 6 位代码在 SH/SZ/BJ 间无冲突，直接按代码索引
    grouped = {code.split(".", 1)[0]: group for code, group in events.groupby("thscode")}

    with repository._connect() as connection:
        bar_codes = {
            row["code"]
            for row in connection.execute(
                "SELECT DISTINCT code FROM market_daily_bars "
                "WHERE market='cn' AND instrument_type='stock'"
            )
        }
    if codes is not None:
        bar_codes &= codes

    processed = failed = skipped_empty = skipped_existing = 0
    started = time.perf_counter()
    for index, code in enumerate(sorted(bar_codes), start=1):
        trading_dates = repository.list_stock_dates(code)
        if not trading_dates:
            skipped_empty += 1
            continue
        if on_conflict == "skip" and repository.list_adjustment_factor_dates(code) == trading_dates:
            # 已有覆盖完整的因子（通常是运行时从 TDX 算的），不替换
            skipped_existing += 1
            continue
        code_events = grouped.get(code)
        try:
            if code_events is None:
                frame = pd.DataFrame()
                actions: list[MarketCorporateAction] = []
                action_hash = hashlib.sha256(b"[]").hexdigest()
            else:
                frame, actions, action_hash = build_actions_for_code(code, code_events, action_source)
            factors = _build_factors(code, trading_dates, frame, action_hash, calculated_at)
            if not dry_run:
                repository.replace_adjustment_data(
                    code,
                    actions=actions,
                    factors=factors,
                    action_hash=action_hash,
                    algorithm_version=ALGORITHM_VERSION,
                    source=action_source,
                    calculated_at=calculated_at,
                )
            processed += 1
        except Exception as error:  # noqa: BLE001  # 单票失败不阻断全量导入
            failed += 1
            print(f"  factor_error: {code}: {type(error).__name__}: {error}", flush=True)
        if index % _PROGRESS_CODES == 0:
            elapsed = time.perf_counter() - started
            print(
                f"  factors: {index}/{len(bar_codes)} processed={processed} "
                f"failed={failed} elapsed={elapsed:.0f}s",
                flush=True,
            )

    elapsed = time.perf_counter() - started
    print(
        f"factors_done: codes={len(bar_codes)} processed={processed} "
        f"failed={failed} skipped_empty={skipped_empty} skipped_existing={skipped_existing} "
        f"elapsed={elapsed:.0f}s dry_run={dry_run}"
    )


def main() -> None:
    args = parse_args()
    if not args.skip_bars and not args.daily_k.is_file():
        raise SystemExit(f"ERROR: 日 K 文件不存在: {args.daily_k}")
    if not args.skip_factors and not args.factors.is_file():
        raise SystemExit(f"ERROR: 复权事件文件不存在: {args.factors}")

    codes = None
    if args.codes:
        codes = {item.strip() for item in args.codes.split(",") if item.strip()}
        print(f"codes_filter: {sorted(codes)}")

    repository = MarketDailyBarRepository(args.db)
    repository.initialize()
    print(f"database: {args.db}")

    if not args.skip_bars:
        print(f"import_bars: {args.daily_k}")
        import_daily_bars(
            args.daily_k, repository, codes, args.batch_size, args.on_conflict, args.dry_run
        )
    if not args.skip_factors:
        print(f"import_factors: {args.factors}")
        import_adjustment_factors(
            args.factors, repository, codes, args.on_conflict, args.dry_run
        )


if __name__ == "__main__":
    main()
